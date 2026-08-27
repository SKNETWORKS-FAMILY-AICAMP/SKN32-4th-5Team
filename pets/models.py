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

from pettriage.compute.vocabulary import SPECIES as _SPECIES

#: 화면에 보일 한국어 이름은 Django 의 몫이지만, **코드 목록은 도메인의 것이다.**
#: `compute.vocabulary.SPECIES` 가 단일 출처다 (D-22) — `contracts.py` 도 같은 방식으로
#: 자기 `Literal` 을 이 목록에 묶어 둔다.
#:
#: 🔴 **2026-08-26 흡수** — 원래 여기 세 줄이 그냥 다시 적혀 있었다. 그러면 종이 늘 때
#:    고칠 곳이 셋이 되고, 한 곳을 빠뜨리면 **화면에서는 고를 수 있는데 판정이 모르는 종**이
#:    생긴다. 2026-08-01 에 `contracts.py` 에서 똑같은 재정의를 걷어낸 적이 있다 (D-48).
SPECIES_CHOICES = [
    ("dog", "개"),
    ("cat", "고양이"),
    ("bird", "새"),
]

assert {c for c, _ in SPECIES_CHOICES} == set(_SPECIES), (
    f"종 정의가 어긋났다 — pets.models={[c for c, _ in SPECIES_CHOICES]} "
    f"vocabulary={list(_SPECIES)}. 단일 출처는 compute.vocabulary.SPECIES 다."
)

SIZE_CHOICES = [
    ("small", "소형"),
    ("medium", "중형"),
    ("large", "대형")
]

class Pet(models.Model):
    pet_id = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pets")
    name = models.CharField(max_length=50)
    species = models.CharField(max_length=10, choices=SPECIES_CHOICES)
    breed = models.CharField(max_length=50, null=True, blank=True)
    weight_kg = models.FloatField(null=True, blank=True)
    #프로필 화면용
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, blank=True)
    age = models.CharField(max_length=20, blank=True)  # "2살" · "6개월" 자유 입력
    gender = models.CharField(max_length=10, blank=True)
    intro = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)  # 알러지 · 질환
    photo = models.ImageField(upload_to="pets/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pets"
        #: 🔴 **`ordering` 이 없으면 `.first()` 가 무엇을 주는지 아무도 모른다.**
        #:
        #: `pet_id` 는 랜덤 UUID 문자열 PK 다. 정렬을 안 걸면 DB 가 편한 순서로 주고,
        #: 그 순서는 등록순과 아무 상관이 없다. 그런데 화면 셋이 `.first()` 에 기대어
        #: **"첫 반려동물"** 을 고른다 —
        #:   `chat/views.py`(pet_id 없이 /chat/ 진입) · `chat/context_processors.py`
        #:   (사이드바 카드) · `diary/views.py`(기록장 기본 pet).
        #:
        #: 2026-08-27 권소라의 UI 테스트(TC-FR-CHAT-006)가 잡아냈다 —
        #: *"현재는 등록순과 우연히 일치하나 신규 등록 시 뒤집힐 수 있음"*.
        #: 우연히 맞는 것은 맞는 것이 아니다. FR-CHAT-006 이 "첫 반려동물"이라고
        #: 적었으므로 **등록순**으로 못박는다.
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.pet_id})"
