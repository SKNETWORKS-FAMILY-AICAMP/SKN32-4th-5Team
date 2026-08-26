# -*- coding: utf-8 -*-
"""메뉴 항목이 실제로 하는 일.

**공통 원칙 둘.**

  ① 환경변수를 사람이 외우게 하지 않는다.
     `PETTRIAGE_PROFILE=eval` 을 잊으면 `default.yaml` 의 `serve.engine: stub` 이
     답한다 — 겉보기에 잘 도는데 실제로는 아무것도 안 하는 상태다. 여기서 세운다.

  ② 실패를 삼키지 않는다.
     종료 코드를 그대로 보여 준다. 조용히 넘어가면 다음 단계에서 이유 모를 오류가 난다.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

from checks import ROOT, venv_python

#: 🔴 `django` 를 빠뜨리면 `python manage.py runserver` 가 `ModuleNotFoundError` 로 죽는다.
#:    2026-08-26 실제로 그랬다 — 팀원이 `django` extra 를 만들기 전에 설치한 환경에는
#:    Django 가 없는데, 런처는 아무 말도 하지 않았다.
#:    **extra 를 새로 만들면 이 줄을 함께 고친다.**
PKG_EXTRAS = ".[api,rag,ingest,db,dev,django]"


def _run(args: list[str], *, env_extra: dict[str, str] | None = None, cwd: Path = ROOT) -> int:
    env = {**os.environ, **(env_extra or {})}
    print(f"\n  $ {' '.join(str(a) for a in args)}\n")
    try:
        return subprocess.call([str(a) for a in args], cwd=str(cwd), env=env)
    except KeyboardInterrupt:
        print("\n  (중단됨)")
        return 130
    except FileNotFoundError as e:
        print(f"  실행 파일을 찾지 못했습니다: {e}")
        return 127


def _py() -> str:
    """가상환경 파이썬. 없으면 지금 돌고 있는 것."""
    v = venv_python()
    return str(v) if v.exists() else sys.executable


def _eval_env() -> dict[str, str]:
    """평가·시연 프로필. **이걸 잊으면 stub 이 답한다.**"""
    return {"PETTRIAGE_PROFILE": "eval", "PYTHONUTF8": "1"}


# ── 1 처음 설치 ──────────────────────────────────────────────


def install() -> int:
    if not venv_python().exists():
        print("  가상환경을 만듭니다 (.venv)")
        rc = _run([sys.executable, "-m", "venv", ".venv"])
        if rc != 0:
            return rc
    print("  패키지를 설치합니다. 5~10분 걸립니다.")
    print("  [db] 를 포함합니다 - 없으면 인증 테스트가 모듈째 건너뛰어집니다.")
    print("  [django] 를 포함합니다 - 없으면 웹앱(manage.py)이 아예 안 뜹니다.")
    return _run([_py(), "-m", "pip", "install", "-e", PKG_EXTRAS, "-c", "constraints.txt"])


# ── 2 .env ───────────────────────────────────────────────────


def setup_env() -> int:
    return _run([_py(), "scripts/setup_env.py"])


# ── 3 벡터 인덱스 ────────────────────────────────────────────


def build_index() -> int:
    chroma = ROOT / ".chroma"
    if chroma.exists() and sum(1 for _ in chroma.rglob("*") if _.is_file()) > 3:
        print("  인덱스가 이미 있습니다.")
        if input("  다시 만들까요? [y/N] ").strip().lower() != "y":
            return 0
    print("  처음이면 임베딩 모델(BAAI/bge-m3)을 내려받습니다 - 4~9GB, 10~30분.")
    print("  네트워크와 디스크를 확보하고 시작하세요.")
    if input("  계속할까요? [Y/n] ").strip().lower() == "n":
        return 0
    return _run([_py(), "scripts/build_index.py", "--store", "chroma"], env_extra=_eval_env())


# ── 4 환경 점검 ──────────────────────────────────────────────


def doctor() -> int:
    return _run([_py(), "scripts/doctor.py"], env_extra=_eval_env())


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def _wait_until_up(host: str, port: int, proc: subprocess.Popen, timeout: int = 300) -> bool:
    """포트가 열릴 때까지 기다린다. **프로세스가 죽으면 즉시 그만둔다.**"""
    t0 = time.time()
    dots = 0
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return False
        if _port_open(host, port, 0.4):
            return True
        time.sleep(0.6)
        dots += 1
        if dots % 10 == 0:
            print(f"  … 기다리는 중 ({int(time.time() - t0)}초)")
    return False


# ── 5 시연 서버 ──────────────────────────────────────────────


def _docker() -> str | None:
    """`checks.find_docker()` 를 그대로 쓴다 — 탐색 경로를 두 벌 두지 않는다 (D-22)."""
    from checks import find_docker

    return find_docker()


def _docker_env(base: dict | None = None) -> dict:
    """docker 가 **자기 형제 실행 파일**을 찾을 수 있게 PATH 에 설치 폴더를 얹는다.

    🔴 `_docker()` 가 PATH 밖에서 `docker.exe` 를 찾아 줘도, **docker 자신은 자격 증명
    헬퍼(`docker-credential-desktop.exe`)를 PATH 에서 찾는다.** 그래서 절대 경로로만
    부르면 이미지 받기가 이렇게 죽는다 (2026-08-26 실제로 겪음) —

        error getting credentials - err: exec: "docker-credential-desktop":
        executable file not found in %PATH%

    **실행 파일을 경로로 찾아 줬으면 그 형제들도 함께 찾아 줘야 한다.**
    절반만 풀면 증상이 엉뚱한 곳(엔진이 꺼졌나?)을 가리킨다.
    """
    env = dict(base if base is not None else os.environ)
    dk = _docker()
    if not dk:
        return env
    bin_dir = str(Path(dk).parent)
    cur = env.get("PATH", "")
    if bin_dir.lower() not in cur.lower():
        env["PATH"] = f"{cur};{bin_dir}" if cur else bin_dir
    return env


def _spawn(cmd: list[str], name: str, port: int, env: dict) -> subprocess.Popen | None:
    """프로세스를 띄우고 **포트가 실제로 열릴 때까지** 기다린다.

    죽으면 즉시 그만둔다 — "떴다고 생각했는데 아니었다"가 가장 비싼 실패다.
    """
    print(f"  · {name} 기동 — :{port}")
    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env)
    if _wait_until_up("127.0.0.1", port, proc, timeout=300):
        return proc
    if proc.poll() is not None:
        print(f"  ✗ {name} 가 시작하지 못했습니다 (종료 코드 {proc.returncode}).")
        print("     위 로그를 읽으세요. [4] 환경 점검이 도움이 됩니다.")
    else:
        print(f"  ✗ {name} 가 5분이 지나도 :{port} 를 열지 않습니다.")
        proc.terminate()
    return None


def _shutdown(procs: list[subprocess.Popen], nginx: bool) -> None:
    for pr in procs:
        pr.terminate()
    for pr in procs:
        try:
            pr.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pr.kill()
    if nginx:
        print("  · nginx 컨테이너를 멈춥니다.")
        dk = _docker()
        if dk:
            subprocess.call([dk, "compose", "stop", "nginx"], cwd=str(ROOT), env=_docker_env())


def demo() -> int:
    """시연 서버.

    🔴 **4차는 프로세스가 셋이다** (docs/12 §2 · §5 · `docs/lgj/01_체크해야될사항들.md` §4).

        Django   :8000   공개 진입점 — 로그인 · 펫 · 다이어리 · 채팅 화면
        FastAPI  :8001   추론 — /api/ask · 내부 요약
        nginx    :80     둘을 한 주소로 합친다 → http://localhost/

    **nginx 가 왜 필요한가** — 채팅 화면의 `/api/ask` 는 페이지와 같은 주소로 나간다.
    Django(:8000)만 띄우면 Django 가 그 경로를 몰라 **404** 다. nginx 가 `/api/` 를
    :8001 로 보내 준다 (`docker/nginx/nginx.conf`).

    포트를 외우는 법 — **번호가 작을수록 바깥이다.** `80 → 8000 → 8001`.
    """
    import checks

    print("\n  ── 어떤 구성으로 띄울까요 ────────────────────")
    print("   1  4차 전체    Django + 추론 + nginx  →  http://localhost/    (권장)")
    print("   2  Django 만   화면만 확인 · 채팅은 안 됨  →  :8000")
    print("   3  추론 만     3차 화면 · 4차 화면은 안 보임  →  :8001")
    print("   0  뒤로")
    shape = input("\n  고르세요: ").strip()
    if shape not in ("1", "2", "3"):
        return 0

    # ── 선행 조건 ──
    if shape in ("1", "2"):
        mark, note = checks.check_django_db()
        if mark == checks.BAD:
            print(f"\n  !! 웹앱 DB — {note}")
            print("     로그인·펫 등록이 전부 실패합니다. 먼저 돌리세요:")
            print("       python manage.py migrate")
            return 1
    docker_exe = _docker() if shape == "1" else None
    if shape == "1" and docker_exe is None:
        # `which` 실패는 **설치 안 됨(또는 PATH 밖)** 이다. 엔진이 꺼진 경우는
        # 아래 `docker compose up` 이 0 이 아닌 코드로 실패한다 — 둘을 섞어 말하면
        # 사용자가 엉뚱한 곳(엔진 켜기)을 뒤진다.
        print("\n  !! docker 를 찾지 못했습니다 — PATH 와 알려진 설치 위치 둘 다 봤습니다.")
        print("     확인:  docker --version")
        print()
        print("     nginx 없이도 할 수 있는 것 —")
        print("       [2] Django 만  →  로그인 · 펫 · 다이어리 화면은 전부 보입니다.")
        print("                        채팅의 /api/ask 만 404 입니다.")
        print("     Docker Desktop 을 깔면 [1] 로 전체가 붙습니다.")
        return 1

    # ── LLM 모드 (추론을 띄울 때만 묻는다) ──
    free = False
    if shape in ("1", "3"):
        print("\n  ── 추론 모드 ────────────────────────────────")
        print("   1  실제 LLM      진짜 답변           !! 질의마다 비용 발생")
        print("   2  무료 (폴백)   화면·흐름 확인용     비용 0 · 답변 품질은 낮다")
        m = input("\n  고르세요: ").strip()
        if m not in ("1", "2"):
            return 0
        free = m == "2"
        if not free:
            # 질의 1건마다 LLM 을 6~7회 부른다 — 5태스크 + 초안 + 판정.
            print("\n  !! 질의 1건마다 LLM 호출 6~7회 — 비용이 나갑니다.")
            print("     시연이 끝나면 Ctrl+C 로 반드시 끄세요.")
            if input("  계속할까요? [y/N] ").strip().lower() != "y":
                return 0

    # ── 포트 선점 확인 ──
    want = {"1": [8000, 8001, 80], "2": [8000], "3": [8001]}[shape]
    busy = [p for p in want if _port_open("127.0.0.1", p, 0.3)]
    if busy:
        print(f"\n  !! 포트 {busy} 가 이미 사용 중입니다.")
        print("     이전 서버가 떠 있을 수 있습니다. 그 창에서 Ctrl+C 로 끄세요.")
        print("     nginx 라면:  docker compose stop nginx")
        return 1

    extra = _eval_env()
    if free:
        # `--arm none` 과 같은 상태 — 그래프는 그대로 돌고 5태스크만 폴백으로 간다.
        # `engine=stub` 으로 내리는 것과 다르다. 그건 파이프라인 자체가 가짜다.
        extra["PETTRIAGE__MODEL__PROVIDER"] = "none"
    env = {**os.environ, **extra}

    print("\n  !! 추론 첫 기동은 임베딩 모델을 읽느라 수십 초 걸립니다.")
    print("     준비되면 브라우저가 열립니다. 끄려면 Ctrl+C.\n")

    procs: list[subprocess.Popen] = []
    nginx_up = False
    try:
        if shape in ("1", "3"):
            pr = _spawn(
                [_py(), "-m", "uvicorn", "pettriage.app.main:app",
                 "--host", "127.0.0.1", "--port", "8001"],
                "FastAPI 추론", 8001, env,
            )
            if pr is None:
                return 1
            procs.append(pr)

        if shape in ("1", "2"):
            # `--noreload` — 자동 재시작은 자식 프로세스를 하나 더 만들어서
            # Ctrl+C 로 부모만 죽으면 포트를 쥔 채 남는다.
            pr = _spawn(
                [_py(), "manage.py", "runserver", "127.0.0.1:8000", "--noreload"],
                "Django", 8000, env,
            )
            if pr is None:
                return 1
            procs.append(pr)

        if shape == "1":
            print("  · nginx 컨테이너 — :80")
            rc = subprocess.call(
                [docker_exe, "compose", "up", "nginx", "-d"],
                cwd=str(ROOT),
                env=_docker_env(env),
            )
            if rc != 0:
                # 여기까지 왔으면 실행 파일도 있고 형제 경로도 얹었다.
                # 남는 원인은 **엔진이 꺼진 것**이거나 이미지를 못 받는 것이다.
                print("  ✗ nginx 를 띄우지 못했습니다. 위 오류를 읽으세요.")
                print("     · Docker Desktop 앱이 켜져 있고 'Engine running' 인가")
                print("     · 이미지를 처음 받는 중이면 네트워크를 확인한다")
                return 1
            nginx_up = True
            t0 = time.time()
            while time.time() - t0 < 30 and not _port_open("127.0.0.1", 80, 0.4):
                time.sleep(0.5)

        url = {"1": "http://localhost/", "2": "http://127.0.0.1:8000/",
               "3": "http://127.0.0.1:8001/"}[shape]
        print(f"\n  준비됐습니다 — {url} 를 엽니다.")
        if shape == "2":
            print("  (nginx 가 없어 채팅의 /api/ask 는 404 입니다 — 화면만 확인하세요.)")
        if shape == "3":
            print("  (3차 화면입니다 — 4차 Django 화면은 여기서 안 보입니다.)")
        print()
        webbrowser.open(url)
        for pr in procs:
            pr.wait()
    except KeyboardInterrupt:
        print("\n  서버를 끕니다.")
    finally:
        _shutdown(procs, nginx_up)
    return 0


# ── 6 평가 ───────────────────────────────────────────────────

ARMS = [
    ("none", "코드·규칙만", "무료 · 1분 미만"),
    ("A", "직접 API", "LLM 60건 · 약 6분 · 비용 발생"),
    ("A-LC", "LangChain", "LLM 60건 · 약 6분 · 비용 발생"),
]


def evaluate() -> int:
    print("\n  ── 비교군 ──────────────────────────────────")
    for i, (arm, desc, cost) in enumerate(ARMS, 1):
        mark = "   " if arm == "none" else "!! "
        print(f"   {i}  {arm:6} {desc:14} {mark}{cost}")
    print("   0  뒤로")
    sel = input("\n  고르세요: ").strip()
    if sel == "0" or not sel.isdigit() or not (1 <= int(sel) <= len(ARMS)):
        return 0
    arm, _, cost = ARMS[int(sel) - 1]
    if arm != "none":
        print(f"\n  !! {cost}")
        if input("  계속할까요? [y/N] ").strip().lower() != "y":
            return 0
    stamp = time.strftime("%Y-%m-%d_%H%M")
    out = f"eval/reports/{stamp}_{arm}.json"
    return _run(
        [_py(), "eval/harness/run_eval.py", "--arm", arm, "--json", out],
        env_extra=_eval_env(),
    )


# ── 7 테스트 ─────────────────────────────────────────────────


def tests() -> int:
    print("  pytest 에 -q 를 붙이지 않습니다 - addopts 와 겹쳐 개수가 안 보입니다.")
    return _run([_py(), "-m", "pytest"])


# ── 8 DB 초기화 ──────────────────────────────────────────────


def reset_db() -> int:
    """🔴 **3차(SQLAlchemy) DB 만 지운다** (2026-08-26 검토).

    D-104 로 `pets`·`diary_entries` 의 소유자는 **Django** 다. 4차에서 만든 계정·펫·
    다이어리는 `DJANGO_DATABASE_URL`(기본 `webapp.sqlite3`) 쪽에 쌓이므로 **여기서 안 지워진다.**

    그쪽을 비우려면 파일을 지우고 다시 마이그레이션한다.

        Remove-Item webapp.sqlite3
        python manage.py migrate

    또한 아래 `pettriage.app.database` 는 **폐기 대상**이다 (14 §2.1 — `init_db.py` 삭제).
    7b 에서 이 함수째 Django 쪽으로 옮긴다.
    """
    print("\n  ⚠️  3차(SQLAlchemy) DB 만 지웁니다. 4차 계정·펫·다이어리는 남습니다.")
    print("      그쪽까지 비우려면:  Remove-Item webapp.sqlite3  →  python manage.py migrate")
    db = ROOT / "pettriage.sqlite3"
    if db.exists():
        print(f"  {db.name} 를 지웁니다 ({db.stat().st_size // 1024}KB)")
        if input("  시연 데이터가 모두 사라집니다. 계속할까요? [y/N] ").strip().lower() != "y":
            return 0
        try:
            db.unlink()
        except OSError as e:
            print(f"  지우지 못했습니다: {e}  (서버가 켜져 있으면 먼저 끄세요)")
            return 1
    return _run([_py(), "-m", "pettriage.app.database"], env_extra=_eval_env())


# ── 9 자유질의 ───────────────────────────────────────────────


def freeform() -> int:
    print("  골든셋 밖 질문 20건을 돌립니다.")
    print("  !! 실제 LLM 을 부릅니다 - 3~5분, 비용 발생.")
    if input("  계속할까요? [y/N] ").strip().lower() != "y":
        return 0
    stamp = time.strftime("%Y-%m-%d_%H%M")
    return _run(
        [_py(), "scripts/probe_freeform.py", "--json", f"eval/reports/자유질의_{stamp}.json"],
        env_extra=_eval_env(),
    )
