"""테스트 공통 픽스처.

이 프로젝트에는 프로세스 전역 상태가 셋 있다 — 설정 캐시(`lru_cache`),
엔진·세션·기록 저장소(`deps` 모듈 전역), 그리고 `main.app` 임포트 시점의 앱 인스턴스.

전역을 그대로 두면 **앞 테스트가 뒤 테스트를 오염시키고**, 그런 통과는
순서에 의존하는 가짜다. 그래서 매 테스트마다 초기화한다.
"""

from __future__ import annotations

# ══════════════════════════════════════════════════════════════
# 🔴 **이 블록은 `pettriage` 임포트보다 위에 있어야 한다.**
#
# `app/routes/__init__.py` 가 **임포트 시점에** `load_dotenv()` 로 `.env` 를
# `os.environ` 에 밀어 넣고 `os.getenv("DATABASE_URL")` 로 라우터 구성을 정한 뒤
# `ALL_ROUTERS` 를 모듈 상수로 굳힌다. 픽스처 안에서 환경변수를 바꿔도 이미 늦다.
#
# 비우지 않으면 **`.env` 에 `DATABASE_URL` 을 넣은 사람만 다른 앱을 테스트한다** —
# auth/pets/users 라우터가 켜지고, 로컬은 초록인데 CI 는 다른 구성을 돈다.
# `test_auth_api.py` 머리말이 경계하는 *"우리가 정하지 않은 것을 둘이 각자 정한다"* 이다.
#
# `load_dotenv()` 는 **이미 있는 환경변수를 덮지 않으므로** 여기서 세우면 `.env` 를 이긴다.
# DB 를 쓰는 테스트는 자기 앱을 따로 조립한다 (`test_auth_api.py`·`test_records_api.py`)
# 므로 영향이 없다 — 그쪽은 `dependency_overrides[get_db]` 로 SQLite 를 끼운다.
# ══════════════════════════════════════════════════════════════
import os

os.environ["DATABASE_URL"] = ""

# ── Django 앱 테스트는 `django` extra 가 있을 때만 수집한다 ──────────────
#
# 🔴 **없는 것을 없다고 말하고 넘어간다.** `.[api,dev]` 만 깐 구성(FastAPI 만 보는
#    팀원 · CI `db-deps` 잡)에서 `tests/django_apps/` 를 수집하면 임포트 에러로
#    **전체 스위트가 죽는다.** 반대로 조용히 건너뛰면 *"Django 테스트가 돌았다"* 로
#    읽힌다 — 그건 04 §8 이 금하는 **말 없는 검사 축소**다.
#
#    그래서 건너뛰되 이유가 보이게 둔다.
#
# 🔴 **`collect_ignore_glob = ["django_apps/*"]` 로는 안 막힌다** (2026-08-27 CI 에서 확인).
#    그건 **폴더 안의 파일**만 거르는데, pytest 는 그 전에 폴더로 내려가면서
#    `django_apps/conftest.py` 를 먼저 임포트한다. 그 conftest 첫 줄이
#    `from django.test import Client` 라서 거기서 죽고, **스위트 전체가 exit 2** 로 끝났다.
#
#        ERROR collecting tests/django_apps
#        E   ModuleNotFoundError: No module named 'django'
#
#    `collect_ignore` 에 **폴더 이름**을 주면 아예 내려가지 않으므로 conftest 도 안 읽는다.
#    로컬에서 `django` 임포트가 실패하는 가짜 모듈로 재현해서 고쳤다 — 고치기 전에
#    같은 오류가 나는 것을 먼저 봤다.
try:
    import django as _django  # noqa: F401

    _has_django = True
except ImportError:  # pragma: no cover - 구성에 따라 갈린다
    _has_django = False
    collect_ignore = ["django_apps"]
    print(
        "\n※ django 가 없어 tests/django_apps/ 를 건너뛴다 — "
        "돌리려면 pip install -e '.[api,db,django,dev]' -c constraints.txt\n"
    )

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from pettriage import config as config_mod  # noqa: E402
from pettriage.app import deps  # noqa: E402
from pettriage.app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_global_state(monkeypatch: pytest.MonkeyPatch):
    """설정 캐시와 전역 저장소를 테스트마다 비운다."""
    monkeypatch.delenv("PETTRIAGE_PROFILE", raising=False)
    monkeypatch.setenv("DATABASE_URL", "")  # 위 블록과 짝 — `Secrets` 가 `.env` 를 다시 읽는다
    for key in list(__import__("os").environ):
        if key.startswith("PETTRIAGE__"):
            monkeypatch.delenv(key, raising=False)
    config_mod.reset_caches()
    deps.reset_state()
    yield
    config_mod.reset_caches()
    deps.reset_state()


@pytest.fixture
def client() -> TestClient:
    """앱을 매번 새로 만든다 — 미들웨어·설정이 테스트마다 독립이어야 한다."""
    return TestClient(create_app())
