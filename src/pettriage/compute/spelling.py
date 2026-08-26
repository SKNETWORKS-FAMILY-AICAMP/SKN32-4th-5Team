"""표기 흔들림 교정 — **별칭 표가 놓치는 이형태를 계산으로 잇는다.**

설계 근거: docs/06_설계결정기록.md · D-59 · D-60  /  aliases.py §④ "표기 변형은 부채다"

이 모듈은 무엇을 하는 곳인가
--------------------------
> **별칭 표가 "손으로 넣은 것만" 잡는 한계를 메운다.**

`aliases.py` 는 `체리씨`·`체리 씨`·`체리씨앗`·`체리 씨앗` 을 각각 한 행으로 넣어
띄어쓰기를 커버한다. 그 방식은 **넣은 것만** 산다. 실측 (2026-08-26) —

    초콜릿  →  resolve_substance: name='초콜릿'  how='직접'   →  /api/ask: answered · level 3
    초콜렛  →  resolve_substance: name=None      how='없음'   →  /api/ask: **refused** (근거없음)

한 글자 차이로 **level 3(CALL_NOW) 물질을 통째로 놓친다.** 별칭 표에 초콜렛이 없고,
부분일치는 글자가 달라 실패하고, 임베딩 검색도 임계 미달로 떨어져 세 층이 모두 뚫린다.

왜 편집거리인가
--------------
표기 변형은 **열린 집합**이다. 초콜렛·쵸콜릿·초코렛… 을 표에 다 넣을 수는 없다.
반면 "한 글자 다르다" 는 **닫힌 규칙**이다. 표를 키우지 않고 이형태를 흡수한다.

**다만 편집거리는 오탐을 만든다.** 제약 없이 거리 1을 허용하면 이렇게 된다 —

    개밥하  →  개박하    (안전 판정)     ← "우리 개 밥하고 산책했어요"
    하나나  →  바나나    (안전 판정)     ← "하나나 알려주세요"
    테이블  →  케이블    (감전 경고)     ← "테이블 위에 둬도 돼?"
    사고    →  사과      (안전 판정)
    포토    →  포도      (위험 판정)

앞의 둘이 특히 나쁘다. **위험한 것을 안전하다고 말하는 오류는 급여 뒤라 회복되지
않는다.** 잘못된 경고는 보호자가 정정하면 끝나지만, 잘못된 "안전해요" 는 끝나지 않는다.
오류 비용이 대칭이 아니므로 **막는 규칙**을 넷 둔다 (§ GUARDS).

무엇을 하지 않는가
----------------
- **판정하지 않는다.** 교정된 이름만 돌려준다. 등급은 기존 경로가 낸다.
- **동점이면 고르지 않는다.** 후보가 둘 이상이면 `None` 을 돌려 판정을 유보한다.
- **기존 파일을 건드리지 않는다.** `vocabulary.resolve_substance` 가 `how='없음'` 을
  낸 **뒤에만** 부르는 후단 보정이다. 별칭 → 부분일치 순서(D-59)는 그대로다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "FIRST_CHAR_MUST_MATCH",
    "MAX_DISTANCE",
    "MAX_LENGTH_DIFF",
    "MIN_NORMALIZED_LEN",
    "Correction",
    "correct",
    "edit_distance",
    "normalize",
]

# ─────────────────────────────────────────────────────────────
# GUARDS — 오탐을 막는 네 규칙
# ─────────────────────────────────────────────────────────────

#: 정규화 후 이 길이 미만인 어휘는 교정 대상에서 뺀다.
#:
#: 2글자에 거리 1을 허용하면 **절반이 달라도 통과한다.** `포도`↔`포토` · `사과`↔`사고` ·
#: `양파`↔`양말` 이 전부 걸린다. 짧은 말은 표기 변형보다 **다른 낱말**일 확률이 높다.
MIN_NORMALIZED_LEN = 3

#: 허용 편집거리. 1 을 넘기지 않는다.
#:
#: 2 로 올리면 `산세비에리아`↔`산세베리아` 같은 것이 잡히지만 오탐이 함께 늘어난다.
#: 그런 것은 별칭 표에 한 행으로 넣는 편이 싸고 안전하다 — 계산은 규칙이 넓어질수록
#: **어디까지 잡히는지 사람이 예측할 수 없게 된다.**
MAX_DISTANCE = 1

#: 첫 글자가 다르면 교정하지 않는다.
#:
#: 한국어 표기 흔들림은 **뒤에서** 일어난다 (초콜`릿`/초콜`렛`, 몬스테`라`/몬스테`리아`).
#: 첫 글자가 다른 것은 대개 다른 낱말이다 — `테이블`↔`케이블`, `하나나`↔`바나나`.
FIRST_CHAR_MUST_MATCH = True

#: 길이 차가 이보다 크면 교정하지 않는다. (거리 1 이면 자동으로 만족하지만 명시한다)
MAX_LENGTH_DIFF = 1

#: 공백과 문장부호. `체리 씨` = `체리씨` 로 만든다.
#:
#: aliases.py §④ 가 "띄어쓰기는 열린 집합이 아니라 정규화다" 라고 적어 둔 그것이다.
#: 표에서 20행 → 10행으로 줄일 수 있는 부채가 여기에 해당한다.
_STRIP = re.compile(r"[\s\-_.,!?~·''\"()\[\]/]+")


def normalize(text: str) -> str:
    """공백·문장부호를 지우고 소문자로 만든다.

    >>> normalize("체리 씨")
    '체리씨'
    >>> normalize("Choco-Late")
    'chocolate'
    """
    return _STRIP.sub("", text).lower()


def edit_distance(a: str, b: str, *, ceiling: int = MAX_DISTANCE) -> int:
    """레벤슈타인 거리. `ceiling` 을 넘는 것이 확정되면 즉시 끊는다.

    끊을 때는 `ceiling + 1` 을 돌려준다 — 정확한 값이 아니라 **"넘었다"** 는 표시다.
    호출자는 임계 초과 여부만 보므로 정확한 거리를 계산할 이유가 없다.

    >>> edit_distance("초콜렛", "초콜릿")
    1
    >>> edit_distance("초콜렛", "포도")
    2
    """
    if a == b:
        return 0
    if abs(len(a) - len(b)) > ceiling:
        return ceiling + 1

    previous = list(range(len(b) + 1))
    for i, ch_a in enumerate(a, start=1):
        current = [i]
        for j, ch_b in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,  # 삭제
                    current[j - 1] + 1,  # 삽입
                    previous[j - 1] + (ch_a != ch_b),  # 교체
                )
            )
        if min(current) > ceiling:
            return ceiling + 1
        previous = current
    return previous[-1]


@dataclass(frozen=True)
class Correction:
    """교정 결과. **응답에 그대로 실어 보호자에게 무엇으로 읽었는지 밝힌다.**

    `surface` 를 감추면 보호자는 자기 말이 어떻게 해석됐는지 모른 채 답을 받는다.
    교정은 추정이므로 **추정한 사실 자체가 답의 일부다.**
    """

    surface: str  # 보호자가 쓴 말 — "초콜렛"
    name: str  # 교정된 어휘 이름 — "초콜릿"
    distance: int  # 몇 글자 달랐는가 — 1


def correct(surface: str, known: object) -> Correction | None:
    """`surface` 를 아는 어휘 중 하나로 교정한다. 못 하거나 애매하면 `None`.

    `known` 은 어휘 이름의 순회 가능한 모음이다 (`vocabulary.known_substances()`).

    **동점은 교정하지 않는다.** 거리가 같은 후보가 둘 이상이면 어느 쪽인지 계산으로는
    가릴 수 없다. 하나를 고르면 그 순간 **틀릴 확률 50% 를 사용자 모르게 감수시키는
    것**이 된다. 유보하고 되묻는 편이 옳다.
    """
    probe = normalize(surface)
    if len(probe) < MIN_NORMALIZED_LEN:
        return None

    best_distance = MAX_DISTANCE + 1
    winners: list[str] = []

    for name in known:
        target = normalize(name)
        if len(target) < MIN_NORMALIZED_LEN:
            continue
        if abs(len(probe) - len(target)) > MAX_LENGTH_DIFF:
            continue
        if FIRST_CHAR_MUST_MATCH and probe[:1] != target[:1]:
            continue

        distance = edit_distance(probe, target)
        if distance > MAX_DISTANCE:
            continue
        if distance < best_distance:
            best_distance, winners = distance, [name]
        elif distance == best_distance and name not in winners:
            winners.append(name)

    if len(winners) != 1:  # 못 찾음(0) 또는 애매함(2+) — 둘 다 유보다
        return None
    return Correction(surface=surface, name=winners[0], distance=best_distance)
