"""Django settings — webapp (D-99: 인증·화면·계정/펫/다이어리).

FastAPI 쪽(`src/pettriage/app/`)과 같은 `.env`를 공유한다 — `DATABASE_URL`이
그 예다. 값이 갈리면 두 서버가 다른 DB를 보게 되므로, 새 비밀 값을 추가할 땐
`.env.example`에도 반드시 같이 적는다.
"""

from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

import os  # noqa: E402 — load_dotenv 뒤에 와야 아래 os.environ 조회가 .env 값을 본다


# ── 비밀 ──────────────────────────────────────────────────
# 🔴 약한 기본 키로 조용히 뜨는 것을 막는다 (JWT_SECRET_KEY와 같은 이유 — D-41).
_secret_key = os.environ.get("DJANGO_SECRET_KEY", "")
if not _secret_key:
    raise RuntimeError(
        "DJANGO_SECRET_KEY 환경변수가 없습니다. .env 에 값을 넣으세요 — "
        'python -c "import secrets; print(secrets.token_urlsafe(48))"'
    )
SECRET_KEY = _secret_key

# 🔴 **기본값은 false 다.** `.env` 를 빠뜨린 배포에서 디버그 페이지가 켜진 채 뜨는 것이
#    가장 비싼 실패다. 로컬은 `.env` 에 `DJANGO_DEBUG=true` 를 넣는다 (.env.example).
#    SECRET_KEY 는 없으면 기동을 막고(D-41), DEBUG 는 없으면 안전한 쪽으로 간다.
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]


# ── 앱 ────────────────────────────────────────────────────

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "pets",
    "diary",
    "chat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "webapp.middleware.KSTMiddleware",
]

ROOT_URLCONF = "webapp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "chat.context_processors.active_pet",
            ],
        },
    },
]

WSGI_APPLICATION = "webapp.wsgi.application"


# ── DB ──────────────────────────────────────────────────
# ⚠️ FastAPI의 DATABASE_URL을 그대로 쓰지 않는다. Django의 pets/diary_entries
# 테이블은 이름은 SQLAlchemy 원본과 같지만 컬럼이 다르다 — 특히 `user_id`가
# SQLAlchemy는 문자열(UUID)인데 Django는 정수(auth.User PK)다. 같은 파일을
# 공유하면 둘 중 먼저 만든 스키마를 다른 쪽이 잘못 읽는다. accounts·pets·records가
# FastAPI에서 완전히 빠지기 전까지는 DJANGO_DATABASE_URL로 별도 파일을 쓴다.
#
# SQLAlchemy 스타일(`sqlite+pysqlite://` · `mysql+pymysql://`)이라 Django가
# 바로 못 읽는다. `+드라이버` 부분만 걷어내고 나머지는 그대로 파싱한다.


def _database_from_url(url: str) -> dict:
    scheme, sep, rest = url.partition("://")
    if not sep:
        raise RuntimeError(f"DATABASE_URL 형식이 아닙니다: {url!r}")
    dialect = scheme.split("+")[0]

    if dialect == "sqlite":
        # partition이 "://"의 슬래시 2개를 먹으므로 rest 맨 앞엔 슬래시가 하나 남는다
        # (SQLAlchemy 세 슬래시 관례와 동일) — 그 한 글자만 걷어낸다.
        path = rest[1:]
        name = ":memory:" if path == ":memory:" else str(BASE_DIR / path)
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": name}

    if dialect == "mysql":
        import pymysql

        pymysql.install_as_MySQLdb()  # Django의 mysql 백엔드는 MySQLdb API를 기대한다
        parsed = urlsplit(f"mysql://{rest}")
        return {
            "ENGINE": "django.db.backends.mysql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username or "",
            "PASSWORD": parsed.password or "",
            "HOST": parsed.hostname or "localhost",
            "PORT": str(parsed.port or 3306),
        }

    raise RuntimeError(f"지원하지 않는 DATABASE_URL 방언입니다: {dialect!r}")


_database_url = os.environ.get("DJANGO_DATABASE_URL", "")
if not _database_url:
    raise RuntimeError("DJANGO_DATABASE_URL 환경변수가 없습니다. .env 파일을 확인하세요.")

DATABASES = {"default": _database_from_url(_database_url)}


# ── 비밀번호 검증 ────────────────────────────────────────────

# 🔒 **D-104 — `AUTH_USER_MODEL` 을 설정하지 않는다.** Django 기본 `auth.User`(정수 PK)를
#    쓰기로 확정했다 (2026-08-26). 여기에 커스텀 모델을 지정하면 `pets` · `diary_entries` 의
#    "주인" 칸 타입이 바뀌고, 마이그레이션이 한 번이라도 적용된 뒤에는 되돌리기가 매우 비싸다.
#    바꾸려면 D-104 를 먼저 뒤집는다. 배경은 `accounts/models.py` 머리말.

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ── 국제화 ────────────────────────────────────────────────
# models.py(SQLAlchemy)와 같은 원칙 — UTC로 저장하고 표시 계층에서 KST로 바꾼다.

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# ── 정적 파일 ─────────────────────────────────────────────
# 🔴 **`/static/` 은 3차 FastAPI 가 쓰고 있다.** nginx 가 `/static/` 을 통째로 8001 로
#    보내므로(docker/nginx/nginx.conf), Django 관리자가 `/static/admin/...` 을 부르면
#    FastAPI 로 가서 **404 다** — 관리자 화면의 CSS 가 안 뜬다 (12 §3.1 · 11 §6.2).
#
#    접두사를 갈라 놓는다. `/django-static/` 은 nginx 의 `location /` 규칙에 걸려
#    Django 로 온다. 6단계에서 3차 `web/` 을 지우면 `/static/` 을 되찾을 수 있다.
STATIC_URL = "/django-static/"

