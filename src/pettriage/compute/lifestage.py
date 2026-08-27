"""성장기 판단 — **한 곳에서만 정한다** (D-22).

2026-08-27 에 이 규칙이 **두 벌**이었고 서로 다른 답을 냈다.

    diary/views.py   `float("0.5살")`      → ValueError → 성장기 아님
    diary.html       `parseFloat("0.5살")` → 0.5        → 성장기

`parseFloat` 은 앞에서부터 숫자만 읽고 멈추는데 `float()` 은 문자열 전체가 숫자여야 한다.
`age` 는 `"2살"` · `"6개월"` 처럼 **자유 입력**이라 이 차이가 그대로 드러났다 —
생후 6개월을 `0.5살` 로 적으면 **화면엔 "🌱 성장기" 배지가 뜨는데 서버는 체중 급변
알림을 냈다.** 같은 화면이 같은 아이에 대해 반대로 말한 것이다.

`diary/views.py` 의 옛 docstring 은 *"`isJuvenile()`과 같은 판단"* 이라고 적혀 있었다.
**주장이 사실이 아니었고, 아무도 그것을 검사하지 않았다.**

그래서 규칙을 여기(Django 를 모르는 순수 함수)로 올렸다. 얻는 것 둘 —

1. **서버가 판단하고 화면은 받아 쓴다.** `diary.html` 은 이제 계산하지 않는다.
   등급 이름·색을 화면이 정하지 않고 `GET /api/triage-levels` 로 받는 것과 같은 방식이다 (D-40).
2. **`tests/` 에서 바로 검증된다.** Django 앱 코드는 `testpaths` 밖이라 CI 가 한 줄도
   실행하지 않지만(13 §5), 여기 있으면 본다.

## 왜 성장기엔 알림을 끄나

신생아 강아지·새끼 고양이·부화 직후 앵무새 새끼는 **하루에 5~10%씩 체중이 느는 것이
정상**이다 (2026-08-26 확인 · pawsinwork.com · hari.ca 등). 체중 급변 알림의 임계값
5% · 10% 가 이 기간엔 아예 의미가 없다. 새 숫자를 만드는 대신 알림 자체를 끈다 (D-103).
"""

from __future__ import annotations

import re

#: 성장기로 보는 상한 — 만 1살.
JUVENILE_YEARS = 1.0

#: `"2살"` · `"0.5 살"` · `"3주"` 처럼 **숫자 뒤에 단위가 붙는** 자유 입력에서 앞 숫자만 뗀다.
#: JS `parseFloat` 과 같은 태도다 — 읽히는 데까지 읽고 멈춘다.
_LEADING_NUMBER = re.compile(r"\s*[+-]?(\d+\.?\d*|\.\d+)")

#: 1년 미만이 확실한 단위. 숫자를 볼 것도 없이 성장기다.
#:
#: 🔴 **`"주"` 를 빠뜨리면 안 된다.** 옛 구현은 `"개월"` 만 봐서 `"3주"` 가 성인으로 잡혔다 —
#:    하루 5~10% 증가가 정상인 **가장 확실한 성장기가 통째로 새고 있었다.**
_SUB_YEAR_UNITS = ("개월", "주", "일")


def is_juvenile(age: str | None) -> bool:
    """`age` 자유 입력이 성장기를 뜻하는가.

    >>> is_juvenile("6개월"), is_juvenile("3주"), is_juvenile("0.5살")
    (True, True, True)
    >>> is_juvenile("2살"), is_juvenile(""), is_juvenile(None)
    (False, False, False)

    ⚠️ **모르면 `False` 다.** 알림을 끄는 쪽이 아니라 켜는 쪽으로 기운다 —
    성장기가 아닌데 껐다가 진짜 체중 급변을 놓치는 것이, 성장기인데 켜서
    한 번 더 알리는 것보다 나쁘다 (D-09 의 하향 금지와 같은 방향).
    """
    if not age:
        return False
    text = age.strip()
    if any(u in text for u in _SUB_YEAR_UNITS):
        return True
    m = _LEADING_NUMBER.match(text)
    if m is None:
        return False
    return float(m.group(1)) < JUVENILE_YEARS
