# -*- coding: utf-8 -*-
"""요구사항 정의서(`docs/10`)의 **정합성**을 검사한다 — 내용이 아니라 참조를 본다.

    python scripts/check_requirements.py

**왜 스크립트인가.** §7 추적표는 §3·§5·§6 과 같은 사실을 두 번 적는 자리다.
사람이 맞추면 반드시 어긋나고(D-69), 어긋난 추적표는 **문서가 거짓말을 하는 것**이라
없느니만 못하다. 7단계에서 테스트 작성자가 이 표를 믿고 일한다.

검사하는 것 — **참조가 이어지는가**

    ✗ (오류)  ID 중복 · 끊긴 참조 · 고아 요구사항 · 추적표에 없는 FR
    ⚠️ (경고)  미작성 유스케이스 · 빈 근거 · 미착수 칸

검사하지 않는 것 — 요구사항이 **옳은가**. 그것은 사람이 검토한다 (10 §9).

종료 코드: 오류 1건 이상이면 1. 경고만이면 0 (미완성 단계에서도 돌아야 하므로).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "10_요구사항정의서.md"

ID_RE = re.compile(r"\b((?:UC|FR|NFR|SC|A|TC)-\d{2})\b")
TODO = "⬜"


def _clean(cell: str) -> str:
    """표 칸에서 강조·코드 표시를 걷어 낸다."""
    return re.sub(r"[*`~]", "", cell).strip()


def _rows(text: str) -> list[tuple[str, list[str]]]:
    """(가장 가까운 제목, 칸 목록) 목록. 구분선과 머리행은 버린다."""
    out: list[tuple[str, list[str]]] = []
    heading = ""
    for line in text.splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            continue
        if not line.lstrip().startswith("|"):
            continue
        cells = [_clean(c) for c in line.strip().strip("|").split("|")]
        if not cells or all(set(c) <= {"-", ":", ""} for c in cells):
            continue
        if cells[0] in {"ID", "FR", "항목", "#"}:
            continue
        out.append((heading, cells))
    return out


def _pick(rows, *keywords):
    """제목에 키워드가 들어간 표들의 행만 고른다."""
    return [c for h, c in rows if any(k in h for k in keywords)]


def _ids(cell: str) -> list[str]:
    return ID_RE.findall(cell)


def main() -> int:
    if not DOC.exists():
        print(f"✗ {DOC.relative_to(ROOT)} 가 없다")
        return 1

    text = DOC.read_text(encoding="utf-8")
    rows = _rows(text)
    err: list[str] = []
    warn: list[str] = []

    def defined(rows_, label):
        """첫 칸의 ID 를 모은다. 중복은 오류다 (§0.1 ⑤ — ID 는 재사용하지 않는다)."""
        seen: dict[str, int] = {}
        for cells in rows_:
            for i in _ids(cells[0]):
                seen[i] = seen.get(i, 0) + 1
        for i, n in seen.items():
            if n > 1:
                err.append(f"{label} {i} 가 {n}번 정의됐다 — ID 는 재사용하지 않는다")
        return set(seen)

    actors = defined(_pick(rows, "이해관계자"), "액터")
    ucs = defined(_pick(rows, "3.2", "목록"), "유스케이스")
    scs = defined(_pick(rows, "화면 목록"), "화면")
    frs = defined(_pick(rows, "기능 요구사항 (FR)"), "FR")
    nfrs = defined(_pick(rows, "비기능"), "NFR")

    # 액터·화면 표에서 UC/SC 가 아닌 것이 섞이지 않게
    ucs = {i for i in ucs if i.startswith("UC-")}
    scs = {i for i in scs if i.startswith("SC-")}
    frs = {i for i in frs if i.startswith("FR-")}
    nfrs = {i for i in nfrs if i.startswith("NFR-")}

    if not frs:
        err.append("FR 을 하나도 못 읽었다 — §5 표 형식이 바뀌었는지 본다")
        print_report(err, warn)
        return 1

    # ── 명세된 유스케이스 (### UC-04 · … 형태의 제목)
    specified = set(re.findall(r"^###\s+(UC-\d{2})", text, re.M))
    for uc in sorted(ucs - specified):
        warn.append(f"{uc} 는 §3.2 에 있으나 §4 에 명세가 없다 — 템플릿으로 채운다")
    for uc in sorted(specified - ucs):
        err.append(f"{uc} 는 §4 에 명세가 있으나 §3.2 목록에 없다 — 끊긴 참조")

    # ── FR 표: UC 참조 · 근거
    for cells in _pick(rows, "기능 요구사항 (FR)"):
        fid = next(iter(_ids(cells[0])), None)
        if not fid:
            continue
        refs = _ids(cells[2]) if len(cells) > 2 else []
        for uc in refs:
            if uc not in ucs:
                err.append(f"{fid} 가 없는 유스케이스 {uc} 를 가리킨다")
        if not refs and TODO not in cells[2]:
            warn.append(f"{fid} 에 유스케이스 참조가 없다")
        if len(cells) > 4 and (not cells[4] or cells[4] == TODO):
            warn.append(f"{fid} 의 근거 칸이 비었다 — 근거 없는 줄은 요구사항이 아니다 (§0.1 ③)")

    # ── NFR: 측정 방법과 실측값
    for cells in _pick(rows, "비기능"):
        nid = next(iter(_ids(cells[0])), None)
        if not nid or not nid.startswith("NFR-"):
            continue
        if len(cells) > 2 and (not cells[2] or cells[2] == TODO):
            err.append(f"{nid} 에 측정 방법이 없다 — 잴 수 없으면 NFR 이 아니다 (§0.1 ②)")
        if len(cells) > 3 and (not cells[3] or cells[3] == TODO):
            warn.append(f"{nid} 의 실측값이 비었다")

    # ── 추적표
    traced: set[str] = set()
    for cells in _pick(rows, "추적표"):
        fid = next(iter(_ids(cells[0])), None)
        if not fid or not fid.startswith("FR-"):
            continue
        if fid in traced:
            err.append(f"추적표에 {fid} 가 두 번 나온다")
        traced.add(fid)
        if fid not in frs:
            err.append(f"추적표의 {fid} 가 §5 에 정의돼 있지 않다 — 끊긴 참조")
        for uc in _ids(cells[1]) if len(cells) > 1 else []:
            if uc not in ucs:
                err.append(f"추적표 {fid} 가 없는 유스케이스 {uc} 를 가리킨다")
        for sc in _ids(cells[2]) if len(cells) > 2 else []:
            if sc.startswith("SC-") and sc not in scs:
                err.append(f"추적표 {fid} 가 없는 화면 {sc} 를 가리킨다")
        if len(cells) > 3 and (not cells[3] or cells[3] == TODO):
            warn.append(f"{fid} 에 대응 테스트가 없다 — 7단계 입력")

    for fid in sorted(frs - traced):
        err.append(f"{fid} 이 추적표에 없다 — 고아 요구사항. 아무도 검증하지 않는다")

    # ── 요약
    print("━━ 요구사항 정의서 정합성 ━━")
    print(f"  액터 {len(actors)} · 유스케이스 {len(ucs)}(명세 {len(specified)}) · 화면 {len(scs)}")
    print(f"  FR {len(frs)} (추적 {len(traced)}) · NFR {len(nfrs)}")
    todo = text.count(TODO)
    if todo:
        print(f"  {TODO} 미착수 표시 {todo}개")
    return print_report(err, warn)


def print_report(err: list[str], warn: list[str]) -> int:
    for w in warn:
        print(f"  ⚠️ {w}")
    for e in err:
        print(f"  ✗ {e}")
    if err:
        print(f"\n오류 {len(err)}건. 참조가 끊겨 있으면 추적표를 믿을 수 없다.")
        return 1
    print("\n  ✓ 참조는 모두 이어져 있다" + (f" (경고 {len(warn)}건)" if warn else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
