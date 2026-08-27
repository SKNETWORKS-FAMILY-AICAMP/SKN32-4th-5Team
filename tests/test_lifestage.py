"""성장기 판단 (`compute.lifestage`) — 규칙이 다시 두 벌로 갈라지지 않게 못박는다.

2026-08-27 이전에는 같은 판단이 `diary/views.py` 와 `diary.html` 에 따로 있었고,
**서로 다른 답을 냈다.** 아무도 그것을 검사하지 않아서 몇 주를 버텼다.

이 파일이 있는 이유는 규칙이 맞는지 보기 위해서만이 아니라,
**규칙이 한 곳에 있는지 보기 위해서**다 (D-22).
"""

import pytest

from pettriage.compute.lifestage import JUVENILE_YEARS, is_juvenile


class TestSubYearUnits:
    """1년 미만이 확실한 단위는 숫자를 볼 것도 없다."""

    @pytest.mark.parametrize("age", ["6개월", "3개월", "1개월", "12개월", "생후 2개월"])
    def test_개월은_성장기다(self, age):
        assert is_juvenile(age) is True

    @pytest.mark.parametrize("age", ["3주", "2주", "생후 2주", "6주령"])
    def test_주는_성장기다(self, age):
        """🔴 옛 구현이 통째로 놓치던 자리.

        `"개월"` 만 봐서 `"3주"` 가 성인으로 잡혔다. 하루 5~10% 증가가 정상인
        **가장 확실한 성장기**가 체중 급변 알림을 그대로 맞고 있었다.
        """
        assert is_juvenile(age) is True

    @pytest.mark.parametrize("age", ["10일", "생후 5일"])
    def test_일도_성장기다(self, age):
        assert is_juvenile(age) is True


class TestYears:
    @pytest.mark.parametrize("age", ["2살", "1살", "3살", "10살", "2", "15"])
    def test_한살이상은_성장기가_아니다(self, age):
        assert is_juvenile(age) is False

    @pytest.mark.parametrize("age", ["0.5살", "0살", "0.9살", "0.5", "0"])
    def test_한살미만은_성장기다(self, age):
        assert is_juvenile(age) is True


class TestTwoImplementationsDisagreed:
    """🔴 화면(JS)과 서버(Python)가 실제로 다른 답을 냈던 입력들.

    | age     | 옛 화면 `parseFloat` | 옛 서버 `float()` |
    |---------|---------------------|-------------------|
    | "0.5살" | 0.5 → 성장기        | ValueError → 아님 |
    | "0살"   | 0   → 성장기        | ValueError → 아님 |

    증상은 **같은 화면이 같은 아이에 대해 반대로 말하는 것**이었다 —
    체중 그래프 옆엔 "🌱 성장기" 배지가 뜨는데 우측 하단엔 "체중이 급증했어요"
    토스트가 떴다. 이제 판단은 서버 한 곳에서 나오고 화면은 받아 쓴다.
    """

    @pytest.mark.parametrize("age", ["0.5살", "0살"])
    def test_어긋나던_입력이_성장기로_모인다(self, age):
        assert is_juvenile(age) is True


class TestUnknownIsNotJuvenile:
    """모르면 알림을 **켜는** 쪽으로 기운다.

    성장기가 아닌데 껐다가 진짜 체중 급변을 놓치는 것이,
    성장기인데 켜서 한 번 더 알리는 것보다 나쁘다 (D-09 하향 금지와 같은 방향).
    """

    @pytest.mark.parametrize("age", ["", None, "몰라요", "어려요", "-"])
    def test_읽을_수_없으면_아니다(self, age):
        assert is_juvenile(age) is False


def test_경계는_상수로_노출된다():
    """`1.0` 을 테스트가 다시 적으면 그것도 두 벌이다."""
    assert JUVENILE_YEARS == 1.0
    assert is_juvenile(f"{JUVENILE_YEARS - 0.01}") is True
    assert is_juvenile(f"{JUVENILE_YEARS}") is False
