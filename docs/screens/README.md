# 여기로 화면

모든 화면은 실제 앱을 헤드리스 브라우저로 띄워 찍었다. 테스터 폰은 412×892(갤럭시 S 계열), 운영 콘솔은 데스크톱 1366×900과 모바일 412×892. 라이트와 다크는 각각 `light/`, `dark/`에 있다.

한눈에 보기: [phone-light-overview.png](phone-light-overview.png) · [phone-dark-overview.png](phone-dark-overview.png)

## 테스터 폰 PWA "여기로"

| 번호 | 화면 | 설명 |
| --- | --- | --- |
| 01 | [no-tester](phone/light/01-no-tester.png) | 테스터 링크 없이 열었을 때 |
| 02 | [keypad](phone/light/02-keypad.png) | 삼성 전화 키패드 |
| 03 | [keypad-typed](phone/light/03-keypad-typed.png) | 번호 입력 중, 저장된 연락처 "여기로 기차예약" 추천 |
| 04 | [keypad-menu](phone/light/04-keypad-menu.png) | ⋮ 메뉴에서 메시지로 이동 |
| 05 | [contacts](phone/light/05-contacts.png) | 연락처 탭, 누르면 바로 발신 |
| 06 | [recents](phone/light/06-recents.png) | 최근기록 |
| 07 | [dialing](phone/light/07-dialing.png) | 발신 중, 링백음 |
| 08 | [in-call](phone/light/08-in-call.png) | 통화 중, 스피커 켜진 상태로 시작 |
| 09 | [in-call-keypad](phone/light/09-in-call-keypad.png) | 통화 중 키패드 |
| 10 | [pay-notice](phone/light/10-pay-notice.png) | 통화 중 카카오페이 결제 요청 알림 |
| 11 | [pay-sheet](phone/light/11-pay-sheet.png) | 카카오페이 결제창 |
| 12 | [pay-password](phone/light/12-pay-password.png) | 카카오페이 비밀번호(무작위 배열 키패드) |
| 13 | [pay-done](phone/light/13-pay-done.png) | 결제 완료 |
| 14 | [sms-notice](phone/light/14-sms-notice.png) | 통화 중 승차권 문자 알림 |
| 15 | [sms-list](phone/light/15-sms-list.png) | 삼성 메시지 목록 |
| 16 | [sms-thread](phone/light/16-sms-thread.png) | 삼성 메시지 대화, 링크 없는 승차권 문자 |
| 17 | [call-ended](phone/light/17-call-ended.png) | 통화 종료 |

## 운영 콘솔 PWA "여기로 운영"

| 번호 | 화면 | 데스크톱 | 모바일 |
| --- | --- | --- | --- |
| 01 | 로그인(ID/PW) | [desktop](console/light/01-login-desktop.png) | [mobile](console/light/01-login-mobile.png) |
| 02 | 개요(완주율 게이지, 되묻기, 동의 없는 예약, 통화 시간) | [desktop](console/light/02-overview-desktop.png) | [mobile](console/light/02-overview-mobile.png) |
| 03 | 통화 목록 | [desktop](console/light/03-calls-desktop.png) | [mobile](console/light/03-calls-mobile.png) |
| 04 | 통화 상세(자막·도구 호출·게이트 8조건·결제) | [desktop](console/light/04-call-detail-desktop.png) | [mobile](console/light/04-call-detail-mobile.png) |
| 05 | 실시간(진행 중 통화, 대리 예약, 운영 설정) | [desktop](console/light/05-live-desktop.png) | [mobile](console/light/05-live-mobile.png) |
| 06 | 테스터(설치 링크, QR) | [desktop](console/light/06-testers-desktop.png) | [mobile](console/light/06-testers-mobile.png) |

콘솔 캡처는 `?demo=1` 합성 데이터로 찍었다. 같은 주소에 `?demo=1`을 붙이면 로그인 없이 발표용 데모 화면이 열린다.

## 다시 찍기

```bash
npm run dev:phone & npm run dev:console      # 5199, 5174
node tools/capture-screens.mjs                # BROWSER=<chromium 경로>로 바꿀 수 있음
```
