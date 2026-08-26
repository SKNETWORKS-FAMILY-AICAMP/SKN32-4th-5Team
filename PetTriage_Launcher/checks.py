# -*- coding: utf-8 -*-
"""지금 무엇이 안 돼 있는지 한 줄로 보여 준다.

**런처의 절반은 이 파일이다.** 2026-08-04 에 겪은 문제 대부분이
*"지금 무엇이 안 돼 있는지 몰라서"* 생겼다 — 키가 빈 줄인 것도, 프로필이 없어
`stub` 이 답한 것도, 인덱스가 없어 검색이 0건인 것도 **돌려 보고 나서야** 알았다.

여기서 재는 것은 **빠른 것만**이다. 무거운 검사는 `scripts/doctor.py` 가 한다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OK, WARN, BAD = "OK", "!!", "XX"


def venv_python() -> Path:
    """이 저장소의 가상환경 파이썬. 있든 없든 경로는 계산된다."""
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def in_venv() -> bool:
    return Path(sys.prefix).resolve() == (ROOT / ".venv").resolve()


def check_venv() -> tuple[str, str]:
    if not venv_python().exists():
        return BAD, "없음 - [1] 부터"
    return (OK, "활성") if in_venv() else (WARN, "있으나 비활성")


def check_packages() -> tuple[str, str]:
    """**임포트로 확인한다.** 폴더가 있다고 깔린 것이 아니다."""
    if not in_venv():
        return WARN, "venv 밖이라 확인 불가"
    missing = []
    for mod, label in (
        ("pettriage", "본체"),
        ("django", "웹앱"),
        ("langgraph", "langgraph"),
        ("chromadb", "chromadb"),
        ("sqlalchemy", "[db]"),
        ("jwt", "[db]"),
    ):
        try:
            __import__(mod)
        except ImportError:
            missing.append(label)
    if missing:
        return BAD, f"빠짐: {' '.join(missing)} - [1]"
    return OK, "설치됨"


def find_docker() -> str | None:
    """`docker` 실행 파일. **PATH 에만 기대지 않는다.**

    Docker Desktop 을 **사용자 계정에 설치**하면 설치 관리자가 PATH 를 안 넣어 주는
    경우가 있다 (2026-08-26 · 4.87.0 · `%LOCALAPPDATA%\\Programs\\DockerDesktop`).
    그러면 앱은 멀쩡히 도는데 명령만 없어서 **설치가 실패한 줄 안다.**

    🔴 이 경로를 쓰는 쪽은 `_docker_env()` 로 **형제 실행 파일도 함께 찾게** 해야 한다.
       `docker` 는 자격 증명 헬퍼를 PATH 에서 찾으므로, 절반만 풀면 이미지 받기가 죽는다.
    """
    import shutil

    found = shutil.which("docker")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA", "")
    for cand in (
        Path(local) / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe",
        Path(local) / "Programs" / "Docker" / "Docker" / "resources" / "bin" / "docker.exe",
        Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        / "Docker" / "Docker" / "resources" / "bin" / "docker.exe",
    ):
        if cand.exists():
            return str(cand)
    return None


def check_docker() -> tuple[str, str]:
    """**실행 파일 유무만** 본다 — 상태줄은 매번 그려지므로 느리면 안 된다.

    엔진이 실제로 도는지는 `scripts/doctor.py` 가 본다 (`docker info` 는 수 초 걸린다).
    """
    import shutil

    if not find_docker():
        return WARN, "없음 — [5]는 2번으로"
    if shutil.which("docker"):
        return OK, "있음"
    # 런처는 절대 경로로 부르므로 이대로도 돈다. PowerShell 에서 직접 칠 때만 걸린다.
    return OK, "있음(PATH 밖 · 런처는 무관)"


def check_env() -> tuple[str, str]:
    """`.env` 는 있고 **키가 쓸 수 있는가.** 있음/없음만 보면 자리표시자가 통과한다."""
    env = ROOT / ".env"
    if not env.exists():
        return BAD, "없음 - [2]"
    try:
        from dotenv import dotenv_values
    except ImportError:
        return WARN, "확인 불가 (패키지 없음)"
    v = dotenv_values(str(env))
    bad = []
    if len((v.get("OPENAI_API_KEY") or "").strip()) < 20:
        bad.append("OPENAI_API_KEY")
    if len((v.get("JWT_SECRET_KEY") or "").strip()) < 16:
        bad.append("JWT_SECRET_KEY")
    if not (v.get("DATABASE_URL") or "").strip():
        bad.append("DATABASE_URL")
    # ── 4차 (D-99 · Django) ──
    #   🔴 `DJANGO_SECRET_KEY` 가 없으면 **Django 가 기동을 멈춘다** (webapp/settings.py · D-41).
    #      런처가 이것을 안 보면 ".env ✅" 라고 해 놓고 웹앱이 안 뜬다.
    if len((v.get("DJANGO_SECRET_KEY") or "").strip()) < 16:
        bad.append("DJANGO_SECRET_KEY")
    #   추론 주소가 8000(= Django 자기 포트)이면 GET /api/report 가 자기 자신을 부른다.
    inf = (v.get("INFERENCE_INTERNAL_URL") or "").strip()
    if inf and inf.endswith(":8000"):
        bad.append("INFERENCE_INTERNAL_URL(:8001 이어야 함)")
    if bad:
        return WARN, f"{' '.join(bad)} 비었음 - [2]"
    return OK, "키 4종"


def check_index() -> tuple[str, str]:
    """벡터 인덱스. **없으면 검색이 0건이고 시스템이 아무것도 못 한다.**"""
    d = ROOT / ".chroma"
    if not d.exists():
        return BAD, "없음 - [3]"
    n = sum(1 for _ in d.rglob("*") if _.is_file())
    if n < 3:
        return WARN, "비어 있음 - [3]"
    return OK, "있음"


def check_db() -> tuple[str, str]:
    """시연용 SQLite. 0바이트면 `initdb` 를 아직 안 돌린 것이다.

    ⚠️ **이 검사는 3차(SQLAlchemy) DB 만 본다.** 4차의 계정·펫·다이어리는
    `DJANGO_DATABASE_URL` 쪽에 쌓인다 (D-104 로 스키마 소유자는 Django 다).
    `check_django_db()` 가 그쪽을 본다.
    """
    try:
        from dotenv import dotenv_values

        url = (dotenv_values(str(ROOT / ".env")).get("DATABASE_URL") or "").strip()
    except Exception:
        url = ""
    if url and not url.startswith("sqlite"):
        return OK, "외부 DB"
    f = ROOT / "pettriage.sqlite3"
    if not f.exists() or f.stat().st_size == 0:
        # 🔴 **4차에서는 없는 것이 정상일 수 있다.** 계정·펫·다이어리는 Django 쪽
        #    (`웹앱DB`)으로 옮겨 갔다 (D-104). 이 DB 는 아직 폐기되지 않은 FastAPI
        #    라우터(auth·users·pets·records)만 쓰고, 그 라우터들은 7b 에서 사라진다.
        #    그러니 "없음"을 문제처럼 보이게 하지 않는다 — 3차 경로를 쓸 때만 필요하다.
        return WARN, "없음 (3차 경로용 · 4차는 웹앱DB)"
    return OK, f"{f.stat().st_size // 1024}KB"


def check_django_db() -> tuple[str, str]:
    """Django 쪽 DB 와 **마이그레이션이 돌았는가.**

    🔴 마이그레이션이 안 돌면 웹앱은 뜨지만 **로그인·펫 등록이 전부 실패한다.**
    파일 유무만 보면 그 상태를 초록으로 보고하게 된다.
    """
    try:
        from dotenv import dotenv_values

        url = (dotenv_values(str(ROOT / ".env")).get("DJANGO_DATABASE_URL") or "").strip()
    except Exception:
        url = ""
    if url and not url.startswith("sqlite"):
        return WARN, "외부 DB - 직접 확인"
    f = ROOT / "webapp.sqlite3"
    if not f.exists() or f.stat().st_size == 0:
        return BAD, "migrate 안 함"
    try:
        import sqlite3

        with sqlite3.connect(str(f)) as con:
            names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    except Exception:
        return WARN, "읽을 수 없음"
    # `pets`·`diary_entries` 가 없으면 마이그레이션이 끝까지 안 돈 것이다 (D-104 완료 판정).
    if not {"pets", "diary_entries"} <= names:
        return BAD, "pets/diary 마이그레이션 안 됨"
    return OK, f"{len(names)}개 표"


def status_line() -> str:
    parts = []
    for label, fn in (
        ("venv", check_venv),
        ("패키지", check_packages),
        (".env", check_env),
        ("인덱스", check_index),
        ("DB", check_db),
        ("웹앱DB", check_django_db),
        ("docker", check_docker),
    ):
        mark, note = fn()
        parts.append(f"{label} {mark}" + (f"({note})" if mark != OK else ""))
    return "  ".join(parts)


def blocking(step: str) -> str | None:
    """이 항목을 누르기 전에 먼저 해야 할 것. 없으면 None."""
    needs = {
        "2": [], "3": ["pkg"], "4": ["pkg"], "5": ["pkg", "env", "idx", "web"],
        "6": ["pkg", "env", "idx"], "7": ["pkg"], "8": ["pkg", "env"], "9": ["pkg", "env", "idx"],
    }.get(step, [])
    if "pkg" in needs and check_packages()[0] == BAD:
        return "패키지가 없습니다. 먼저 [1] 처음 설치."
    if "env" in needs and check_env()[0] == BAD:
        return ".env 가 없습니다. 먼저 [2] .env 설정."
    if "idx" in needs and check_index()[0] == BAD:
        return "벡터 인덱스가 없습니다. 먼저 [3] 벡터 인덱스 만들기."
    # 🔴 마이그레이션이 안 되면 화면은 뜨는데 **로그인·펫 등록이 전부 실패한다.**
    #    띄우고 나서 알면 늦다 — 누르기 전에 막는다 (D-104 완료 판정).
    if "web" in needs and check_django_db()[0] == BAD:
        return "웹앱 DB 가 준비되지 않았습니다. 먼저:  python manage.py migrate"
    return None
