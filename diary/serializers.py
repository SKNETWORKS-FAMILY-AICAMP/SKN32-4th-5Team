"""POST /api/records 입력 검증.

`contracts.RecordCreate`를 재정의하지 않는다 (D-100) — Django 자기 모델(DiaryEntry)에
대한 Serializer만 둔다. 다만 프론트는 FastAPI 시절과 같은 JSON을 그대로 보내므로,
그 모양(필드·검증 규칙)은 `contracts.py`의 `RecordCreate`와 같아야 실제로 동작한다.

`recorded_at` 정규화 로직은 `contracts.py:110`의 `_normalize_recorded_at`과
같은 이유로 같은 방식으로 처리한다 — 리포트 기간 필터가 문자열 비교라
`2026-7-3` 같은 0 안 채운 값이 들어오면 정렬이 깨진다.
"""

from __future__ import annotations

from datetime import datetime

from rest_framework import serializers

from pets.models import SPECIES_CHOICES

_SPECIES_KEYS = [key for key, _ in SPECIES_CHOICES]


class RecordCreateSerializer(serializers.Serializer):
    pet_id = serializers.CharField(min_length=1, max_length=64)
    species = serializers.ChoiceField(choices=_SPECIES_KEYS)
    recorded_at = serializers.CharField()
    note = serializers.CharField(max_length=4000, required=False, allow_blank=True, default="")
    meals = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    symptoms = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    weight_kg = serializers.FloatField(
        required=False, allow_null=True, max_value=200, default=None
    )
    droppings = serializers.CharField(required=False, allow_null=True, default=None)

    def validate_weight_kg(self, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise serializers.ValidationError("weight_kg는 0보다 커야 합니다.")
        return value

    def validate_recorded_at(self, value: str) -> str:
        """ISO 8601로 파싱해 정규화된 문자열로 되돌린다 (contracts.py와 동일 규칙)."""
        raw = (value or "").strip()
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise serializers.ValidationError(
                f"recorded_at 이 ISO 8601 이 아니다: {raw!r} "
                "(예: 2026-07-02 · 2026-07-02T09:00 · 2026-07-02T09:00:00+09:00)"
            ) from exc
        return dt.isoformat()
