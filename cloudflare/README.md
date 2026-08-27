# Cloudflare Workers 배포

KNU 공지 알리미를 게시판별 독립 Worker로 매분 실행합니다.

## Worker 구성

- `knu-notice-discord-notifier`: 전자공학부 공지사항
- `knu-employment-discord-notifier`: 전자공학부 취업게시판
- `knu-career-discord-notifier`: 진로취업 공지사항
- `knu-field-training-discord-notifier`: 현장실습 공지사항
- `knu-ai-discord-notifier`: 인공지능혁신융합대학사업단 공지사항

모든 Worker는 같은 D1 `KNU-Notifier`를 사용하며, 각 Worker에 `DISCORD_WEBHOOK_URL` Secret이 필요합니다.

## 배포

```bash
npm install
npm run check:all
npm run deploy:all
```

새 Worker를 처음 만든 뒤에는 해당 설정 파일로 Discord Secret을 등록합니다.

```bash
npx wrangler secret put DISCORD_WEBHOOK_URL -c wrangler.field-training.jsonc
npx wrangler secret put DISCORD_WEBHOOK_URL -c wrangler.ai.jsonc
```

첫 실행은 현재 게시글을 기준점으로 저장하므로 기존 공지가 한꺼번에 전송되지 않습니다.
