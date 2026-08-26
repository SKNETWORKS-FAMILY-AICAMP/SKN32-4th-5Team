"""표기 교정을 **실제 어휘**에 붙여 효과와 부작용을 함께 잰다.

    .venv\\Scripts\\python scripts\\check_spelling.py

무엇을 판정하는가
----------------
    ✓ 살린다   교정 전 '없음' 이던 것이 어휘로 이어진다
    ✗ 오탐     교정하면 안 되는 것이 교정된다   ← **하나라도 있으면 실패다**
    · 한계     못 살린다 (거리 2 이상) — 실패가 아니라 별칭 표의 몫이다

오탐이 왜 실패인가 — 교정은 추정이고, 추정이 **안전 판정**으로 이어지면 보호자는
급여한 뒤에야 틀렸음을 안다. 못 잡는 것은 "모르겠어요" 로 끝나지만 잘못 잡는 것은
끝나지 않는다. 그래서 정탐 0건보다 오탐 1건이 나쁘다.
"""

from __future__ import annotations

import sys

from pettriage.compute.spelling import correct
from pettriage.compute.vocabulary import known_substances, resolve_substance

#: 살아나야 하는 것 — 표기 흔들림
SHOULD_CORRECT = ["초콜렛", "초코릿", "고구가", "마카다미어", "자일리툴"]

#: 교정되면 안 되는 것 — 오탐 함정
SHOULD_NOT_CORRECT = [
    "포토",  # →포도  · 2글자
    "사고",  # →사과  · 2글자
    "양말",  # →양파  · 2글자
    "테이블",  # →케이블 · 첫 글자
    "하나나",  # →바나나 · 첫 글자
    "개밥하",  # →개박하 · 첫 글자
    "산책했어요",
    "밥그릇",
    "병원",
    "간식",
]


def main() -> int:
    vocabulary = list(known_substances())
    print(f"어휘 {len(vocabulary)}종 로드\n")

    print("=" * 58)
    print("① 교정으로 살아나야 하는 것")
    print("=" * 58)
    revived = 0
    for term in SHOULD_CORRECT:
        before = resolve_substance(term)
        if before.name is not None:
            print(f"  ·  {term:10} 이미 잡힘 (how={before.how}) — 교정 불필요")
            continue
        fixed = correct(term, vocabulary)
        if fixed is None:
            print(f"  ·  {term:10} 못 살림 — 거리 2 이상. 별칭 표의 몫")
        else:
            revived += 1
            print(f"  ✓  {term:10} → {fixed.name}  (거리 {fixed.distance})")

    print()
    print("=" * 58)
    print("② 교정되면 안 되는 것")
    print("=" * 58)
    false_positives = []
    for term in SHOULD_NOT_CORRECT:
        before = resolve_substance(term)
        if before.name is not None:
            print(f"  ·  {term:10} 교정 전부터 잡힘 (how={before.how}) — 검사 대상 아님")
            continue
        fixed = correct(term, vocabulary)
        if fixed is None:
            print(f"  ✓  {term:10} 교정 안 함")
        else:
            false_positives.append((term, fixed.name))
            print(f"  ✗  {term:10} → {fixed.name}  ← 오탐")

    print()
    print("=" * 58)
    print(f"살린 것 {revived}건 / 오탐 {len(false_positives)}건")
    if false_positives:
        print()
        print("오탐이 있다. 규칙을 조이기 전에는 붙이면 안 된다:")
        for surface, name in false_positives:
            print(f"  {surface} → {name}")
        return 1
    print("오탐 없음.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
