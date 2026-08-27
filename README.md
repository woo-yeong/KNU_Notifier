# 경북대학교 Discord 공지 알리미

경북대학교의 주요 공지 게시판을 매분 확인해 새 글과 수정된 글을 Discord로 전송하는 알림 서비스입니다.

## 알림 대상

| 게시판 | 확인 주기 |
| --- | --- |
| [전자공학부 공지사항](https://see.knu.ac.kr/mobile/content/notice.html) | 매분 |
| [전자공학부 취업게시판](https://see.knu.ac.kr/mobile/content/employment.html) | 매분 |
| [경북대학교 진로취업 공지사항](https://home.knu.ac.kr/HOME/knujob/sub.htm?nav_code=knu1623817159) | 매분 |
| [경북대학교 현장실습 공지사항](https://home.knu.ac.kr/HOME/knujob/sub.htm?nav_code=knu1623826179) | 매분 |
| [인공지능혁신융합대학사업단 공지사항](https://home.knu.ac.kr/HOME/aic/sub.htm?nav_code=aic1635293208) | 매분 |

Discord 알림에는 게시판 출처, 공지 제목, 작성자, 작성일, 원문 링크가 포함됩니다.

같은 게시글의 제목·작성자·작성일이 변경되면 수정된 공지로 다시 알립니다. 조회수 변화와 목록에 표시되지 않는 본문 수정은 감지하지 않습니다.

## Discord 참여

공지 알림을 받으려면 아래 서버에 참여하면 됩니다.

[전자공학부 알리미 Discord 서버 참여하기](https://discord.gg/ZZy8esfcm)

## 동작 구조

게시판별 Cloudflare Worker가 독립적으로 매분 실행됩니다.

| Worker | 담당 게시판 |
| --- | --- |
| `knu-notice-discord-notifier` | 전자공학부 공지사항 |
| `knu-employment-discord-notifier` | 전자공학부 취업게시판 |
| `knu-career-discord-notifier` | 진로취업 공지사항 |
| `knu-field-training-discord-notifier` | 현장실습 공지사항 |
| `knu-ai-discord-notifier` | 인공지능혁신융합대학사업단 공지사항 |

모든 Worker는 같은 Cloudflare D1 데이터베이스를 사용해 게시글 상태와 마지막 성공 시각을 저장합니다. 한 Worker에서 오류가 발생해도 다른 게시판의 수집에는 영향을 주지 않습니다.

## 주요 기능

- 게시판별 매분 독립 확인
- 게시글 고유 ID를 이용한 중복 전송 방지
- 제목·작성자·작성일 변경 감지
- 최초 실행 시 기존 글을 조용히 기준점으로 저장
- Cloudflare Observability 로그 지원
- GitHub Actions를 통한 5분 주기 상태 감시
- 특정 게시판이 10분 이상 성공하지 못하면 감시 작업 실패 처리

## 배포

`cloudflare` 디렉터리에서 실행합니다.

```bash
npm install
npm run check:all
npm run deploy:all
```

각 Worker에는 Discord 웹훅 Secret을 개별 등록해야 합니다.

```bash
npx wrangler secret put DISCORD_WEBHOOK_URL --config wrangler.jsonc
npx wrangler secret put DISCORD_WEBHOOK_URL --config wrangler.employment.jsonc
npx wrangler secret put DISCORD_WEBHOOK_URL --config wrangler.career.jsonc
npx wrangler secret put DISCORD_WEBHOOK_URL --config wrangler.field-training.jsonc
npx wrangler secret put DISCORD_WEBHOOK_URL --config wrangler.ai.jsonc
```

웹훅 URL은 비밀번호와 같습니다. 코드나 공개 저장소에 직접 저장하지 마세요.

## 상태 확인

대표 Worker의 Health 엔드포인트에서 다섯 게시판의 마지막 성공 시각을 확인할 수 있습니다.

[Worker 상태 확인](https://knu-notice-discord-notifier.wooyeong.workers.dev/health)
