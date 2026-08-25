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

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"

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
    "pets",
    "diary",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "webapp.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
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


STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ── 추론 서비스(FastAPI) 내부 호출 ──────────────────────────
# GET /api/report가 요약(LLM)만 여기로 위임한다 (D-99 3안). 외부에 안 열리는
# 내부망 주소라 로컬 개발 기본값은 127.0.0.1:8000이다 (docs/14 §3.4).
INFERENCE_INTERNAL_URL = os.environ.get("INFERENCE_INTERNAL_URL", "http://127.0.0.1:8000")


# ── DRF ──────────────────────────────────────────────────
# ⚠️ 임시 — 세션·Basic 인증만 켜져 있다. JWT냐 세션이냐는 docs/14 §7 미결이라
# 계정 앱이 정해지면 여기부터 바뀐다. 지금은 Django 로그인(관리자 계정 등)이 되면
# 그대로 API도 접근 가능한 수준으로만 맞춰 둔다.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
}
