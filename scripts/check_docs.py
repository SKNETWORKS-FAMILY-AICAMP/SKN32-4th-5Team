# -*- coding: utf-8 -*-
"""산출물 문서가 **주장하는 값**이 실제와 같은지 대조한다.

    python scripts/check_docs.py            # 파일만 읽는다 (빠르다)
    python scripts/check_docs.py --tests    # pytest 수집까지 세어 본다 (수 초)

**왜 필요한가.** `check_requirements.py` 는 문서 *안*의 참조가 이어지는지만 본다.
문서가 **바깥(코드·설정·리포트)에 대해 하는 말**이 맞는지는 아무도 안 봤고,
2026-08-24 하루에 두 번 틀렸다.

    · 테스트 수 `460` — 실제 589. 게다가 분자는 함수 수, 분모는 출처 불명이라
      비율 `13%` 가 아무것도 뜻하지 않았다
    · Django·FastAPI 포트가 `14 §3.1` 에서 **서로 뒤바뀌어** 있었고, 그래서 §3.4 가
      *"8000(추론)은 차단"* 이라고 적었다 — **공개할 것을 막고 막을 것을 여는** 지시였다

둘 다 사람이 **우연히** 발견했다. 그것을 규율로 바꾼다.

CONTRIBUTING — *"선언과 실제가 어긋나면, 거짓말하는 쪽은 대개 선언이다."*
그래서 이 스크립트는 **실물을 먼저 읽고** 문서를 그것에 비춘다.

종료 코드: 어긋난 것이 하나라도 있으면 1.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

err: list[str] = []
ok: list[str] = []


def _read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _docs_text() -> dict[str, str]:
    """4차 산출물 문서만 본다. archive-3rd 와 팀원 폴더는 대상이 아니다."""
    out = {}
    for name in ("10_요구사항정의서", "11_화면설계서", "12_시스템구성도",
                 "13_테스트계획", "14_전환설계"):
        p = DOCS / f"{name}.md"
        if p.exists():
            out[name] = p.read_text(encoding="utf-8")
    return out


#: 이 표시가 있는 줄은 대조하지 않는다.
#:
#: **과거의 오기를 설명하는 문장**이 있다 — *"옛 §3.1 은 Django 를 :8001 로 적었다"* 같은
#: 줄은 실물에 대한 주장이 아니라 **이력**이다. 기계는 그 차이를 못 읽으므로 사람이 표시한다.
#: 남용하면 검사가 무의미해지니, **왜 제외인지를 표시 뒤에 적는다.**
IGNORE = "대조제외"


def claim(doc: str, text: str, pattern: str, label: str, expected: str) -> None:
    """문서가 `pattern` 으로 말하는 값들이 전부 `expected` 인가."""
    text = "\n".join(ln for ln in text.splitlines() if IGNORE not in ln)
    found = set(re.findall(pattern, text))
    if not found:
        return  # 그 문서가 이 값을 말하지 않는다 — 검사 대상이 아니다
    wrong = {f for f in found if f != expected}
    if wrong:
        err.append(f"{doc}: {label} 을 {sorted(wrong)} 로 적었다 — 실제는 `{expected}`")
    else:
        ok.append(f"{doc}: {label} = {expected}")


# ─────────────────────────────────────────────────────────────
# ① 실물을 먼저 읽는다
# ─────────────────────────────────────────────────────────────
def real_ports() -> tuple[str, str]:
    """nginx 의 upstream 이 원본이다 — 라우팅을 실제로 하는 것이 그것이다."""
    conf = _read("docker/nginx/nginx.conf")
    dj = re.search(r"upstream\s+django\s*\{[^}]*:(\d+)", conf)
    fa = re.search(r"upstream\s+fastapi\s*\{[^}]*:(\d+)", conf)
    return (dj.group(1) if dj else ""), (fa.group(1) if fa else "")


def real_config() -> dict[str, str]:
    """`configs/default.yaml` — PyYAML 을 쓰지 않는다. 이 스크립트는 의존성이 없어야 한다."""
    y = _read("configs/default.yaml")
    out = {}
    for key in ("top_k", "score_threshold", "embedding_model"):
        m = re.search(rf"^\s*{key}\s*:\s*([^\s#]+)", y, re.M)
        if m:
            out[key] = m.group(1).strip().rstrip("0").rstrip(".") if key == "score_threshold" else m.group(1)
    return out


def real_baseline() -> dict[str, str]:
    import json

    p = ROOT / "eval" / "reports" / "baseline_before.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text(encoding="utf-8"))
    lat = d.get("latency", {})
    out = {}
    if "answered_p95_ms" in lat:
        out["answered_p95"] = f"{lat['answered_p95_ms'] / 1000:.1f}"
    if "answered_p50_ms" in lat:
        out["answered_p50"] = f"{lat['answered_p50_ms'] / 1000:.1f}"
    if "n" in d:
        out["n"] = str(d["n"])
    return out


def real_clarify_turns() -> str:
    m = re.search(r"^MAX_CLARIFY_TURNS\s*=\s*(\d+)", _read("src/pettriage/app/contracts.py"), re.M)
    return m.group(1) if m else ""


def real_test_count() -> str:
    """`pytest` 수집 수. `-qq` 가 합계 줄을 지우므로 **파일별 수를 더한다.**"""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    m = re.search(r"(\d+)\s*/?\d*\s*tests? collected", r.stdout)
    if m:
        return m.group(1)
    total = sum(int(x) for x in re.findall(r"^\S+\.py:\s*(\d+)$", r.stdout, re.M))
    return str(total) if total else ""


# ─────────────────────────────────────────────────────────────
# ② 문서를 그것에 비춘다
# ─────────────────────────────────────────────────────────────
def main() -> int:
    docs = _docs_text()
    if not docs:
        print("✗ docs/10~14 를 하나도 못 읽었다")
        return 1

    print("━━ 문서 ↔ 실물 대조 ━━")

    dj, fa = real_ports()
    if not dj or not fa:
        err.append("nginx.conf 에서 upstream 포트를 못 읽었다 — 이 검사 전체가 무의미해진다")
    else:
        print(f"  · 실물 포트 — Django {dj} · FastAPI {fa} (docker/nginx/nginx.conf)")
        if dj == fa:
            err.append(f"nginx 의 두 upstream 이 같은 포트({dj})다")
        # 🔴 여기가 실제로 틀렸던 자리다
        for name, text in docs.items():
            claim(name, text, r"Django[^\n|]{0,20}?[`:*\s]{1,4}(80\d\d)", "Django 포트", dj)
            claim(name, text, r"(?:FastAPI|추론)[^\n|]{0,24}?[`:*\s]{1,4}(80\d\d)", "추론 포트", fa)
        # settings.py 의 기본값이 추론 포트를 가리키는가
        m = re.search(r'INFERENCE_INTERNAL_URL\s*=\s*os\.environ\.get\([^)]*?:(\d+)', _read("webapp/settings.py"))
        if m and m.group(1) != fa:
            err.append(f"webapp/settings.py 의 INFERENCE_INTERNAL_URL 기본값이 :{m.group(1)} — 추론은 :{fa} 다")
        elif m:
            ok.append(f"settings.py: INFERENCE_INTERNAL_URL → :{fa}")

    cfg = real_config()
    if cfg:
        print(f"  · 실물 설정 — top_k {cfg.get('top_k')} · 임계 {cfg.get('score_threshold')} · {cfg.get('embedding_model')}")
        for name, text in docs.items():
            if "top_k" in cfg:
                claim(name, text, r"top[_ ]?k\D{0,12}?\*{0,2}(\d+)", "top_k", cfg["top_k"])
            if "embedding_model" in cfg:
                claim(name, text, r"(BAAI/[\w\-.]+)", "임베딩 모델", cfg["embedding_model"])

    turns = real_clarify_turns()
    if turns:
        print(f"  · 되묻기 상한 — {turns} (contracts.py)")
        for name, text in docs.items():
            claim(name, text, r"MAX_CLARIFY_TURNS`?\D{0,6}?\((\d+)\)", "되묻기 상한", turns)

    base = real_baseline()
    if base:
        print(f"  · 기준선 — 골든셋 {base.get('n')}건 · answered p95 {base.get('answered_p95')}s")
        for name, text in docs.items():
            if "answered_p95" in base:
                claim(name, text, r"p95[^\n|]{0,12}?\*{0,2}(\d+\.\d)s", "p95 지연", base["answered_p95"])
    else:
        print("  · 기준선 리포트 없음 — 지연·건수 대조를 건너뛴다")

    # 문서가 가리키는 파일이 실재하는가
    missing = set()
    for name, text in docs.items():
        body = "\n".join(ln for ln in text.splitlines() if IGNORE not in ln)
        for path in re.findall(r"`((?:src|templates|chat|pets|diary|accounts|webapp|docker|configs|eval|scripts)/[\w./\-]+\.\w+)`", body):
            if not (ROOT / path).exists():
                missing.add(f"{name}: `{path}` 가 없다")
    err.extend(sorted(missing))

    if "--tests" in sys.argv:
        n = real_test_count()
        if n:
            print(f"  · pytest 수집 — {n}건")
            for name, text in docs.items():
                claim(name, text, r"\*{0,2}(\d{3})\*{0,2}\s*(?:passed|건)?\s*(?:passed)?", "", n) if False else None
            # 수는 자리가 많아 오탐이 크다. `13 §2` 의 표만 본다.
            t13 = docs.get("13_테스트계획", "")
            m = re.search(r"\|\s*수집·실행\s*\|\s*\*{0,2}(\d+)", t13)
            if m and m.group(1) != n:
                err.append(f"13_테스트계획: 수집·실행을 {m.group(1)} 로 적었다 — 실제는 {n}")
            elif m:
                ok.append(f"13_테스트계획: 수집·실행 = {n}")
        else:
            print("  · pytest 수집 실패 — 이 검사만 건너뛴다")

    print()
    for o in ok:
        print(f"  ✓ {o}")
    for e in err:
        print(f"  ✗ {e}")
    if err:
        print(f"\n어긋남 {len(err)}건. **실물을 먼저 읽고** 어느 쪽을 고칠지 정한다 (CONTRIBUTING).")
        return 1
    print("\n  ✓ 문서가 하는 말이 실물과 같다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
