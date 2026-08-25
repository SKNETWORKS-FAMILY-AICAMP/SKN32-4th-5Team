import uuid

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse

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


@login_required
def pet_edit(request, pet_id):
    """프로필 수정. 남의 프로필은 조회 단계에서 막힌다."""
    pet = get_object_or_404(Pet, pet_id=pet_id, user=request.user)
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
            pet.name = name
            pet.species = species
            pet.size = size
            pet.age = request.POST.get("age", "").strip()
            pet.gender = request.POST.get("gender", "").strip()
            pet.intro = request.POST.get("intro", "").strip()
            pet.notes = request.POST.get("notes", "").strip()
            pet.weight_kg = float(weight_raw) if weight_raw else None
            if request.POST.get("remove_photo"):
                pet.photo.delete(save=False)  # 파일도 함께 지운다
                pet.photo = None
            elif request.FILES.get("photo"):
                pet.photo = request.FILES["photo"]
            pet.save()
            return redirect("pets:list")

    return render(request, "pets/pet_form.html", {"pet": pet, "error": error})


@login_required
def pet_delete(request, pet_id):
    """프로필 삭제. POST 로만 지운다 — 주소를 여는 것만으로 지워지면 안 된다."""
    pet = get_object_or_404(Pet, pet_id=pet_id, user=request.user)
    if request.method == "POST":
        pet.delete()
    return redirect("pets:list")

@login_required
def pet_photo_delete(request, pet_id):
    """사진만 지운다. 화면 이동 없이 응답만 돌려준다."""
    pet = get_object_or_404(Pet, pet_id=pet_id, user=request.user)
    if request.method == "POST" and pet.photo:
        pet.photo.delete(save=True)  # 파일과 DB 값을 함께 지운다
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False}, status=400)