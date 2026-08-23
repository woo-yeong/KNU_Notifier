# 경북대 전자공학부 Discord 공지 알리미

다음 네 게시판의 새 글을 10분마다 확인해 Discord로 전송합니다.

- 전자공학부 공지사항 전체: https://see.knu.ac.kr/mobile/content/notice.html
- 전자공학부 취업게시판: https://see.knu.ac.kr/mobile/content/employment.html
- 진로취업 공지사항: https://home.knu.ac.kr/HOME/knujob/sub.htm?nav_code=knu1623817159
- 현장실습 공지사항: https://home.knu.ac.kr/HOME/knujob/sub.htm?nav_code=knu1623826179

Discord 알림은 게시판별 색상과 아이콘을 사용합니다.

- 🔵 전자공학부 공지사항
- 🟢 전자공학부 취업게시판
- 🟠 진로취업 공지사항
- 🟣 현장실습 공지사항

알림 상단에는 출처 게시판이, 바로 아래에는 클릭 가능한 공지 제목이 표시됩니다.

같은 게시글 ID라도 목록에 표시되는 제목·작성자·작성일이 변경되면 `✏️ 수정된 공지`로 다시 알립니다. 조회수 변화는 수정으로 취급하지 않습니다. 게시판 목록에 드러나지 않는 본문만의 무표시 수정은 감지 대상이 아닙니다.

Python 외부 패키지가 필요하지 않습니다. 각 사이트의 게시글 고유 ID로 중복을 판별하므로 고정 공지의 순서가 바뀌어도 같은 글을 반복 전송하지 않습니다.

## 1. Discord 웹훅 만들기

1. 알림을 받을 Discord 채널의 **채널 편집**을 누릅니다.
2. **연동 → 웹후크 → 새 웹후크**를 선택합니다.
3. **웹후크 URL 복사**를 누릅니다.

웹훅 URL은 비밀번호와 같습니다. 코드나 공개 저장소에 직접 붙여 넣지 마세요.

## 2. GitHub 저장소 만들기

1. GitHub에서 새 저장소를 만듭니다. 공개·비공개 모두 가능합니다.
2. 이 폴더 안의 파일을 **폴더 구조 그대로** 저장소 최상단에 올립니다.
3. 저장소의 **Settings → Secrets and variables → Actions**로 이동합니다.
4. **New repository secret**을 누릅니다.
5. 이름은 `DISCORD_WEBHOOK_URL`, 값에는 복사한 Discord 웹훅 URL을 입력합니다.

## 3. 권한 설정

`state.json`을 자동 갱신하려면 다음 권한이 필요합니다.

1. 저장소 **Settings → Actions → General**로 이동합니다.
2. **Workflow permissions**에서 **Read and write permissions**를 선택합니다.
3. 저장합니다.

## 4. 최초 실행

1. 저장소의 **Actions** 탭을 엽니다.
2. 왼쪽에서 **Check KNU SEE notices**를 선택합니다.
3. **Run workflow**를 누릅니다.

각 게시판의 최초 실행은 현재 보이는 글을 기준점으로 저장하고 알림을 보내지 않습니다. 이 처리가 없으면 기존 공지가 한꺼번에 Discord로 전송됩니다. 이후부터 새로 등록된 게시글만 전송합니다. 나중에 게시판이 추가되어도 새 게시판의 과거 글만 조용히 기준점으로 저장합니다.

연결 자체를 시험하려면 **Run workflow** 창에서 `Send a Discord connection test only`를 체크하고 실행하세요.

## 동작 주기와 주의점

- 설정상 10분마다 실행하지만 GitHub Actions 사정에 따라 수분 이상 늦어질 수 있습니다.
- 학교 사이트가 일시적으로 응답하지 않으면 작업이 실패하고 다음 주기에 다시 시도합니다.
- 학교가 게시판 HTML 구조를 크게 바꾸면 Actions에서 오류가 납니다. 조용히 누락시키지 않고 실패하도록 설계했습니다.
- GitHub가 장기간 활동이 없는 공개 저장소의 예약 실행을 중지할 수 있으므로 Actions 탭을 가끔 확인하세요.
