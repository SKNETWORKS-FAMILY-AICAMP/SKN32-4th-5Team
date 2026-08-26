"""POST /api/records · GET /api/report — 다이어리.

`src/pettriage/app/routes/records.py`를 Django DRF로 옮긴 것 (D-99).
저장 로직은 그대로다 — 같은 `(pet, user, recorded_date)`가 있으면 갱신, 없으면 새로 만든다.
소유자 확인은 pet 조회 시 `(pet_id, user)`로 붙는다 — `pet_id`만으로 찾으면
남의 것도 찾아지므로 D-52 원칙을 그대로 따른다.

`GET /api/report`는 2026-08-25 오한빈과 확정한 3안대로다 — Django는 DB 조회만
하고, 집계 문장화(LLM)는 FastAPI의 `report.summarize_period()`를 그대로
내부 호출로 위임한다. `report.py`는 한 줄도 고치지 않는다.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from pets.models import Pet

from .models import DiaryEntry
from .serializers import RecordCreateSerializer

log = logging.getLogger(__name__)

#: report.py의 `_NOTE_CHARS`와 같은 값이어야 한다 — 그보다 작게 자르면 요약이
#: 실제로 덜 보고 만들어진다. 크게 잡는 건 안전하지만(어차피 거기서 또 자름)
#: 전송량 절감 효과가 준다.
_NOTE_CHARS_FOR_SUMMARY = 300

#: "오늘"을 판단하는 기준 시간대. UTC로 저장하고(models.py 전역 원칙) 여기서만
#: KST로 바꾼다 — UTC 자정~오전 9시 사이에 "오늘"을 UTC 기준으로 판단하면
#: 실제로는 이미 KST로 다음 날인데 하루 전으로 잘못 세는 사고가 난다.
_KST = ZoneInfo("Asia/Seoul")

#: 직전 체중 대비 변화율 구간 — 종 구분 없이 공통이다 (2026-08-26 팀 결정).
#: 새도 개·고양이와 다른 임계값을 쓸 근거가 없었다 — 오히려 새는 하루 중
#: 공복·급여로 5~10% 정도 왔다갔다하는 게 정상이라(myrightbird.com), 종별로
#: 낮추면 정상 변동을 "위험"으로 잘못 잡을 수 있다.
#:
#: ★흡수(lse, 2026-08-26) — **값을 `settings` 로 옮겼다** (D-103 · D-41).
#:   *"12% 변했다"* 는 사용자 기록이지만 *"12%면 상담하라"* 는 외부 주장이다.
#:   전자는 계산이고 후자는 설정이다. 위 주석의 근거는 그대로 둔다 — 값이 어디서
#:   왔는지는 **값 옆이 아니라 이 자리에** 남아야 다음 사람이 읽는다.
_WEIGHT_CHANGE_WATCH_THRESHOLD_PCT = settings.DIARY_WEIGHT_ALERT_WATCH_PCT
_WEIGHT_CHANGE_VET_THRESHOLD_PCT = settings.DIARY_WEIGHT_ALERT_VET_PCT


@method_decorator(ensure_csrf_cookie, name="dispatch")
class DiaryPageView(LoginRequiredMixin, TemplateView):
    """GET /diary/ — 기록장 화면. Django 세션 인증 + CSRF 쿠키 발급."""

    template_name = "diary/diary.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pet_id = self.request.GET.get("pet_id")
        pet = None
        if pet_id:
            pet = Pet.objects.filter(pet_id=pet_id, user=self.request.user).first()
        if pet is None:
            pet = self.request.user.pets.first()
        ctx["pet"] = pet
        return ctx


class RecordCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RecordCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            pet = Pet.objects.get(pet_id=data["pet_id"], user=request.user)
        except Pet.DoesNotExist:
            return Response({"detail": "반려동물을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        recorded_at = datetime.fromisoformat(data["recorded_at"])
        if recorded_at.tzinfo is None:
            recorded_at = recorded_at.replace(tzinfo=UTC)

        # 조류가 아니면 droppings 는 버린다 (D-36 최소 수집).
        droppings = data["droppings"] if data["species"] == "bird" else None

        entry, _created = DiaryEntry.objects.update_or_create(
            pet=pet,
            user=request.user,
            recorded_date=recorded_at.date(),
            defaults={
                "recorded_at": recorded_at,
                "weight_kg": data["weight_kg"],
                "meals": data["meals"],
                "symptoms": data["symptoms"],
                "note": data["note"] or None,
                "droppings": droppings,
            },
        )

        # FastAPI 원본과 같이 갱신이든 신규든 201로 응답한다 (records.py의 데코레이터가
        # 두 분기 모두에 같은 상태코드를 적용하는 것과 동일).
        return Response(
            {"record_id": entry.entry_id, "pet_id": entry.pet_id, "indexed": False},
            status=status.HTTP_201_CREATED,
        )


def _row_to_dict(e: DiaryEntry) -> dict:
    """DB 행 → FastAPI `records.py::_row_to_dict()`와 같은 모양.

    report.py의 `summarize_period(rows, ...)`가 기대하는 입력이 이 모양이라,
    여기서 어긋나면 내부 호출 저편에서 조용히 잘못된 요약이 나온다.
    """
    return {
        "record_id": e.entry_id,
        "pet_id": e.pet_id,
        "recorded_at": e.recorded_at.isoformat() if e.recorded_at else "",
        "note": e.note or "",
        "meals": e.meals or [],
        "symptoms": e.symptoms or [],
        "weight_kg": e.weight_kg,
        "droppings": e.droppings,
    }


def _summarize_via_inference(
    rows: list[dict], period_from: str, period_to: str
) -> tuple[str, str]:
    """FastAPI의 `POST /internal/report/summarize`를 불러 요약을 받는다.

    note는 300자로 잘라서 보낸다 — report.py의 `_digest()`가 어차피 그 길이로
    자르므로 요약 결과는 동일하고, 전송량만 줄어든다 (2026-08-25 성능 확인).

    ⚠️ 추론 서비스가 안 떠 있으면 예외를 삼키고 폴백 문구를 준다 — report.py의
    "폴백을 숨기지 않는다"(04 §8)와 같은 태도다. `timeline`은 그대로 나가므로
    사용자는 기록 원본은 잃지 않는다.
    """
    rows_for_summary = [
        {**row, "note": (row["note"] or "")[:_NOTE_CHARS_FOR_SUMMARY]} for row in rows
    ]
    url = f"{settings.INFERENCE_INTERNAL_URL}/internal/report/summarize"
    try:
        resp = httpx.post(
            url,
            json={"rows": rows_for_summary, "period_from": period_from, "period_to": period_to},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["summary"], data["summary_by"]
    except httpx.HTTPError as e:
        log.warning("추론 서비스 내부 호출 실패 — 기록만 보여준다: %s", type(e).__name__)
        return "요약 서비스에 연결할 수 없습니다. 기록 원본은 아래에서 확인해 주세요.", "code"


def _is_juvenile(age: str) -> bool:
    """`diary.html`의 `isJuvenile()`과 같은 판단 — "개월" 표기거나 나이 숫자가 1 미만.

    성장기 판단 자체는 이 프로젝트에 이미 있었다(절대 체중 범위 체크용). 체중
    급변 감지에도 같은 기준을 그대로 쓴다 — 실제로 찾아보니 신생아 강아지·
    새끼 고양이·부화 직후 앵무새 새끼는 **하루에 5~10%씩 체중이 느는 게 정상**이다
    (2026-08-26 확인, pawsinwork.com·hari.ca 등). 이 알림의 임계값(5~10%)이
    성장기엔 아예 의미가 없어진다는 뜻이라, 새 숫자를 만드는 대신 이 기간엔
    알림 자체를 끈다.
    """
    if not age:
        return False
    if "개월" in age:
        return True
    try:
        return float(age) < 1
    except ValueError:
        return False


def _detect_weight_change(rows: list[dict], age: str = "") -> dict | None:
    """가장 최근 두 체중 기록을 비교해 급변 여부를 2단계(주의·병원)로 판정한다.

    `diary.html`의 `renderWeightStatus()`는 **절대 범위**(품종·크기별 정상 체중대)를
    보는 화면 로직이고, 이건 **변화율**을 보는 별개 신호다 — 정상 범위 안에서도
    짧은 기간에 급격히 변하면 그 자체로 이상 신호일 수 있다 (탈수·질병 등).

    기록이 2건 미만이면(비교 불가) `None`을 돌려준다 — 폴백을 숨기지 않는
    `report.py` 태도와 같다.
    """
    if _is_juvenile(age):
        return None

    weighed = [r for r in rows if r["weight_kg"] is not None]
    if len(weighed) < 2:
        return None

    prev, latest = weighed[-2], weighed[-1]
    if prev["weight_kg"] <= 0:
        return None

    change_pct = (latest["weight_kg"] - prev["weight_kg"]) / prev["weight_kg"] * 100
    abs_pct = abs(change_pct)
    if abs_pct < _WEIGHT_CHANGE_WATCH_THRESHOLD_PCT:
        return None

    direction = "증가" if change_pct > 0 else "감소"
    pct_display = round(abs_pct, 1)

    if abs_pct < _WEIGHT_CHANGE_VET_THRESHOLD_PCT:
        level = "watch"
        advice = "당분간 지켜봐 주세요."
    else:
        level = "vet"
        advice = "수의사와 상담해보세요."

    return {
        "level": level,  # "watch" | "vet"
        "from_kg": prev["weight_kg"],
        "to_kg": latest["weight_kg"],
        "change_pct": round(change_pct, 1),
        "message": (
            f"최근 체중이 {pct_display}% {direction}했어요 "
            f"({prev['weight_kg']}kg → {latest['weight_kg']}kg). {advice}"
        ),
    }


def _calculate_streak(dates: set[str]) -> int:
    """오늘(또는 오늘 기록이 아직 없으면 어제)부터 거슬러 올라가며 연속 기록 일수를 센다.

    듀오링고 스트릭과 같은 방식이다 — 오늘 아직 기록을 안 남겼어도 어제까지
    이어져 있으면 스트릭은 아직 안 끊긴 것으로 본다(오늘 자정까지 유예).
    오늘도 어제도 기록이 없으면 0(끊김)이다.

    `dates`는 **기간 필터와 무관하게 항상 전체 기록**에서 뽑아야 한다 — 다운로드
    모달처럼 특정 과거 기간만 조회할 때도 "오늘 기준 스트릭"은 그대로 나와야
    하기 때문이다 (`ReportView.get()`에서 별도 쿼리로 만든다).
    """
    if not dates:
        return 0

    today = datetime.now(_KST).date()
    cursor = today
    if cursor.isoformat() not in dates:
        cursor -= timedelta(days=1)
        if cursor.isoformat() not in dates:
            return 0

    streak = 0
    while cursor.isoformat() in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


class ReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pet_id = request.query_params.get("pet_id", "")
        period_from = request.query_params.get("period_from", "")
        period_to = request.query_params.get("period_to", "")

        try:
            pet = Pet.objects.get(pet_id=pet_id, user=request.user)
        except Pet.DoesNotExist:
            return Response({"detail": "반려동물을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        qs = DiaryEntry.objects.filter(pet=pet, user=request.user)
        if period_from:
            qs = qs.filter(recorded_date__gte=datetime.fromisoformat(period_from).date())
        if period_to:
            qs = qs.filter(recorded_date__lte=datetime.fromisoformat(period_to).date())
        entries = qs.order_by("recorded_at")

        rows = [_row_to_dict(e) for e in entries]
        summary, summary_by = _summarize_via_inference(rows, period_from, period_to)
        weight_alert = _detect_weight_change(rows, pet.age)

        all_dates = set(
            DiaryEntry.objects.filter(pet=pet, user=request.user)
            .values_list("recorded_date", flat=True)
        )
        streak = _calculate_streak({d.isoformat() for d in all_dates})

        return Response(
            {
                "pet_id": pet_id,
                "streak": streak,
                "period_from": period_from,
                "period_to": period_to,
                "timeline": rows,
                "summary": summary,
                "summary_by": summary_by,
                "weight_alert": weight_alert,
            }
        )
