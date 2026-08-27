from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST


def login_view(request):
    """로그인. 이미 로그인된 사용자는 프로필 목록으로 보낸다."""
    if request.user.is_authenticated:
        return redirect("/chat/")

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(request.GET.get("next") or "/chat/")
        error = "아이디 또는 비밀번호가 올바르지 않아요."

    return render(request, "accounts/login.html", {"error": error})


def signup_view(request):
    """회원가입. 성공하면 바로 로그인시킨다."""
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        if len(username) < 4:
            error = "아이디는 4자 이상이어야 해요."
        elif User.objects.filter(username=username).exists():
            error = "이미 사용 중인 아이디예요."
        elif len(password) < 8:
            error = "비밀번호는 8자 이상이어야 해요."
        elif password != password2:
            error = "비밀번호가 일치하지 않아요."
        else:
            user = User.objects.create_user(username=username, password=password)
            login(request, user)
            return redirect("/chat/")

    return render(request, "accounts/signup.html", {"error": error})


@require_POST
def logout_view(request):
    """로그아웃. **POST 로만 받는다** (FR-30).

    🔒 GET 으로 열리면 **남이 남을 로그아웃시킬 수 있다.** 공격자가 게시판이나 메일에
    `<img src="https://…/accounts/logout/">` 한 줄만 심으면, 그 글을 연 사람은 조용히
    로그아웃된다. 브라우저가 이미지를 가지러 가면서 세션 쿠키를 같이 보내기 때문이다.

    피해가 크지는 않다 — 지워지는 것은 세션뿐이다. 다만 **작업 중이던 것이 날아가고**,
    반복되면 서비스를 못 쓴다. Django 도 4.1 부터 자기 `LogoutView` 를 POST 전용으로 바꿨다.

    POST 로 오면 CSRF 토큰이 필요하고, 토큰은 우리 화면에서만 나온다.

    `@login_required` 는 **일부러 안 붙였다.** 붙이면 이미 나간 사람이 한 번 더 눌렀을 때
    `?next=/accounts/logout/` 를 달고 로그인 화면으로 갔다가, 로그인 뒤 그 주소를 GET 으로
    다시 열어 405 가 난다. 익명 요청에 `logout()` 은 그냥 아무 일도 안 하므로 그대로 둔다.
    """
    logout(request)
    return redirect("accounts:login")


def check_id(request):
    """회원가입 화면의 '중복확인' 버튼이 부르는 주소."""
    username = request.GET.get("username", "").strip()
    if len(username) < 4:
        return JsonResponse({"ok": False, "msg": "아이디는 4자 이상이어야 해요."})
    if User.objects.filter(username=username).exists():
        return JsonResponse({"ok": False, "msg": "이미 사용 중인 아이디예요."})
    return JsonResponse({"ok": True, "msg": "사용 가능한 아이디예요."})