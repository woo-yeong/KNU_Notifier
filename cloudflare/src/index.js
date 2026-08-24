const SOURCES = [
  {
    key: "notice",
    name: "전자공학부 공지사항",
    url: "https://see.knu.ac.kr/mobile/content/notice.html",
    emoji: "🔵",
    color: 0x1f5ea8,
    kind: "see",
    detail: "https://see.knu.ac.kr/mobile/content/notice.html?gtid=notice&pg=vv&fidx=",
  },
  {
    key: "employment",
    name: "전자공학부 취업게시판",
    url: "https://see.knu.ac.kr/mobile/content/employment.html",
    emoji: "🟢",
    color: 0x2e8b57,
    kind: "see",
    detail: "https://see.knu.ac.kr/mobile/content/employment.html?gtid=job&pg=vv&fidx=",
  },
  {
    key: "career_notice",
    name: "진로취업 공지사항",
    url: "https://home.knu.ac.kr/HOME/knujob/sub.htm?nav_code=knu1623817159",
    emoji: "🟠",
    color: 0xe67e22,
    kind: "knujob",
  },
];

const USER_AGENT = "KNU-Notice-Discord-Notifier/2.0";

function decodeHtml(value) {
  return value
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;|&#160;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/\s+/g, " ")
    .trim();
}

function classText(block, className) {
  const pattern = new RegExp(
    `<[^>]+class=["'][^"']*\\b${className}\\b[^"']*["'][^>]*>([\\s\\S]*?)<\\/[^>]+>`,
    "i",
  );
  return decodeHtml(block.match(pattern)?.[1] || "");
}

