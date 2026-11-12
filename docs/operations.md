# 배포와 운영

## 주소

| 무엇 | 주소 |
| --- | --- |
| 테스터 폰 PWA | https://yeogiro-kaist.web.app/t/&lt;토큰&gt; (테스터별 링크는 콘솔 테스터 탭에서 복사) |
| 운영 콘솔 PWA | https://yeogiro-kaist.web.app/console/ (계정은 조중휘에게 받기) |
| 통화 서버 | https://yeogiro-call-990320254644.asia-northeast3.run.app/api/health |

## 배포

```bash
# 통화 서버. Cloud Run 서울, 인스턴스 1개, 요청 타임아웃 1시간
gcloud run deploy yeogiro-call --source server --region asia-northeast3 \
  --account=<프로젝트 계정> --project=yeogiro-kaist

# 웹. 폰 앱은 apps/phone/.env.production 의 VITE_API_BASE 로 서버에 직접 붙습니다
npm run deploy:web
```

비밀값은 Secret Manager의 `openai-api-key`, `tago-service-key` 에서 Cloud Run 환경변수로 들어갑니다.

통화 세션이 서버 메모리에 있어서 인스턴스는 1개로 고정합니다. 서버를 다시 배포하면 진행 중인 통화가 끊기니 테스트가 없는 시간에 합니다.

폰 앱의 API와 SSE는 Hosting rewrite의 60초 제한을 피하려고 Cloud Run에 직접 연결합니다.

최소 인스턴스가 0이라 한동안 통화가 없으면 첫 연결이 몇 초 늦습니다. 시연 직전에는 `--min-instances 1` 로 올려 둡니다.

## 운영 명령

```bash
cd server
python -m yeogiro.admin seed-testers 12 --home 대전     # 테스터와 설치 링크 만들기
python -m yeogiro.admin add-admin <email>               # 콘솔 운영자 추가
python -m yeogiro.admin flags --rail-mode mock --booking on
python -m yeogiro.admin check-voice                     # 음성 세션 설정을 OpenAI가 받는지
python -m yeogiro.worker --check                        # 코레일 로그인과 조회 1회
```
