from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect, render


def login_view(request):
    """로그인. 이미 로그인된 사용자는 프로필 목록으로 보낸다."""
    if request.user.is_authenticated:
        return redirect("/pets/")

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(request.GET.get("next") or "/pets/")
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
            return redirect("/pets/")

    return render(request, "accounts/signup.html", {"error": error})


def logout_view(request):
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