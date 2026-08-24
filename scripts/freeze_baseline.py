#!/usr/bin/env python3
"""0단계 · 전환 전 기준선 고정 — 골든셋을 N판 돌리고 **소음대까지 함께** 박는다.

    python scripts/freeze_baseline.py               # 2판 (권장)
    python scripts/freeze_baseline.py --runs 3      # 3차와 같은 3판
    python scripts/freeze_baseline.py --check       # 돌리지 않고 사전 점검만

## 왜 스크립트인가 — 숫자 하나로는 8단계가 성립하지 않는다

    D-102 는 전환의 성공 기준을 **"판정 결과가 같다"** 로 정했다. 그런데
    `temperature=0` 이어도 `seed` 를 주지 않으므로 **같은 코드로 두 번 돌려도 결과가
    흔들린다** (`scripts/diff_reports.py` 머리말). 3차는 기준선 3판으로 그 폭을
    **±1건(±1.7pp)** 으로 재 두었고, 그 덕분에 D-86 을 개선으로, D-87 을 회귀로
    판정할 수 있었다.

    기준선을 한 판만 박아 두면 8단계에서 나온 차이가 **전환 탓인지 소음인지 못 가른다.**
    그래서 기준선은 *숫자* 가 아니라 **숫자 + 소음대**다. 그리고 그 둘을 사람이 손으로
    맞추면 빠뜨린다 (D-69 — 설정과 절차는 코드가 읽는다).

## 무엇을 하나

    ① 사전 점검 — 커밋 안 된 변경 · 태그 중복 · 골든셋 · 인덱스 · 키 · 프로파일
    ② N판 실행 — `--arm A` · **게이트 인자를 주지 않는다** (기준선은 판정이 아니라 기록이다)
    ③ 판을 케이스 단위로 겹쳐 **흔들린 건**을 뽑고 소음대를 낸다
    ④ 1판을 `eval/reports/baseline_before.json` 으로 굳히고 `.md` 에 요약을 쓴다
    ⑤ 태그 명령은 **안내만** 한다 — git 은 PowerShell 에서 돈다 (14 §7)

⚠️ **돌기 전에 아무것도 고치지 않는다.** `dirty=True` 인 리포트는 재현할 수 없고,
   재현할 수 없는 기준선은 8단계에서 비교 대상이 되지 못한다. 이 스크립트가
   더러운 작업 트리에서 멈추는 이유가 그것이다.

⚠️ **판이 도는 동안에는 읽기만 한다.** 3차에서 골든셋 수정이 측정 중에 디스크에 닿아
   세 판이 옛 파일을 본 사고가 두 번 났다.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "eval" / "reports"
GOLDEN_DIR = ROOT / "eval" / "goldenset"

#: 8단계(회귀 확인)가 이 이름을 찾는다. 14 §5 · D-102.
TAG = "freeze-django-before"
FINAL_JSON = REPORT_DIR / "baseline_before.json"
FINAL_MD = REPORT_DIR / "baseline_before.md"


def git(*args: str) -> str:
    """읽기 전용 git 호출.

    · `--no-optional-locks` — **`git status` 는 인덱스를 갱신하려고 `.git/index.lock` 을
      잡는다.** 파일 삭제가 막힌 환경(리눅스 VM 마운트 등)에서 이 자물쇠가 남으면
      그 뒤의 모든 커밋이 *"Another git process seems to be running"* 으로 막힌다
      (2026-08-24 실제 발생). 이 스크립트는 읽기만 하므로 자물쇠가 필요 없다.
    · `core.quotepath=false` — 한글 파일명이 8진 이스케이프로 나오지 않게 한다.
    · `encoding` — 윈도우 기본은 cp949 라 한글 경로·커밋메시지에서 깨진다.
    """
    try:
        out = subprocess.run(
            ["git", "--no-optional-locks", "-c", "core.quotepath=false", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return ""
    return out.stdout.strip()


# ─────────────────────────────────────────────────────────────
# ① 사전 점검 — 여기서 막는 것이 6분짜리 판을 버리는 것보다 싸다
# ─────────────────────────────────────────────────────────────
def preflight(allow_dirty: bool, force: bool) -> list[str]:
    """막을 것(치명)과 알릴 것(경고)을 나눠 돌려준다. 치명이 하나라도 있으면 돌지 않는다."""
    fatal: list[str] = []
    warn: list[str] = []

    dirty = git("status", "--porcelain")
    if dirty:
        n = len(dirty.splitlines())
        msg = f"커밋되지 않은 변경 {n}건 — 이 위에서 잰 숫자는 재현할 수 없다 (04 §8)"
        (warn if allow_dirty else fatal).append(msg)
        for line in dirty.splitlines()[:10]:
            warn.append(f"    {line}")

    if TAG in git("tag").splitlines():
        msg = f"태그 `{TAG}` 가 이미 있다 — 기준선은 이미 박혔다. 다시 박으면 8단계의 기준이 움직인다"
        (warn if force else fatal).append(msg)

    goldens = sorted(GOLDEN_DIR.glob("golden_*.csv"))
    if not goldens:
        fatal.append(f"골든셋이 없다 — {GOLDEN_DIR}")
    else:
        rows = 0
        for p in goldens:
            with p.open(encoding="utf-8-sig", newline="") as f:
                rows += max(0, sum(1 for _ in f) - 1)
        print(f"  · 골든셋 {rows}건 ({', '.join(p.name for p in goldens)})")
        if rows < 10:
            fatal.append(f"골든셋이 {rows}건뿐이다 — 분모가 작으면 비율이 무의미하다")

    store = Path(os.environ.get("VECTORSTORE_DIR") or (ROOT / ".chroma"))
    if not store.is_absolute():
        store = ROOT / store
    if not store.exists():
        fatal.append(f"벡터 인덱스가 없다 ({store}) — `make index` 를 먼저 돌린다 (D-44)")

    env_text = ""
    env_file = ROOT / ".env"
    if env_file.exists():
        env_text = env_file.read_text(encoding="utf-8", errors="replace")
    has_key = bool(os.environ.get("OPENAI_API_KEY")) or any(
        line.startswith("OPENAI_API_KEY=") and line.split("=", 1)[1].strip()
        for line in env_text.splitlines()
    )
    if not has_key:
        fatal.append("OPENAI_API_KEY 가 비어 있다 — arm A 는 5태스크가 전부 폴백으로 돈다")

    # 🔴 셸에 빈 값이 남아 있으면 `.env` 값이 가려진다 (.env.example 함정 셋).
    if "OPENAI_API_KEY" in os.environ and not os.environ["OPENAI_API_KEY"].strip():
        fatal.append("셸의 OPENAI_API_KEY 가 빈 문자열이다 — `Remove-Item Env:OPENAI_API_KEY`")

    leftover = [k for k in os.environ if k.startswith("PETTRIAGE__MODEL__")]
    if leftover:
        warn.append(f"셸에 남은 모델 설정 {leftover} — `--arm` 이 비우고 세운다 (arms.py)")

    return fatal + [f"\x00{w}" for w in warn]


# ─────────────────────────────────────────────────────────────
# ② 실행
# ─────────────────────────────────────────────────────────────
def run_one(idx: int, arm: str, out: Path) -> tuple[int, float]:
    """한 판. **게이트 인자를 주지 않는다** — 기준선은 판정이 아니라 기록이다.

    다만 `run_eval.py` 는 중대 과소평가·등급 미판정 게이트를 인자와 무관하게 돌린다.
    그 빨간불은 **기록하되 중단시키지 않는다.** JSON 은 게이트보다 먼저 쓰인다.
    """
    env = dict(os.environ)
    # 🔴 셸에서 세우지 않으면 engine 이 stub 이다. 여기서 못박는다 (.env 로는 안 먹는다).
    env["PETTRIAGE_PROFILE"] = "eval"
    env.setdefault("PYTHONIOENCODING", "utf-8")

    cmd = [
        sys.executable,
        str(ROOT / "eval" / "harness" / "run_eval.py"),
        "--arm",
        arm,
        "--json",
        str(out),
    ]
    print(f"\n━━ {idx}판 · arm {arm} → {out.name} ━━")
    t0 = time.monotonic()
    rc = subprocess.run(cmd, cwd=ROOT, env=env, check=False).returncode
    return rc, time.monotonic() - t0


# ─────────────────────────────────────────────────────────────
# ③ 겹쳐 보기 — 총계가 같아도 케이스가 갈릴 수 있다 (diff_reports 머리말)
# ─────────────────────────────────────────────────────────────
def overlay(reports: list[dict]) -> dict:
    """판을 케이스 단위로 겹친다. **흔들린 건의 목록**이 소음대의 실체다."""
    ids = [c["case_id"] for c in reports[0]["cases"]]
    flipped: list[dict] = []
    for cid in ids:
        rows = []
        for rep in reports:
            hit = next((c for c in rep["cases"] if c["case_id"] == cid), None)
            if hit is not None:
                rows.append(hit)
        if len(rows) < len(reports):
            continue
        moved = {
            key: [r.get(key) for r in rows]
            for key in ("passed", "actual_status", "actual_level", "llm_level")
            if len({json.dumps(r.get(key), ensure_ascii=False) for r in rows}) > 1
        }
        if moved:
            flipped.append({"case_id": cid, **moved})

    passes = [sum(1 for c in rep["cases"] if c["passed"]) for rep in reports]
    n = reports[0]["n"]
    return {
        "n": n,
        "passes": passes,
        "pass_rates": [p / n for p in passes] if n else [],
        "band_cases": max(passes) - min(passes) if passes else 0,
        "band_pp": (max(passes) - min(passes)) / n * 100 if n else 0.0,
        "flipped": flipped,
        "pass_flipped": [f["case_id"] for f in flipped if "passed" in f],
    }


def summary_md(reports: list[dict], ov: dict, arm: str, elapsed: list[float]) -> str:
    p = reports[0]["provenance"]
    lines = [
        "# 전환 전 기준선 — 골든셋 " + str(ov["n"]) + "건",
        "",
        "> **SKN 4차 단위 프로젝트** · 0단계 (14 §5 · D-102)",
        "> `scripts/freeze_baseline.py` 가 만든다. **손으로 고치지 않는다.**",
        "",
        "이 숫자는 성능 주장이 아니라 **비교 기준점**이다. 8단계(회귀 확인)는",
        "전환 후 수치를 여기와 맞대고, **소음대 안이면 같다고 읽는다.**",
        "",
        "## 1. 무엇을 잰 것인가",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| 커밋 | `{p.get('repo_commit', '?')[:12]}` |",
        f"| 커밋 안 된 변경 | {'🔴 있음 — 재현 불가' if p.get('dirty') else '없음'} |",
        f"| 비교군 | `--arm {arm}` |",
        f"| 엔진 · 모델 | {reports[0]['engine']} · {reports[0]['model']} |",
        f"| 임베딩 | {p.get('embedding_model')} · top_k {p.get('top_k')} |",
        f"| 프로파일 | {p.get('profile')} · max_clarify_turns {p.get('max_clarify_turns')} |",
        f"| 판 수 | {len(reports)}판 ({', '.join(f'{e / 60:.1f}분' for e in elapsed)}) |",
        "",
        "## 2. 소음대 — 같은 코드로 몇 건이 흔들리나",
        "",
        "| 판 | 통과 | 통과율 |",
        "|---|---|---|",
    ]
    for i, (cnt, rate) in enumerate(zip(ov["passes"], ov["pass_rates"], strict=False), 1):
        lines.append(f"| {i} | {cnt}/{ov['n']} | {rate * 100:.1f}% |")
    lines += [
        "",
        f"**소음대 ±{ov['band_cases']}건 (±{ov['band_pp']:.1f}pp)** — "
        f"통과가 갈린 건 {len(ov['pass_flipped'])}건"
        + (f" ({', '.join(ov['pass_flipped'])})" if ov["pass_flipped"] else ""),
        "",
        "> 🔴 **전환 후 차이가 이 폭 안이면 \"달라졌다\"고 말하지 않는다.**",
        "> 밖이면 `scripts/diff_reports.py` 로 어느 건이 어디로 갔는지 먼저 본다 —",
        "> 총계만 보면 방향을 못 읽는다 (틀리던 건이 거절로 빠져도 일치도는 오른다).",
        "",
        "## 3. 판 사이에서 움직인 케이스",
        "",
    ]
    if not ov["flipped"]:
        lines.append("없다. 판이 완전히 일치했다.")
    else:
        lines.append("| case_id | 무엇이 | 판별 값 |")
        lines.append("|---|---|---|")
        for f in ov["flipped"]:
            for key, vals in f.items():
                if key == "case_id":
                    continue
                shown = " → ".join("―" if v is None else str(v) for v in vals)
                lines.append(f"| {f['case_id']} | {key} | {shown} |")
        lines += [
            "",
            "**`llm_level` 만 갈리고 `passed` 는 안 갈린 건**은 결함이 아니라 증거다 —",
            "규칙 바닥과 게이트가 LLM 의 흔들림을 흡수했다는 뜻이다 (D-09 · 04b).",
        ]
    lines += [
        "",
        "## 4. 8단계에서 할 일",
        "",
        "```powershell",
        "python eval/harness/run_eval.py --arm " + arm + " --json eval/reports/baseline_after.json",
        "python scripts/diff_reports.py eval/reports/baseline_before.json "
        "eval/reports/baseline_after.json",
        "```",
        "",
        f"판정: 통과 건수 차이가 **{ov['band_cases']}건 이하**면 동일로 읽는다. "
        "그보다 크면 뒤집힌 케이스를 전수로 설명한 뒤에 병합한다 (D-102).",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="0단계 · 전환 전 기준선 고정 (14 §5 · D-102)")
    ap.add_argument("--runs", type=int, default=2, help="판 수 (기본 2). 소음대를 내려면 2 이상")
    ap.add_argument("--arm", default="A", choices=["none", "A", "A-LC", "C", "D"], help="비교군")
    ap.add_argument("--check", action="store_true", help="사전 점검만 하고 끝낸다")
    ap.add_argument(
        "--allow-dirty",
        action="store_true",
        help="🔴 커밋 안 된 변경 위에서도 돈다. 그 리포트는 재현할 수 없다",
    )
    ap.add_argument("--force", action="store_true", help=f"`{TAG}` 가 이미 있어도 다시 잰다")
    a = ap.parse_args(argv)

    print("━━ 사전 점검 ━━")
    issues = preflight(a.allow_dirty, a.force)
    fatal = [m for m in issues if not m.startswith("\x00")]
    warn = [m[1:] for m in issues if m.startswith("\x00")]
    for w in warn:
        print(f"  ⚠️ {w}")
    for f in fatal:
        print(f"  ✗ {f}")
    if fatal:
        print("\n돌지 않는다. 위를 먼저 처리한다.")
        return 1
    print("  ✓ 준비됨")

    if a.runs < 2:
        print("  ⚠️ 1판만으로는 소음대를 낼 수 없다 — 8단계 판정 기준이 서지 않는다")
    if a.check:
        print("\n(--check) 여기까지.")
        return 0

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    reports: list[dict] = []
    elapsed: list[float] = []
    for i in range(1, a.runs + 1):
        out = REPORT_DIR / f"baseline_before_{i}.json"
        rc, sec = run_one(i, a.arm, out)
        if not out.exists():
            print(f"✗ {i}판이 리포트를 남기지 못했다 (종료코드 {rc}). 중단한다.")
            return 1
        if rc != 0:
            print(f"  ⚠️ {i}판 종료코드 {rc} — 게이트가 빨간불이다. 기록은 남긴다 (기준선이므로)")
        reports.append(json.loads(out.read_text(encoding="utf-8")))
        elapsed.append(sec)
        print(f"  · {sec / 60:.1f}분")

    commits = {r["provenance"].get("repo_commit") for r in reports}
    if len(commits) > 1:
        print("✗ 판 사이에 커밋이 바뀌었다 — 같은 코드를 잰 것이 아니다. 다시 돌린다.")
        return 1

    ov = overlay(reports)
    shutil.copyfile(REPORT_DIR / "baseline_before_1.json", FINAL_JSON)
    FINAL_MD.write_text(summary_md(reports, ov, a.arm, elapsed), encoding="utf-8")

    print("\n━━ 기준선 ━━")
    print(f"  통과 {ov['passes']} / {ov['n']}건")
    print(f"  소음대 ±{ov['band_cases']}건 (±{ov['band_pp']:.1f}pp)")
    if ov["pass_flipped"]:
        print(f"  흔들린 건 {', '.join(ov['pass_flipped'])}")
    print(f"  → {FINAL_JSON.relative_to(ROOT)}")
    print(f"  → {FINAL_MD.relative_to(ROOT)}")
    print(
        "\n다음 (PowerShell 에서 — 14 §7):\n"
        "  git add eval/reports/baseline_before*.json eval/reports/baseline_before.md\n"
        '  git commit -m "test: 전환 전 기준선 고정 — 골든셋 '
        f"{len(reports)}판 · 소음대 ±{ov['band_cases']}건\"\n"
        f"  git tag -a {TAG} -m \"Django 전환 착수 직전 (D-102)\"\n"
        f"  git push origin ohb --follow-tags"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
