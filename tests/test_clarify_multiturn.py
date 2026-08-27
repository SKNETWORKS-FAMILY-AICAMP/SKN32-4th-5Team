"""되묻기가 **여러 턴에 걸쳐** 이어지는가 (FR-15 · FR-37 · UC-04).

2026-08-27 에 권소라의 수동 테스트(TC-FR-CHAT-005)가 이 비고를 남겼다 —

    "0알 먹었어 → 되질문 발생 → 포도 or 초콜릿 답변해도 재차 되질문 후 응답불가"

원인이 둘이었고 서로를 가리고 있었다.

**① 실제 엔진이 앞 턴을 잃었다.** `GraphEngine._build_state` 가 그래프에 넘기는 것은
   `question` 하나뿐이었다. 두 번째 턴에 그래프가 보는 것은 `"포도"` 한 마디였고,
   *"0알 먹었어"* 는 사라진 뒤였다. `session.question_history` 는 채워지고 있었지만
   **읽는 곳이 `StubEngine` 뿐**이었다 — 스텁이 진짜 엔진보다 대화를 잘 이어받았다.

**② 되묻기 예산이 안 돌아왔다.** `Session.merge()` 는 `SLOTS`(종·펫·체중·양) 넷만 보고
   진전을 판단하는데 **물질은 거기 없다.** 그래서 *"포도요"* 라고 제대로 답해도
   `progressed=False` 였다. `merge()` 의 docstring 이 *"협조적인 사용자가 슬롯을 하나씩
   채우다가 상한에 걸려 거절된다"* 를 막겠다고 적어 놓고, 정작 물질에서 그 일이 났다.

**자동화 657건이 전부 초록인 채로 이걸 놓쳤다.** 되묻기 테스트는 있었지만 전부
**한 턴짜리**였다. `test_state_reaches_response.py` 가 머리말에 적은 것과 같은 모양이다 —
*"노드 단위 테스트는 노드가 키를 돌려주는가까지 보고, 계약 테스트는 응답이 유효한가부터
본다. 그 사이가 비어 있었다."* 이번에 빈 곳은 **턴과 턴 사이**였다.
"""

from __future__ import annotations

import pytest

from pettriage.app.contracts import MAX_CLARIFY_TURNS, AskRequest
from pettriage.app.session import Session
from pettriage.graph.engine import GraphEngine


@pytest.fixture
def engine() -> GraphEngine:
    """`__init__` 을 건너뛴다 — 상태 조립만 보므로 그래프 컴파일이 필요 없다."""
    return GraphEngine.__new__(GraphEngine)


class TestContextReachesTheGraph:
    """① 앞 턴이 그래프까지 가는가."""

    def test_첫_턴은_이력이_비어_있다(self, engine):
        """🔴 **단일 턴 동작이 이전과 같아야 한다.**

        골든셋 60건이 전부 단일 턴이다. 여기서 이력이 새면 기준선이 흔들리고
        D-102(전환 전후 판정 동일)를 못 쓴다.
        """
        session = Session(session_id="s-1")
        req = AskRequest(question="강아지가 포도를 먹었어요")
        session.merge(req)

        state = engine._build_state(req, session)

        assert state["question"] == "강아지가 포도를 먹었어요"
        assert state["question_history"] == []

    def test_두번째_턴에_앞_발화가_실린다(self, engine):
        session = Session(session_id="s-1")
        session.merge(AskRequest(question="0알 먹었어"))
        req = AskRequest(question="포도")
        session.merge(req)

        state = engine._build_state(req, session)

        assert state["question"] == "포도"
        assert (
            "0알 먹었어" in state["question_history"]
        ), "되묻기 답변만 보면 무엇에 대한 답인지 알 수 없다"

    def test_최근_발화가_앞에_온다(self, engine):
        session = Session(session_id="s-1")
        for q in ["첫째", "둘째", "셋째"]:
            session.merge(AskRequest(question=q))
        req = AskRequest(question="넷째")
        session.merge(req)

        state = engine._build_state(req, session)

        assert state["question_history"][0] == "셋째"

    def test_이력은_되묻기_상한만큼만_쌓인다(self, engine):
        """무한정 모으면 오래된 대화가 판단에 섞인다."""
        session = Session(session_id="s-1")
        for i in range(10):
            session.merge(AskRequest(question=f"발화{i}"))

        assert len(session.question_history) <= MAX_CLARIFY_TURNS + 1


class TestClarifyBudgetReturns:
    """② 진전이 있으면 되묻기 예산이 돌아오는가.

    `_build_response` 를 직접 부른다 — 그래프를 돌리지 않고 **예산 규칙만** 본다.
    """

    @staticmethod
    def _clarify_state(missing: list[str], turns: int) -> dict:
        return {
            "status": "clarify",
            "missing_slots": missing,
            "clarify_question": "무엇을 먹었나요?",
            "clarify_turns": turns,
        }

    def test_비어_있던_것이_줄면_예산이_돌아온다(self, engine):
        session = Session(session_id="s-1")

        engine._build_response(self._clarify_state(["substance", "amount_g"], 1), session)
        assert session.clarify_turns == 1

        # 사용자가 물질을 답했다 — 남은 것이 줄었다
        engine._build_response(self._clarify_state(["amount_g"], 2), session)

        assert (
            session.clarify_turns == 0
        ), "제대로 답했는데 예산이 안 돌아오면 협조적인 사용자가 거절당한다"

    def test_그대로면_예산이_줄어든다(self, engine):
        """진전이 없으면 상한은 상한대로 작동해야 한다."""
        session = Session(session_id="s-1")

        engine._build_response(self._clarify_state(["substance"], 1), session)
        engine._build_response(self._clarify_state(["substance"], 2), session)

        assert session.clarify_turns == 2

    def test_늘어나도_예산이_줄어든다(self, engine):
        session = Session(session_id="s-1")

        engine._build_response(self._clarify_state(["substance"], 1), session)
        engine._build_response(self._clarify_state(["substance", "weight_kg"], 2), session)

        assert session.clarify_turns == 2

    def test_물질은_세션_슬롯이_아니라서_merge_로는_못_잡는다(self):
        """🔴 이 테스트가 **왜 예산 규칙이 따로 필요한지**를 고정한다.

        `merge()` 만 믿으면 물질 진전이 영원히 안 잡힌다.
        """
        from pettriage.app.session import SLOTS

        assert "substance" not in SLOTS
        session = Session(session_id="s-1")
        session.merge(AskRequest(question="0알 먹었어"))

        progressed = session.merge(AskRequest(question="포도"))

        assert (
            progressed is False
        ), "물질을 답해도 merge 는 진전으로 안 센다 — missing_slots 를 견줘야 하는 이유"


class TestAnsweredClearsState:
    def test_답이_나오면_되묻기_상태가_비워진다(self, engine):
        session = Session(session_id="s-1")
        engine._build_response(self._c(["substance"], 1), session)
        assert session.last_missing == ["substance"]

        engine._build_response({"status": "refused", "refusal_reason": "근거없음"}, session)

        assert session.last_missing == []
        assert session.clarify_turns == 0

    @staticmethod
    def _c(missing: list[str], turns: int) -> dict:
        return {
            "status": "clarify",
            "missing_slots": missing,
            "clarify_question": "?",
            "clarify_turns": turns,
        }
