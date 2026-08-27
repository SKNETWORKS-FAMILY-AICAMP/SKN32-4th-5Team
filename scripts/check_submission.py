"""제출 묶음이 **지금 문서와 같은가.**

    python scripts/check_submission.py

🔴 **이 검사가 있는 이유** — 2026-08-27 에 `제출_4차/` 를 git 에 올리기로 했다 (D-111).
   저장소로 제출하니 제출물이 저장소에 있어야 한다. 그런데 **PDF 는 diff 가 안 된다.**

   `docs/13` 을 고치고 `make submit-pdf` 를 안 돌리면, 저장소에는 낡은 제출물이
   **조용히** 남는다. `git status` 는 깨끗하고, PR 에는 아무것도 안 뜨고,
   제출한 사람은 최신을 냈다고 믿는다. 이 저장소가 이미 두 번 겪은 모양이다 —
   요구사항 `.xlsx` 두 판본 사이에서 한 줄이 사라진 일, `12 §10` 이 로컬만 보고
   ✅ 를 적어 둔 일. **사본은 원본과 갈라지고, 갈라진 것은 조용하다.**

   그래서 만들 때 원본 `.md` 의 해시를 `제출_4차/MANIFEST.md` 에 적어 두고,
   여기서 지금 원본과 대조한다. 어긋나면 **빨강이다.**

의존성이 없다 — 표준 라이브러리만 쓴다. CI 의 `lint` 잡에서도 돈다.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = ROOT / "제출_4차"
MANIFEST = OUT / "MANIFEST.md"

#: 장부 표의 한 줄. `| `파일` | `원본` | `해시` | 쪽 | 자/쪽 |`
_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|")

#: 스크립트 안에 원본이 있는 표지. 대조할 `.md` 가 없다.
_INLINE = "(스크립트 안)"


def _hash(p: Path) -> str:
    """🔴 **줄바꿈을 지우고 잰다.** `build_submission_pdf.source_hash` 와 같아야 한다.

    `.gitattributes` 가 `* text=auto` 라서, 팀원이 **Windows 에서 새로 clone 하면**
    `.md` 가 CRLF 로 받아진다. 내용은 한 글자도 안 바뀌었는데 바이트가 달라지고,
    날바이트를 쟀으면 **아무 잘못 없는 사람의 CI 가 빨강이 된다.**

    *"내 쪽에서는 아무것도 안 고쳤는데 빨강"* 인 검사는 고쳐지지 않는다 — **지워진다.**
    검사는 자기가 틀릴 수 있는 자리를 먼저 막아야 신뢰를 얻는다.
    """
    text = p.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def main() -> int:
    print("━━ 제출 묶음 대조 ━━")

    if not MANIFEST.exists():
        print(f"  ✗ {MANIFEST.relative_to(ROOT)} 가 없다")
        print("    → Linux 에서: python scripts/build_submission_pdf.py --write")
        return 1

    rows = [
        m.groups()
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if (m := _ROW.match(line))
    ]
    if not rows:
        print(f"  ✗ {MANIFEST.name} 에서 표를 못 읽었다 — 손으로 고쳤는지 본다")
        return 1

    bad: list[str] = []
    for pdf_name, src_name, want in rows:
        pdf = OUT / pdf_name
        mark = "✓"

        if not pdf.exists():
            bad.append(f"{pdf_name} 이 장부에는 있는데 파일이 없다")
            mark = "✗"
        elif src_name == _INLINE:
            mark = "-"  # 표지는 대조할 원본이 없다
        else:
            src = DOCS / src_name
            if not src.exists():
                bad.append(f"{src_name} 가 없다 — 원본이 옮겨졌나")
                mark = "✗"
            elif (got := _hash(src)) != want:
                bad.append(
                    f"{pdf_name} 가 낡았다 — {src_name} 가 바뀌었다 (장부 {want} · 지금 {got})"
                )
                mark = "✗"

        print(f"  {mark} {pdf_name:24} ← {src_name}")

    # 🔴 **장부에 없는 PDF 도 잡는다.** 손으로 넣은 파일이 제출물인 척하는 자리다.
    listed = {r[0] for r in rows}
    for stray in sorted(OUT.glob("*.pdf")):
        if stray.name not in listed:
            bad.append(f"{stray.name} 은 장부에 없다 — 손으로 넣었나")
            print(f"  ✗ {stray.name:24} ← 장부에 없음")

    # PDF 가 아닌 제출물(발표 `.pptx` 등)은 만드는 스크립트가 없어 해시를 못 적는다.
    # **그래도 있다는 사실은 말한다** — 검사가 조용하면 *"전부 봤다"* 로 읽힌다.
    others = [
        f
        for f in sorted(OUT.iterdir())
        if f.is_file() and f.suffix != ".pdf" and f.name != MANIFEST.name
    ]
    if others:
        print("\n  ※ 장부 밖 (낡았는지 이 검사가 알 수 없다 — 손으로 확인한다):")
        for f in others:
            print(f"     {f.name}  {f.stat().st_size // 1024}KB")

    if bad:
        print("\n  🔴 제출 묶음이 지금 문서와 다르다:")
        for b in bad:
            print(f"     {b}")
        print("\n  → Linux 에서 다시 만든다:  make submit-pdf")
        print("    (Windows 에는 pandoc·xelatex 가 없다 — 만들어진 PDF 를 받아 쓴다)")
        return 1

    print(f"\n  ✓ PDF {len(rows)}개가 지금 docs/ 와 같다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
