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
    """?pet_id → 세션 → 첫 번째 pet 순으로 정한다.

    링크에 pet_id 가 없는 화면(채팅 내역·기록장)에서도 직전에 고른 pet 이
    유지되도록 세션을 본다. 세션 값은 chat_room 이 남긴다.
    """
    if not request.user.is_authenticated:
        return {}
    pet = None
    pet_id = request.GET.get("pet_id")
    if pet_id:
        pet = Pet.objects.filter(pet_id=pet_id, user=request.user).first()
    if pet is None:
        saved = request.session.get("active_pet_id")
        if saved:
            pet = Pet.objects.filter(pet_id=saved, user=request.user).first()
    if pet is None:
        pet = request.user.pets.first()
    if pet is None:
        return {}
    return {
        "active_pet": pet,
        "active_pet_emoji": _SPECIES_EMOJI.get(pet.species, "🐾"),
        "active_pet_meta": _build_meta(pet),
    }