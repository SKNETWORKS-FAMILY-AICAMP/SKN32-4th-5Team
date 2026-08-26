from django.contrib.auth.decorators import login_required
from django.db.utils import DatabaseError
from django.shortcuts import get_object_or_404, redirect, render

from pets.models import Pet

from .models import TRIAGE_MAP, ChatSession


def _unavailable(request):
    """🔴 **채팅 내역 표가 이 DB 에 없다** (2026-08-26 전체 점검 A).

    `chat/models.py` 는 `managed = False` 다 — *"표가 이미 있다"* 를 전제한다.
    그런데 **D-104 로 웹앱 DB 와 3차 DB 를 가르면서 그 표는 저쪽에 남았다.**
    게다가 쓰는 쪽은 FastAPI 의 `chat_logger` 라, 표만 옮겨도 쓰는 곳과 읽는 곳이 갈린다.

    `managed = False` 자체는 옳은 선택이었다. 무너진 것은 **그 전제**이고,
    결정 하나가 다른 결정의 전제를 조용히 지웠다. 7b(DB 통합)에서 풀린다.

    ⚠️ **500 으로 두지 않는다.** 사용자에게 스택트레이스는 아무것도 알려 주지 않고,
       *"기록이 날아갔나"* 라고 읽히게 만든다. **무엇이 없는지 말해 준다** (D-58).
       조용히 빈 목록을 그리는 것도 안 된다 — 그건 *"대화가 없다"* 는 거짓말이다.
    """
    return render(request, "chat/unavailable.html", status=503)


@login_required
def chat_room(request):
    """채팅 화면. pet_id 쿼리스트링으로 특정 pet 선택, 없으면 첫 pet 자동."""
    pet_id = request.GET.get("pet_id")
    if pet_id:
        pet = get_object_or_404(Pet, pet_id=pet_id, user=request.user)
    else:
        pet = request.user.pets.first()
        if pet is None:
            return redirect("pets:create")
    return render(request, "chat/room.html", {"pet": pet})


@login_required
def session_list(request):
    my_pet_ids = list(request.user.pets.values_list('pet_id', flat=True))
    try:
        sessions = list(
            ChatSession.objects.filter(pet_id__in=my_pet_ids).order_by('-created_at')
        )
    except DatabaseError:
        return _unavailable(request)
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
    try:
        session = get_object_or_404(ChatSession, pk=session_id, pet_id__in=my_pet_ids)
        messages = list(session.messages.all())
    except DatabaseError:
        return _unavailable(request)
    return render(request, 'chat/session_detail.html',
                  {'session': session, 'messages': messages})