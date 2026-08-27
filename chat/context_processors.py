"""사이드바 프로필 카드용 — 현재 활성 pet을 모든 템플릿에 노출."""

from pets.models import Pet

_SPECIES_EMOJI = {"dog": "🐶", "cat": "🐱", "bird": "🦜"}
_SIZE_KO = {"small": "소형", "medium": "중형", "large": "대형"}
_SPECIES_KO = {"dog": "견", "cat": "묘", "bird": "앵무새"}


def _build_meta(pet):
    parts = []
    if pet.breed:
        parts.append(pet.breed)
    elif pet.species == "bird":
        parts.append("앵무새")
    elif pet.species and pet.size:
        parts.append(_SIZE_KO.get(pet.size, "") + _SPECIES_KO.get(pet.species, ""))
    if pet.age:
        parts.append(pet.age)
    if pet.gender:
        parts.append(pet.gender)
    if pet.weight_kg:
        parts.append(f"{pet.weight_kg}kg")
    return " · ".join(parts)


def active_pet(request):
    """`?pet_id` → 세션 → 등록순 첫 pet 순으로 정한다.

    링크에 `pet_id` 가 없는 화면(채팅 내역·기록장)에서도 직전에 고른 pet 이 유지되도록
    세션을 본다.

    🔴 **여기서는 세션에 쓰지 않는다.** 이 함수는 모든 템플릿에서 돈다 — 여기서 쓰면
       *언제 무엇이 바뀌었는지* 아무도 못 따라간다. **쓰는 곳은 뷰다** —
       `chat/views.py::chat_room` 과 `diary/views.py::DiaryPageView` 둘.
       (2026-08-27 `lgj` 흡수 — 그쪽은 여기서도 되썼다. 읽는 자리와 쓰는 자리를 가른다.)

    ⚠️ 세션에 남은 id 는 **없는 pet 일 수 있다** (그 사이 지웠을 때).
       `.first()` 로 조용히 버리고 다음 후보로 간다 — 우리가 넣은 값이라 우리가 치운다.
    """
    if not request.user.is_authenticated:
        return {}
    pet = None
    pet_id = request.GET.get("pet_id") or request.session.get("active_pet_id")
    if pet_id:
        pet = Pet.objects.filter(pet_id=pet_id, user=request.user).first()
    if pet is None:
        pet = request.user.pets.first()
    if pet is None:
        return {}
    return {
        "active_pet": pet,
        "active_pet_emoji": _SPECIES_EMOJI.get(pet.species, "🐾"),
        "active_pet_meta": _build_meta(pet),
    }