function parseSee(source, html) {
  const posts = [];
  const entryPattern = /<div\b[^>]*\bclass=["'][^"']*\blistbox\b[^"']*["'][^>]*\bbuid=["']([^"']+)["'][^>]*>([\s\S]*?)(?=<div\b[^>]*\bclass=["'][^"']*\blistbox\b|$)/gi;
  for (const match of html.matchAll(entryPattern)) {
    const postId = match[1].trim();
    const block = match[2];
    const subjectMatch = block.match(/<li\b[^>]*\bclass=["'][^"']*\bsubject\b[^"']*["'][^>]*>([\s\S]*?)<\/li>/i);
    const title = decodeHtml(subjectMatch?.[1] || "").replace(/^(공지\s+)+/, "").trim();
    if (!postId || !title) continue;
    posts.push({
      source: source.key,
      postId,
      title,
      author: classText(block, "neme"),
      date: classText(block, "date"),
      url: `${source.detail}${postId}`,
    });
  }
  return dedupe(posts);
}

function extractAttribute(tag, name) {
  const pattern = new RegExp(`${name}=["']([^"']*)["']`, "i");
  return tag.match(pattern)?.[1] || "";
}

function parseKnuJob(source, html) {
  const board = html.match(/<div\b[^>]*\bclass=["'][^"']*\bboard_list\b[^"']*["'][^>]*>([\s\S]*?)<\/div>/i)?.[1] || html;
  const posts = [];
  for (const rowMatch of board.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/gi)) {
    const row = rowMatch[1];
    const subjectCell = row.match(/<td\b[^>]*\bclass=["'][^"']*\bsubject\b[^"']*["'][^>]*>([\s\S]*?)<\/td>/i)?.[1] || "";
    const anchor = subjectCell.match(/<a\b([^>]*)>([\s\S]*?)<\/a>/i);
    if (!anchor) continue;
    const href = extractAttribute(anchor[1], "href").replace(/&amp;/g, "&");
    const titleText = decodeHtml(anchor[2]);
    if (!href || !titleText) continue;
    const absoluteUrl = new URL(href, source.url).toString();
    const encoded = new URL(absoluteUrl).searchParams.get("mv_data") || "";
    let postId = "";
    try {
      const padded = encoded + "=".repeat((4 - (encoded.length % 4)) % 4);
      postId = new URLSearchParams(atob(padded)).get("idx") || "";
    } catch {
      postId = "";
    }
    if (!postId) postId = encoded.slice(0, 40) || absoluteUrl;
    const category = classText(row, "category");
    posts.push({
      source: source.key,
      postId,
      title: category ? `${category} ${titleText}` : titleText,
      author: classText(row, "writer"),
      date: classText(row, "date"),
      url: absoluteUrl,
    });
  }
  return dedupe(posts);
}

function dedupe(posts) {
  return [...new Map(posts.map((post) => [post.postId, post])).values()];
}

async function fetchPosts(source) {
  let lastError;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const response = await fetch(source.url, {
        headers: { "User-Agent": USER_AGENT, Accept: "text/html" },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const html = await response.text();
      if (html.length > 2_000_000) throw new Error("HTML response is unexpectedly large");
      const posts = source.kind === "see" ? parseSee(source, html) : parseKnuJob(source, html);
      if (!posts.length) throw new Error("게시글 0개: HTML 구조 변경 가능성");
      return posts;
    } catch (error) {
      lastError = error;
      if (attempt < 2) await new Promise((resolve) => setTimeout(resolve, 500 * 2 ** attempt));
    }
  }
  throw new Error(`${source.name} 수집 실패: ${lastError?.message || lastError}`);
}

async function ensureSchema(db) {
  await db.batch([
    db.prepare(`CREATE TABLE IF NOT EXISTS posts (
      source TEXT NOT NULL,
      post_id TEXT NOT NULL,
      title TEXT NOT NULL,
      author TEXT NOT NULL,
      post_date TEXT NOT NULL,
      url TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY (source, post_id)
    )`),
    db.prepare(`CREATE TABLE IF NOT EXISTS source_state (
      source TEXT PRIMARY KEY,
      initialized INTEGER NOT NULL DEFAULT 0,
      updated_at TEXT NOT NULL
    )`),
    db.prepare(`CREATE TABLE IF NOT EXISTS monitor_state (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )`),
  ]);
}

async function sendDiscord(webhookUrl, source, post, eventType) {
  const modified = eventType === "modified";
  const response = await fetch(webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json", "User-Agent": USER_AGENT },
    body: JSON.stringify({
      username: "KNU 전자공학부 알리미",
      allowed_mentions: { parse: [] },
      content: `${source.emoji} **${source.name} ${modified ? "수정된 공지" : "새 공지"}**`,
      embeds: [
        {
          title: `${modified ? "✏️" : "📌"} ${post.title}`.slice(0, 256),
          url: post.url,
          color: source.color,
          fields: [
            { name: "출처 게시판", value: `${source.emoji} ${source.name}`, inline: false },
            { name: "작성자", value: post.author || "-", inline: true },
            { name: "작성일", value: post.date || "-", inline: true },
          ],
        },
      ],
    }),
  });
  if (!response.ok) throw new Error(`Discord HTTP ${response.status}: ${(await response.text()).slice(0, 300)}`);
}

async function savePost(db, post, now) {
  await db.prepare(`INSERT INTO posts (source, post_id, title, author, post_date, url, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(source, post_id) DO UPDATE SET
      title=excluded.title, author=excluded.author, post_date=excluded.post_date,
      url=excluded.url, updated_at=excluded.updated_at`)
    .bind(post.source, post.postId, post.title, post.author, post.date, post.url, now)
    .run();
}

async function checkSource(env, source) {
  if (!env.DISCORD_WEBHOOK_URL) throw new Error("DISCORD_WEBHOOK_URL secret이 없습니다");

  const now = new Date().toISOString();
  const posts = await fetchPosts(source);
  const initialized = await env.DB.prepare(
    "SELECT initialized FROM source_state WHERE source = ?",
  ).bind(source.key).first();

  if (!initialized?.initialized) {
    await env.DB.batch(posts.map((post) => env.DB.prepare(`INSERT OR REPLACE INTO posts
      (source, post_id, title, author, post_date, url, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)`)
      .bind(post.source, post.postId, post.title, post.author, post.date, post.url, now)));
    await env.DB.prepare(`INSERT INTO source_state (source, initialized, updated_at) VALUES (?, 1, ?)
      ON CONFLICT(source) DO UPDATE SET initialized=1, updated_at=excluded.updated_at`)
      .bind(source.key, now).run();
    await recordSuccess(env.DB, source, 0, 0, now);
    return { source: source.key, newCount: 0, modifiedCount: 0, at: now };
  }

  const existingRows = await env.DB.prepare(
    "SELECT post_id, title, author, post_date FROM posts WHERE source = ?",
  ).bind(source.key).all();
  const existing = new Map(
    (existingRows.results || []).map((row) => [row.post_id, row]),
  );

  let newCount = 0;
  let modifiedCount = 0;
  for (const post of [...posts].reverse()) {
    const previous = existing.get(post.postId);
    let eventType = null;
    if (!previous) eventType = "new";
    else if (
      previous.title !== post.title
      || previous.author !== post.author
      || previous.post_date !== post.date
    ) {
      eventType = "modified";
    }

    if (!eventType) continue;

    await sendDiscord(env.DISCORD_WEBHOOK_URL, source, post, eventType);
    await savePost(env.DB, post, now);
    if (eventType === "new") newCount += 1;
    else modifiedCount += 1;
  }

  await env.DB.prepare(
    "UPDATE source_state SET updated_at = ? WHERE source = ?",
  ).bind(now, source.key).run();
  await recordSuccess(env.DB, source, newCount, modifiedCount, now);
  return { source: source.key, newCount, modifiedCount, at: now };
}

async function recordSuccess(db, source, newCount, modifiedCount, now) {
  await db.prepare(`INSERT INTO monitor_state (key, value, updated_at) VALUES ('last_success', ?, ?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at`)
    .bind(JSON.stringify({ source: source.key, newCount, modifiedCount }), now).run();
}

export default {
  async scheduled(_controller, env, _ctx) {
    const results = [];
    let currentSource = null;
    try {
      for (const source of SOURCES) {
        currentSource = source;
        results.push(await checkSource(env, source));
      }
      console.log(JSON.stringify({
        level: "info",
        event: "check_complete",
        sources: results.map((result) => result.source),
        newCount: results.reduce((sum, result) => sum + result.newCount, 0),
        modifiedCount: results.reduce((sum, result) => sum + result.modifiedCount, 0),
        at: new Date().toISOString(),
      }));
    } catch (error) {
      console.error(JSON.stringify({
        level: "error",
        event: "check_failed",
        source: currentSource?.key || "unknown",
        message: error.message,
        at: new Date().toISOString(),
      }));
      throw error;
    }
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/health") return new Response("Not Found", { status: 404 });
    const [lastSuccess, sourceStates] = await Promise.all([
      env.DB.prepare(
        "SELECT value, updated_at FROM monitor_state WHERE key = 'last_success'",
      ).first(),
      env.DB.prepare(
        "SELECT source, updated_at FROM source_state WHERE initialized = 1",
      ).all(),
    ]);
    const expectedSources = new Set(SOURCES.map((source) => source.key));
    const sources = Object.fromEntries(
      (sourceStates.results || [])
        .filter((row) => expectedSources.has(row.source))
        .map((row) => [row.source, row.updated_at]),
    );
    return Response.json({
      ok: Boolean(lastSuccess) && Object.keys(sources).length === SOURCES.length,
      lastSuccess: lastSuccess || null,
      sources,
    });
  },
};

export { decodeHtml, parseKnuJob, parseSee };
