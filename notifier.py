#!/usr/bin/env python3
"""KNU SEE notice watcher -> Discord webhook (standard library only)."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen


STATE_PATH = Path(__file__).with_name("state.json")
USER_AGENT = "KNU-SEE-Discord-Notifier/1.0 (+personal notice watcher)"


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    list_url: str
    detail_url: str
    color: int
    emoji: str = "📢"
    parser_kind: str = "see_mobile"


@dataclass(frozen=True)
class Post:
    source: str
    post_id: str
    title: str
    author: str
    date: str
    url: str

    @property
    def key(self) -> str:
        return f"{self.source}:{self.post_id}"


SOURCES = (
    Source(
        key="notice",
        name="전자공학부 공지사항",
        list_url="https://see.knu.ac.kr/mobile/content/notice.html",
        detail_url="https://see.knu.ac.kr/mobile/content/notice.html?gtid=notice&pg=vv&fidx={post_id}",
        color=0x1F5EA8,
        emoji="🔵",
    ),
    Source(
        key="employment",
        name="전자공학부 취업게시판",
        list_url="https://see.knu.ac.kr/mobile/content/employment.html",
        detail_url="https://see.knu.ac.kr/mobile/content/employment.html?gtid=job&pg=vv&fidx={post_id}",
        color=0x2E8B57,
        emoji="🟢",
    ),
    Source(
        key="career_notice",
        name="진로취업 공지사항",
        list_url="https://home.knu.ac.kr/HOME/knujob/sub.htm?nav_code=knu1623817159",
        detail_url="",
        color=0xE67E22,
        emoji="🟠",
        parser_kind="knujob_table",
    ),
    Source(
        key="field_training",
        name="현장실습 공지사항",
        list_url="https://home.knu.ac.kr/HOME/knujob/sub.htm?nav_code=knu1623826179",
        detail_url="",
        color=0x8E44AD,
        emoji="🟣",
        parser_kind="knujob_table",
    ),
)


class BoardParser(HTMLParser):
    """Parse div.listbox entries without external dependencies."""

    def __init__(self, source: Source):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.posts: list[Post] = []
        self.depth = 0
        self.entry_depth: int | None = None
        self.post_id = ""
        self.capture = ""
        self.subject_parts: list[str] = []
        self.author_parts: list[str] = []
        self.date_parts: list[str] = []

    @staticmethod
    def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
        value = dict(attrs).get("class") or ""
        return set(value.split())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "div":
            self.depth += 1
            classes = self._classes(attrs)
            if self.entry_depth is None and "listbox" in classes:
                self.entry_depth = self.depth
                self.post_id = (dict(attrs).get("buid") or "").strip()
                self.subject_parts, self.author_parts, self.date_parts = [], [], []

        if self.entry_depth is not None:
            classes = self._classes(attrs)
            if tag == "li" and "subject" in classes:
                self.capture = "subject"
            elif tag == "span" and "neme" in classes:
                self.capture = "author"
            elif tag == "span" and "date" in classes:
                self.capture = "date"

    def handle_endtag(self, tag: str) -> None:
        if self.entry_depth is not None:
            # A subject <li> contains nested badge/category <span> tags. Closing
            # those spans must not stop subject capture.
            if tag == "li" and self.capture == "subject":
                self.capture = ""
            elif tag == "span" and self.capture in {"author", "date"}:
                self.capture = ""

        if tag == "div":
            if self.entry_depth is not None and self.depth == self.entry_depth:
                self._finish_entry()
                self.entry_depth = None
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.capture:
            return
        target = {
            "subject": self.subject_parts,
            "author": self.author_parts,
            "date": self.date_parts,
        }[self.capture]
        target.append(data)

    @staticmethod
    def _clean(parts: Iterable[str]) -> str:
        return re.sub(r"\s+", " ", html.unescape(" ".join(parts))).strip()

    def _finish_entry(self) -> None:
        title = self._clean(self.subject_parts)
        # Mobile markup includes badges/categories as text. Keep category, drop only badges.
        title = re.sub(r"^(공지\s+)+", "", title).strip()
        if not self.post_id or not title:
            return
        self.posts.append(
            Post(
                source=self.source.key,
                post_id=self.post_id,
                title=title,
                author=self._clean(self.author_parts),
                date=self._clean(self.date_parts),
                url=self.source.detail_url.format(post_id=self.post_id),
            )
        )


class KnuJobTableParser(HTMLParser):
    """Parse the table-based Career Development Center boards."""

    def __init__(self, source: Source):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.posts: list[Post] = []
        self.depth = 0
        self.board_depth: int | None = None
        self.in_row = False
        self.cell = ""
        self.href = ""
        self.parts: dict[str, list[str]] = {}

    @staticmethod
    def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
        return set((dict(attrs).get("class") or "").split())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "div":
            self.depth += 1
            if self.board_depth is None and "board_list" in self._classes(attrs):
                self.board_depth = self.depth
        if self.board_depth is None:
            return
        if tag == "tr":
            self.in_row = True
            self.href = ""
            self.parts = {"subject": [], "writer": [], "date": [], "category": []}
        elif self.in_row and tag == "td":
            classes = self._classes(attrs)
            self.cell = next((x for x in ("subject", "writer", "date", "category") if x in classes), "")
        elif self.in_row and tag == "a" and self.cell == "subject" and not self.href:
            self.href = (dict(attrs).get("href") or "").strip()

    def handle_data(self, data: str) -> None:
        if self.in_row and self.cell:
            self.parts[self.cell].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.board_depth is not None:
            if tag == "td":
                self.cell = ""
            elif tag == "tr" and self.in_row:
                self._finish_row()
                self.in_row = False
            elif tag == "div" and self.depth == self.board_depth:
                self.board_depth = None
        if tag == "div":
            self.depth -= 1

    @staticmethod
    def _clean(parts: Iterable[str]) -> str:
        return re.sub(r"\s+", " ", html.unescape(" ".join(parts))).strip()

    @staticmethod
    def _post_id(href: str) -> str:
        encoded = parse_qs(urlparse(href).query).get("mv_data", [""])[0]
        if encoded:
            try:
                decoded = base64.b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8")
                idx = parse_qs(decoded).get("idx", [""])[0]
                if idx:
                    return idx
            except (ValueError, UnicodeDecodeError):
                pass
        return hashlib.sha256(href.encode("utf-8")).hexdigest()[:20]

    def _finish_row(self) -> None:
        title = self._clean(self.parts.get("subject", []))
        if not title or not self.href:
            return
        category = self._clean(self.parts.get("category", []))
        if category:
            title = f"{category} {title}"
        absolute_url = urljoin(self.source.list_url, self.href)
        self.posts.append(
            Post(
                source=self.source.key,
                post_id=self._post_id(absolute_url),
                title=title,
                author=self._clean(self.parts.get("writer", [])),
                date=self._clean(self.parts.get("date", [])),
                url=absolute_url,
            )
        )


def fetch_text(url: str, attempts: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=25) as response:
                return response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"페이지 요청 실패: {url} ({last_error})")


def fetch_posts(source: Source) -> list[Post]:
    parser = BoardParser(source) if source.parser_kind == "see_mobile" else KnuJobTableParser(source)
    parser.feed(fetch_text(source.list_url))
    if not parser.posts:
        raise RuntimeError(f"게시글을 찾지 못했습니다. 사이트 구조 변경 가능성: {source.name}")
    # Pinned posts can appear twice: once in the pinned block and again in the
    # normal chronological list. Preserve the first occurrence only.
    unique: dict[str, Post] = {}
    for post in parser.posts:
        unique.setdefault(post.post_id, post)
    return list(unique.values())


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"initialized": False, "initialized_sources": [], "posts": {}}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"state.json을 읽을 수 없습니다: {exc}") from exc
    data.setdefault("initialized", False)
    data.setdefault("posts", {})
    if "initialized_sources" not in data:
        # Upgrade existing installations without replaying old notices.
        data["initialized_sources"] = (
            sorted({key.split(":", 1)[0] for key in data["posts"]}) if data["initialized"] else []
        )
    return data


def save_state(state: dict) -> None:
    temp = STATE_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(STATE_PATH)


def discord_request(webhook_url: str, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urlopen(req, timeout=25) as response:
            if response.status not in (200, 204):
                raise RuntimeError(f"Discord 응답 코드: {response.status}")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Discord 전송 실패: HTTP {exc.code} {detail}") from exc


def notify(webhook_url: str, source: Source, post: Post, event_type: str = "new") -> None:
    is_modified = event_type == "modified"
    event_label = "수정된 공지" if is_modified else "새 공지"
    title_icon = "✏️" if is_modified else "📌"
    payload = {
        "username": "KNU 전자공학부 알리미",
        "allowed_mentions": {"parse": []},
        "content": f"{source.emoji} **{source.name} {event_label}**",
        "embeds": [
            {
                "title": f"{title_icon} {post.title}"[:256],
                "url": post.url,
                "color": source.color,
                "fields": [
                    {"name": "출처 게시판", "value": f"{source.emoji} {source.name}", "inline": False},
                    {"name": "작성자", "value": post.author or "-", "inline": True},
                    {"name": "작성일", "value": post.date or "-", "inline": True},
                ],
                "footer": {"text": f"게시글 ID {post.post_id}"},
            }
        ],
    }
    discord_request(webhook_url, payload)


def test_webhook(webhook_url: str) -> None:
    discord_request(
        webhook_url,
        {
            "username": "KNU 전자공학부 알리미",
            "allowed_mentions": {"parse": []},
            "content": "✅ Discord 웹훅 연결 테스트에 성공했습니다.",
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Discord 연결 테스트만 전송")
    parser.add_argument("--dry-run", action="store_true", help="수집 결과만 출력하고 전송/저장하지 않음")
    args = parser.parse_args()

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url and not args.dry_run:
        print("DISCORD_WEBHOOK_URL 환경변수가 없습니다.", file=sys.stderr)
        return 2
    if args.test:
        test_webhook(webhook_url)
        print("Discord 연결 테스트를 보냈습니다.")
        return 0

    state = load_state()
    collected: list[tuple[Source, Post]] = []
    for source in SOURCES:
        posts = fetch_posts(source)
        print(f"{source.name}: {len(posts)}개 수집")
        collected.extend((source, post) for post in posts)

    if args.dry_run:
        for source, post in collected:
            print(json.dumps(asdict(post), ensure_ascii=False))
        return 0

    known = state["posts"]
    initialized_sources = set(state["initialized_sources"])
    baseline_sources: list[str] = []
    changed_items: list[tuple[Source, Post, str]] = []
    for source in SOURCES:
        source_posts = [post for item_source, post in collected if item_source.key == source.key]
        if source.key not in initialized_sources:
            for post in source_posts:
                known[post.key] = asdict(post)
            initialized_sources.add(source.key)
            baseline_sources.append(source.name)
        else:
            for post in source_posts:
                previous = known.get(post.key)
                if previous is None:
                    changed_items.append((source, post, "new"))
                    continue
                # Detect edits visible on the board list. View counts are not
                # stored, so ordinary traffic never creates false edit alerts.
                if any(previous.get(field, "") != getattr(post, field) for field in ("title", "author", "date")):
                    changed_items.append((source, post, "modified"))

    state["initialized"] = True
    state["initialized_sources"] = sorted(initialized_sources)
    # The page is newest-first; send oldest-first for readable Discord ordering.
    for source, post, event_type in reversed(changed_items):
        notify(webhook_url, source, post, event_type)
        known[post.key] = asdict(post)
        save_state(state)  # Avoid duplicate sends if a later item fails.
        label = "수정" if event_type == "modified" else "신규"
        print(f"{label} 알림 전송: [{source.name}] {post.title}")

    # Remember current metadata and keep state bounded.
    for _, post in collected:
        known[post.key] = asdict(post)
    if len(known) > 1000:
        current_keys = {post.key for _, post in collected}
        retained = {key: value for key, value in known.items() if key in current_keys}
        for key in list(known.keys())[-(1000 - len(retained)) :]:
            retained.setdefault(key, known[key])
        state["posts"] = retained
    save_state(state)
    if baseline_sources:
        print("기준점 저장(과거 글 알림 없음): " + ", ".join(baseline_sources))
    new_count = sum(1 for _, _, event_type in changed_items if event_type == "new")
    modified_count = sum(1 for _, _, event_type in changed_items if event_type == "modified")
    print(f"완료: 새 게시글 {new_count}개, 수정 게시글 {modified_count}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
