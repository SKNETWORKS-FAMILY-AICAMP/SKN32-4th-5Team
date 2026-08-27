from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
from pets.models import Pet
from .models import ChatSession, TRIAGE_MAP


@login_required
def chat_room(request):
    """채팅 화면. pet_id 쿼리스트링으로 특정 pet 선택, 없으면 첫 pet 자동."""
    pet_id = request.GET.get("pet_id") or request.session.get("active_pet_id")
    pet = None
    if pet_id:
        pet = Pet.objects.filter(pet_id=pet_id, user=request.user).first()
    if pet is None:
        pet = request.user.pets.first()
        if pet is None:
            return redirect("pets:create")
    request.session["active_pet_id"] = str(pet.pet_id)
    return render(request, "chat/room.html", {"pet": pet})


@login_required
def session_list(request):
    my_pet_ids = list(request.user.pets.values_list('pet_id', flat=True))
    sessions = ChatSession.objects.filter(pet_id__in=my_pet_ids).order_by('-created_at')
    items = []
    for s in sessions:
        first = s.messages.filter(role='user').first()
        top = s.messages.exclude(triage_level=None).order_by('-triage_level').first()
        label, css = TRIAGE_MAP.get(top.triage_level, (None, None)) if top else (None, None)
        items.append({
            'session': s,
            'preview': first.content if first else '(내용 없음)',
            'badge_label': label,
            'badge_css': css,
        })
    return render(request, 'chat/session_list.html', {'items': items})


@login_required
def session_detail(request, session_id):
    my_pet_ids = list(request.user.pets.values_list('pet_id', flat=True))
    session = get_object_or_404(ChatSession, pk=session_id, pet_id__in=my_pet_ids)
    return render(request, 'chat/session_detail.html',
                  {'session': session, 'messages': session.messages.all()})