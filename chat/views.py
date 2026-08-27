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
    """채팅 화면. 활성 반려동물을 정하고 **세션에 남긴다.**

    🔒 **주소로 온 `pet_id` 와 세션에 남은 `pet_id` 를 다르게 다룬다.**

    | 출처 | 잘못된 값이면 |
    |---|---|
    | `?pet_id=` — **사용자가 지목한 것** | **404.** 남의 것이거나 없는 것이다 |
    | 세션 — **우리가 넣은 것** | 조용히 버리고 첫 pet. 우리 잘못이지 사용자 잘못이 아니다 |

    2026-08-27 `lgj` 흡수에서 이 둘이 한 덩어리가 될 뻔했다. 세션에 죽은 pet id 가 남았을 때
    `/chat/` 이 404 나는 것을 막으려던 것인데, 그렇게 하면 **`?pet_id=<남의_펫>` 도 404 대신
    조용히 내 첫 pet 을 보여 준다.** `FR-07` · `FR-26`(남의 자원은 404)이 그 자리에서 무너지고,
    `TC-NFR-SEC-003` 이 통과로 확인한 것이 무효가 된다. **막으려던 것만 막는다.**
    """
    pet = None
    asked = request.GET.get("pet_id")
    if asked:
        pet = get_object_or_404(Pet, pet_id=asked, user=request.user)
    else:
        saved = request.session.get("active_pet_id")
        if saved:
            pet = Pet.objects.filter(pet_id=saved, user=request.user).first()
    if pet is None:
        pet = request.user.pets.first()
        if pet is None:
            return redirect("pets:create")
    request.session["active_pet_id"] = str(pet.pet_id)
    return render(request, "chat/room.html", {"pet": pet})


@login_required
def session_list(request):
    """활성 pet 이 있으면 그 pet 의 대화만 보인다. `?all=1` 이면 전부 본다.

    ⚠️ **범위를 좁혔으면 화면이 그렇다고 말해야 한다** (04 §8). 세션 상태에 따라
       같은 주소가 다른 범위를 보여 주는데 제목이 그대로면, 사용자는 다른 pet 의
       대화가 *사라졌다* 고 읽는다. `scoped_pet` 을 넘겨 제목이 이름을 달게 하고,
       넓히는 길(`?all=1`)도 같이 준다.
    """
    scoped_pet = None
    if request.GET.get("all") != "1":
        active = request.session.get("active_pet_id")
        if active:
            scoped_pet = request.user.pets.filter(pet_id=active).first()
    if scoped_pet is not None:
        my_pet_ids = [scoped_pet.pet_id]
    else:
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
    return render(
        request,
        'chat/session_list.html',
        {'items': items, 'scoped_pet': scoped_pet, 'pet_count': len(my_pet_ids)},
    )


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