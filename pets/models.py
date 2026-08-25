"""Pet — 반려동물 프로필.

`src/pettriage/app/models.py`의 SQLAlchemy `Pet`을 Django ORM으로 재작성한 것이다 (D-99).
필드는 그 모델과 1:1로 맞췄다 — `pet_id`가 문자열 PK인 것도 그대로다.
`contracts.py`(`RecordCreate.pet_id: str`)가 문자열 ID를 기대하므로,
Django 기본값인 정수 PK로 바꾸면 그쪽 계약이 깨진다.

⚠️ `user` 는 지금 `settings.AUTH_USER_MODEL`(기본 `auth.User`, 정수 PK)을 가리킨다.
   원본 SQLAlchemy `User.user_id`는 문자열(UUID) PK다 — 계정 앱이 아직 없어서
   임시로 기본 User를 쓴 것이고, 계정 앱이 정해지면 이 FK를 다시 봐야 한다.
"""

from django.conf import settings
from django.db import models

SPECIES_CHOICES = [
    ("dog", "개"),
    ("cat", "고양이"),
    ("bird", "새"),
]


class Pet(models.Model):
    pet_id = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pets")
    name = models.CharField(max_length=50)
    species = models.CharField(max_length=10, choices=SPECIES_CHOICES)
    breed = models.CharField(max_length=50, null=True, blank=True)
    weight_kg = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pets"

    def __str__(self) -> str:
        return f"{self.name} ({self.pet_id})"
