"""POST /internal/report/summarize — Django가 보낸 다이어리 rows를 요약한다.

D-99 `GET /api/report` 경계 **A안** (2026-08-25, 오한빈 확정 · `14 §2.4`): Django는 DB 조회만 하고
`report.py`의 `summarize_period()`는 그대로 재사용한다. 이 파일은 그 재사용을
위한 얇은 진입점 하나이고, `report.py` 자체는 한 줄도 고치지 않는다.

⚠️ **외부에 노출하지 않는다** (docs/12 §8 — 추론 서비스 포트 **8001** 은 보안그룹에서 막는다).
   Django가 내부망(127.0.0.1)으로만 부른다. 이 라우트에 별도 인증을 걸지 않은
   이유도 그것이다 — 포트 자체가 바깥에서 안 열린다.

DB(SQLAlchemy)를 쓰지 않으므로 `routes/__init__.py`의 상시 라우터 목록에 둔다 —
`DATABASE_URL` 없이도, `[db]` 없이도 그대로 뜬다.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..report import summarize_period

router = APIRouter(prefix="/internal/report", tags=["internal"])


class SummarizeRequest(BaseModel):
    #: `records.py::_row_to_dict()`(FastAPI)·`diary/views.py::_row_to_dict()`(Django)가
    #: 만드는 것과 같은 모양이어야 한다 — 계약을 새로 만들지 않고 그 모양만 맞춘다.
    rows: list[dict[str, Any]]
    period_from: str = ""
    period_to: str = ""


class SummarizeResponse(BaseModel):
    summary: str
    summary_by: str  # "model" 또는 "code" — 폴백을 숨기지 않는다 (04 §8)


@router.post("/summarize", response_model=SummarizeResponse)
def summarize(req: SummarizeRequest) -> SummarizeResponse:
    summary, summary_by = summarize_period(req.rows, req.period_from, req.period_to)
    return SummarizeResponse(summary=summary, summary_by=summary_by)
