"""POST /api/records — 다이어리 기록 저장 (upsert).

`src/pettriage/app/routes/records.py::create_record`을 Django DRF로 옮긴 것 (D-99).
로직은 그대로다 — 같은 `(pet, user, recorded_date)`가 있으면 갱신, 없으면 새로 만든다.
소유자 확인은 pet 조회 시 `(pet_id, user)`로 붙는다 — `pet_id`만으로 찾으면
남의 것도 찾아지므로 D-52 원칙을 그대로 따른다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from pets.models import Pet

from .models import DiaryEntry
from .serializers import RecordCreateSerializer


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