# `collectstatic` 이 모아 놓을 자리. **이게 없으면 collectstatic 이 실행되지 않는다** —
# 배포에서 관리자·DRF 화면의 정적 파일을 nginx 가 서빙할 방법이 사라진다 (12 §9).
STATIC_ROOT = BASE_DIR / "staticfiles"

# ⚠️ `STATICFILES_DIRS` 를 두지 않는다. 프로젝트 공용 정적 파일이 아직 없고
#    (`{% static %}` 을 쓰는 템플릿이 하나도 없다), 없는 폴더를 가리키면
#    `check` 가 매번 W004 로 경고한다. 생기면 그때 되살린다 (D-58).

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/chat/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ── 추론 서비스(FastAPI) 내부 호출 ──────────────────────────
# GET /api/report가 요약(LLM)만 여기로 위임한다 (D-99 3안). 외부에 안 열리는
# 내부망 주소다 (docs/14 §3.4).
#   🔴 **8001 이다.** 8000 은 Django 자기 포트라, 그 값이면 자기 자신을 부른다
#      (2026-08-24 수정 — nginx `upstream fastapi` 도 8001 이다).
INFERENCE_INTERNAL_URL = os.environ.get("INFERENCE_INTERNAL_URL", "http://127.0.0.1:8001")


# ── 다이어리 체중 급변 알림 (D-103) ──────────────────────────
# **변화율은 사용자 기록에서 나오지만 임계값은 외부 주장이다.** 그래서 코드가 아니라
# 설정에 둔다 (D-41). `configs/*.yaml` 이 아니라 여기인 이유는 이것이 **Django 쪽 기능**
# 이라서다 — 추론 파이프라인 설정과 섞지 않는다. 판정 경로로 옮겨 가면 그때 같이 옮긴다.
#
#   5% 미만          — 알리지 않는다 (정상 범위)
#   5% 이상 10% 미만 — "당분간 지켜봐 주세요"
#   10% 이상          — "수의사와 상담해보세요"
DIARY_WEIGHT_ALERT_WATCH_PCT = float(os.environ.get("DIARY_WEIGHT_ALERT_WATCH_PCT", "5.0"))
DIARY_WEIGHT_ALERT_VET_PCT = float(os.environ.get("DIARY_WEIGHT_ALERT_VET_PCT", "10.0"))


# ── 배포 보안 (2026-08-26 전체 점검 C) ───────────────────────
# 🔴 **여섯 항목이 하나도 없었다.** `DEBUG=false` 는 첫 단추일 뿐이다 — HTTPS 로 올리면서
#    `SESSION_COOKIE_SECURE` 가 없으면 **세션 쿠키가 평문 경로로도 나간다.**
#
# 개발(`DEBUG=true`)에서는 전부 끈다. 로컬은 http 라, 켜면 로그인이 되지 않는다.
# **환경에 따라 갈리는 것을 코드가 알게 두지 않고 `DEBUG` 하나에 묶는다** — 배포에서
# `.env` 를 빠뜨리면 `DEBUG` 가 false 이므로 **안전한 쪽으로 잠긴다.**
#
# 빠진 것이 있는지는 사람이 기억하지 않는다:  python manage.py check --deploy
_PROD = not DEBUG

SECURE_SSL_REDIRECT = _PROD
SESSION_COOKIE_SECURE = _PROD
CSRF_COOKIE_SECURE = _PROD
SECURE_HSTS_SECONDS = 31536000 if _PROD else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = _PROD
SECURE_HSTS_PRELOAD = _PROD
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# nginx 뒤에 있으므로 **원 요청이 https 였는지는 헤더로만 알 수 있다.**
# 이 줄이 없으면 `SECURE_SSL_REDIRECT` 가 무한 리다이렉트를 만든다.
#   ⚠️ nginx 가 이 헤더를 **반드시 덮어써야** 한다. 사용자가 보낸 값을 그대로 믿으면
#      아무나 https 인 척할 수 있다 (`docker/nginx/nginx.conf` 참조).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# 도메인이 정해지면 여기에 넣는다 (`https://` 를 포함한 전체 주소).
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

# ── 업로드 상한 (D-43 관문과 짝) ─────────────────────────────
# 관문(`privacy/images.py`)이 5MB 를 거절하지만, **거기까지 가기 전에** Django 가
# 막는 편이 싸다 — 큰 본문을 메모리에 올리지 않는다.
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024


# ── DRF ──────────────────────────────────────────────────
# ⚠️ 임시 — 세션·Basic 인증만 켜져 있다. JWT냐 세션이냐는 docs/14 §7 미결이라
# 계정 앱이 정해지면 여기부터 바뀐다. 지금은 Django 로그인(관리자 계정 등)이 되면
# 그대로 API도 접근 가능한 수준으로만 맞춰 둔다.
REST_FRAMEWORK = {
    # 🔒 **세션 인증만 쓴다** (D-104 · 2026-08-26).
    #    `BasicAuthentication` 이 함께 켜져 있었다. 주석은 *"JWT 냐 세션이냐가 미결"* 이라
    #    임시라고 적었는데, **그 미결은 D-104 로 닫혔다.**
    #    쓰지 않는 인증 방식은 이득 없이 공격면만 넓힌다 — 브라우저 팝업 자격증명 경로가
    #    열려 있고, 자격증명이 매 요청에 실린다.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
}
