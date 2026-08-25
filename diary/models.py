"""DiaryEntry — 일일 다이어리 기록.

`src/pettriage/app/models.py`의 SQLAlchemy `DiaryEntry`를 Django ORM으로
재작성한 것이다 (D-99). 소유자 확인은 `(user, pet)` 두 필드가 모든 조회에
같이 붙어야 한다 — `pet`만으로 찾으면 남의 기록을 읽는다 (D-52 원칙, 원본과 동일).

`weight_kg`는 nullable — 매일 재지 않는다. NULL을 그대로 둔다 (D-52, 원본과 동일).

`meals`·`symptoms`는 원본(SQLAlchemy)에서 JSON을 문자열(Text)로 저장하고
`records.py`가 `json.dumps`/`json.loads`로 직접 오갔다. Django는 `JSONField`가
네이티브로 있어 그 왕복을 대신하므로 여기서는 `JSONField`를 쓴다 — 물리
스키마만 다르고, `contracts.py`의 `list[str]` 계약은 그대로 만족한다.

⚠️ `user`는 pets.Pet과 같은 이유로 지금 `settings.AUTH_USER_MODEL`(기본 auth.User)을
   가리킨다 — 계정 앱이 정해지면 다시 봐야 한다.
"""

import uuid

from django.conf import settings
from django.db import models


def _generate_entry_id() -> str:
    """`records.py`가 지금 쓰는 것과 같은 형식 — uuid4의 앞 12자리 hex."""
    return uuid.uuid4().hex[:12]


class DiaryEntry(models.Model):
    entry_id = models.CharField(max_length=36, primary_key=True, default=_generate_entry_id)
    pet = models.ForeignKey("pets.Pet", on_delete=models.CASCADE, related_name="diary_entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="diary_entries")
    recorded_date = models.DateField()  # 캘린더용 (날짜만)
    recorded_at = models.DateTimeField()
    weight_kg = models.FloatField(null=True, blank=True)
    meals = models.JSONField(default=list, blank=True)
    symptoms = models.JSONField(default=list, blank=True)
    note = models.TextField(null=True, blank=True)
    droppings = models.CharField(max_length=100, null=True, blank=True)  # 조류 전용
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "diary_entries"
        indexes = [models.Index(fields=["pet", "user", "recorded_date"])]

    def __str__(self) -> str:
        return f"{self.entry_id} · {self.pet_id} · {self.recorded_date}"
