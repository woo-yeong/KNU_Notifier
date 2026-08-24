# Cloudflare Workers 배포

이 디렉터리는 KNU 공지 알리미를 Cloudflare Workers에서 1분마다 실행하기 위한 코드입니다.

## 구성

- Cron: `* * * * *` (매분)
- 상태 저장: D1 `knu-notice-state`
- 비밀값: `DISCORD_WEBHOOK_URL`
- 상태 확인: 배포 URL의 `/health`

## 배포 순서

```bash
npm install
npx wrangler login
npx wrangler d1 create knu-notice-state
```

출력된 `database_id`를 `wrangler.jsonc`의 `REPLACE_WITH_D1_DATABASE_ID`에 넣습니다.

```bash
npx wrangler secret put DISCORD_WEBHOOK_URL
npm run check
npm run deploy
```

첫 실행은 현재 게시글을 기준점으로만 저장하며 과거 공지를 보내지 않습니다. Cloudflare 배포와 새 공지 감지 검증이 끝난 후에만 기존 GitHub Actions 예약 실행을 끕니다.
