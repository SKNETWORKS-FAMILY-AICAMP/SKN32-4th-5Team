import uuid

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import Pet


@login_required
def pet_list(request):
    """로그인한 사용자의 반려동물 목록. 없으면 등록 화면으로 보낸다."""
    pets = Pet.objects.filter(user=request.user)
    if not pets.exists():
        return redirect("pets:create")
    return render(request, "pets/pet_list.html", {"pets": pets})


@login_required
def pet_create(request):
    """반려동물 프로필 등록."""
    error = None

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        species = request.POST.get("species", "")
        size = request.POST.get("size", "")

        if not name:
            error = "이름을 입력해주세요."
        elif species not in dict(Pet._meta.get_field("species").choices):
            error = "품종을 선택해주세요."
        elif size not in dict(Pet._meta.get_field("size").choices):
            error = "크기를 선택해주세요."
        else:
            weight_raw = request.POST.get("weight_kg", "").strip()
            pet = Pet(
                pet_id=uuid.uuid4().hex,
                user=request.user,
                name=name,
                species=species,
                size=size,
                age=request.POST.get("age", "").strip(),
                gender=request.POST.get("gender", "").strip(),
                intro=request.POST.get("intro", "").strip(),
                notes=request.POST.get("notes", "").strip(),
                weight_kg=float(weight_raw) if weight_raw else None,
            )
            if request.FILES.get("photo"):
                pet.photo = request.FILES["photo"]
            pet.save()

            if request.POST.get("action") == "add_another":
                return redirect("pets:create")
            return redirect("pets:list")

    return render(request, "pets/pet_form.html", {"error": error})