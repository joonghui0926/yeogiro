# 기여 규칙

여기로는 PR로만 바뀝니다. 머지는 조중휘([joonghui0926](https://github.com/joonghui0926)) 한 사람만 합니다.

## 순서

1. 최신 `main` 에서 브랜치를 만듭니다. 이름에 종류와 내용을 담아 주세요. 예를 들면 `feat/keypad-haptics`, `fix/payment-timeout`
2. 한 PR에는 한 가지 변경만 담습니다
3. 아래 검사를 모두 통과시킨 뒤 PR을 열고 리뷰를 요청합니다
4. 조중휘가 리뷰하고 머지합니다. 승인 권한이 있더라도 다른 사람은 머지 버튼을 누르지 않습니다

## PR 전에 돌릴 것

```bash
cd server
.venv/Scripts/ruff check src tests
.venv/Scripts/python -m mypy src
.venv/Scripts/python -m pytest

cd ..
npm run typecheck && npm run build
```

화면을 바꿨다면 `node tools/capture-screens.mjs` 로 다시 찍은 캡처를 PR에 붙여 주세요.

## 꼭 지켜 주세요

비밀값은 `.env` 에만 둡니다. `.env.example` 에는 키 이름만 적습니다.

실제 결제는 연결하지 않습니다. 수업 규칙입니다.

코레일의 자동화 방지 장치를 우회하는 코드는 받지 않습니다.

주석은 코드만 보고 알 수 없는 이유가 있을 때만 씁니다.
