"""테스트용 Django 설정 — **실물 설정을 그대로 쓰고 두 가지만 바꾼다.**

    DJANGO_SETTINGS_MODULE=webapp.settings_test

🔴 **`webapp/settings.py` 를 베끼지 않는다.** `from webapp.settings import *` 로 통째로
   가져온다. 베끼면 미들웨어 한 줄이 늘었을 때 테스트만 옛 구성으로 돌고,
   **CI 는 초록인데 배포는 깨지는** 상태가 된다 (D-22 · 단일 출처).

## 왜 이 파일이 필요한가

실물 설정은 `DJANGO_SECRET_KEY` 와 `DJANGO_DATABASE_URL` 이 없으면 **기동을 막는다.**
그건 옳다 — 약한 기본 키로 조용히 뜨는 것이 가장 비싼 실패다 (D-41). 하지만 CI 에는
`.env` 가 없으므로, **테스트에서만** 값을 채워 준다. 실물 설정의 검사는 그대로 둔다.

## ⚠️ 이 테스트가 못 보는 것

DB 가 **sqlite** 다. 배포는 MySQL 이므로 —

- MySQL 만의 것(문자셋 · 컬럼 길이 · `utf8mb4` 이모지 저장)은 **여기서 안 걸린다**
- 마이그레이션이 "돈다" 는 것은 *sqlite 에서 돈다* 는 뜻이다

그래도 둘 다 잡는다: **모델과 마이그레이션이 어긋난 것**, 그리고 **마이그레이션이
아예 안 도는 것**. 지금은 그것조차 지키는 테스트가 없다 (13 §5.2 ①).

MySQL 대조는 7b-4(DB 를 하나로) 뒤에 서비스 컨테이너로 붙인다 — 그때 이 주석을 지운다.
"""

from __future__ import annotations

import os

# ══════════════════════════════════════════════════════════════════════
# 🔴 **`import *` 보다 먼저, 그리고 `setdefault` 가 아니라 덮어쓴다.**
#
#    실물 설정은 임포트 시점에 `load_dotenv()` 로 `.env` 를 읽는다. `load_dotenv` 는
#    **이미 있는 환경변수를 덮지 않으므로**, 여기서 먼저 세우면 `.env` 를 이긴다.
#
#    ⚠️ **처음엔 `setdefault` 로 두고 `DJANGO_DEBUG` 는 아예 안 건드렸다. 틀렸다.**
#       그러면 테스트가 **각자의 `.env` 에 따라 다르게 돈다** —
#
#         `.env` 에 DJANGO_DEBUG=true 인 사람  → _PROD=False → SSL 리다이렉트 꺼짐
#         `.env` 가 없는 CI·컨테이너            → _PROD=True  → 켜짐
#
#       2026-08-27 에 실제로 갈렸다. 컨테이너에서 16건 전부 초록이던 것이 팀장
#       기계에서 `test_평문_http_는_https_로_넘어간다` 하나만 빨강으로 나왔다.
#       **코드는 같은데 결과가 달랐다.**
#
#       테스트는 **어디서 돌든 같은 것을 봐야** 신뢰를 얻는다. 그래서 네 값을 못박는다.
# ══════════════════════════════════════════════════════════════════════

# 🔒 **배포와 같은 모양으로 돌린다** (DEBUG=false). 로컬 개발 설정이 아니라
#    **우리가 실제로 내보내는 구성**을 검사한다 — `SECURE_SSL_REDIRECT` ·
#    `SESSION_COOKIE_SECURE` · `CSRF_COOKIE_SECURE` 가 여기서만 켜진다.
#    4차에서 비싸게 배운 것이 그것이다: 로컬만 보고 ✅ 를 적으면 공개된 쪽이 열려 있다.
os.environ["DJANGO_DEBUG"] = "false"

# 실물 비밀 키를 테스트가 만지지 않게 한다. 값 자체는 동작에 영향이 없다.
os.environ["DJANGO_SECRET_KEY"] = "test-only-not-a-real-secret"
os.environ["DJANGO_ALLOWED_HOSTS"] = "localhost,127.0.0.1"

# DB 는 아래에서 다시 못박지만, 설정 임포트가 **이 값 없이는 RuntimeError** 다.
os.environ["DJANGO_DATABASE_URL"] = "sqlite:///:memory:"

# 🔴 추론 서비스는 안 띄운다. **`.env` 의 실제 주소를 그대로 두면 안 된다** —
#    D-109 테스트(요약을 몇 번 부르나)가 살아 있는 서비스로 나가고,
#    돈이 나가고, 테스트가 네트워크를 기다린다 (13 §5.2 ④).
#    포트 1 은 닫혀 있어 연결이 즉시 거절된다.
os.environ["INFERENCE_INTERNAL_URL"] = "http://127.0.0.1:1"

from webapp.settings import *  # noqa: E402, F403

# 테스트는 **격리된 sqlite** 에서 돈다. 실물 `.env` 가 무엇을 가리키든 상관없이
# 같은 결과가 나와야 한다 — 팀원 기계에서 다르게 도는 테스트는 신뢰를 못 얻는다.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "TEST": {"NAME": ":memory:"},
    }
}

# 비밀번호 해싱을 느린 것에서 빠른 것으로. 테스트에서 bcrypt 라운드를 도는 것은
# **검증하는 바가 없고** 회원가입 테스트마다 수백 ms 를 먹는다.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# 파일 업로드는 임시 폴더로. 실물 `media/` 를 테스트가 더럽히지 않게 한다.
MEDIA_ROOT = "/tmp/pettriage-test-media"  # noqa: S108
