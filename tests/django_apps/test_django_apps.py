"""Django 앱 최소 그물 — **7b-2 로 가기 전에 쳐 두는 것** (13 §5.2 · 14 §5.4).

🔴 **이 파일이 있기 전까지 CI 는 Django 코드를 한 줄도 실행하지 않았다.**

   `pyproject.toml` 의 `testpaths = ["tests"]` 밖에 `accounts/` · `pets/` · `diary/` ·
   `chat/` 이 있었고, 각 앱의 `tests.py` 는 Django 가 만들어 준 **3줄짜리 빈 파일**
   그대로였다. 테스트 666건이 초록인데 화면 코드는 **전부 미검증**이었다.

   그 사이에 결함 넷이 지나갔다 (D-108 · D-109 · D-110 · FR-30). 넷 다 사람이
   화면을 눌러 보고서야 나왔다.

## 왜 하필 이 넷인가

7b-2 는 FastAPI 의 `auth`·`users`·`pets` 라우터를 **지우는** 일이다. 지운 뒤
무엇이 망가졌는지 알려면 **지우기 전에** 그물이 있어야 한다. 그물 없이 지우면
"돌아가는 것 같다"만 남는다.

    ① 마이그레이션    D-104(계정은 Django auth.User) 가 실제로 끝났나
    ② 가입→로그인→세션  D-48 이 여기서 터졌다
    ③ 펫 소유권       **안전 요구사항이다** — 남의 펫이 보이면 사고다 (FR-07)
    ④ 기록→리포트 왕복  Django↔FastAPI 경계를 지나는 유일한 자리 (D-99)

## 실행

    pytest tests/django_apps/               # 이것만
    pytest                                  # 전체 (testpaths 에 들어 있다)

`django` extra 가 필요하다 (`pytest-django` 가 거기 들어 있다) —

    pip install -e '.[api,db,django,dev]' -c constraints.txt

없으면 `tests/conftest.py` 가 이 폴더를 **건너뛰고 그 사실을 찍는다.**
"""

from __future__ import annotations

import io
import uuid

import httpx
import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse

from pets.models import Pet

#: 이 파일 전체가 DB 를 쓴다. 하나씩 붙이는 대신 모듈에 건다.
pytestmark = pytest.mark.django_db


# ── ① 마이그레이션 ──────────────────────────────────────────────


class Test마이그레이션이_깨끗한_DB_에서_끝까지_돈다:
    """13 §5.2 ① · 🔒 **D-104 완료 판정.**

    `pytest-django` 는 테스트 DB 를 만들 때 이미 `migrate` 를 돌린다. 그래서
    **이 클래스의 테스트가 하나라도 수집되면 마이그레이션은 이미 통과한 것이다.**
    그래도 명시적으로 적는 이유 — 통과 사실이 `pytest` 출력에 이름으로 남아야
    다음 사람이 *"마이그레이션은 누가 보나"* 를 안 묻는다.
    """

    def test_모든_앱의_표가_만들어졌다(self, django_db_setup):
        from django.db import connection

        tables = set(connection.introspection.table_names())
        # `db_table` 로 이름을 못박은 것들이다 — 이름이 바뀌면 3차 데이터와 끊긴다.
        for name in ("pets", "diary_entries", "auth_user", "django_session"):
            assert name in tables, f"{name} 표가 없다 — 마이그레이션을 본다"

    def test_모델과_마이그레이션이_어긋나지_않았다(self):
        """🔴 **모델만 고치고 `makemigrations` 를 안 한 상태를 잡는다.**

        이게 없으면 로컬에서는 잘 도는데(개발 DB 에 이미 컬럼이 있으므로)
        **배포에서만** `column not found` 로 죽는다. 그때는 이미 늦다.
        """
        out = io.StringIO()
        try:
            call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=out)
        except SystemExit:  # --check 는 어긋나면 SystemExit(1) 로 나간다
            pytest.fail(
                "모델과 마이그레이션이 어긋났다 — `python manage.py makemigrations` 를 "
                f"돌리고 나온 파일을 커밋한다.\n{out.getvalue()}"
            )


# ── ② 가입 → 로그인 → 세션 ──────────────────────────────────────


class Test가입하고_로그인하면_세션이_유지된다:
    """13 §5.2 ② · UC-01 · UC-02. **D-48 이 여기서 터졌다.**"""

    def test_가입하면_바로_로그인된_상태로_채팅으로_간다(self, client):
        r = client.post(
            reverse("accounts:signup"),
            {"username": "tester1", "password": "hunter2secret", "password2": "hunter2secret"},
        )
        assert r.status_code == 302
        # 🔒 `LOGIN_REDIRECT_URL` 이 아니라 뷰가 직접 정한 자리다 (`accounts/views.py`).
        #    `docs/11` 2쪽과 6쪽이 이 값에서 어긋나 있었다 — 실물은 `/chat/` 이다.
        assert r["Location"] == "/chat/"
        assert client.session.get("_auth_user_id"), "가입 직후인데 세션이 비었다"

    def test_로그인하면_세션이_다음_요청까지_간다(self, client):
        User.objects.create_user(username="tester2", password="hunter2secret")

        r = client.post(
            reverse("accounts:login"), {"username": "tester2", "password": "hunter2secret"}
        )
        assert r.status_code == 302

        # **다음 요청**에서도 로그인 상태여야 한다 — 이것이 "세션 유지" 의 뜻이다.
        r2 = client.get(reverse("pets:list"))
        assert r2.status_code in (200, 302)
        assert (
            r2.status_code != 302 or "/accounts/login/" not in r2["Location"]
        ), "로그인했는데 다음 요청이 로그인 화면으로 돌아갔다 — 세션이 안 붙었다"

    def test_비밀번호가_틀리면_세션이_안_생긴다(self, client):
        User.objects.create_user(username="tester3", password="hunter2secret")

        r = client.post(reverse("accounts:login"), {"username": "tester3", "password": "wrong"})
        assert r.status_code == 200, "틀린 비밀번호인데 넘어갔다"
        assert not client.session.get("_auth_user_id")

    def test_로그아웃은_POST_로만_받는다(self, client):
        """🔒 FR-30. GET 으로 열리면 `<img src=…/logout/>` 한 줄로 남을 로그아웃시킨다."""
        User.objects.create_user(username="tester4", password="hunter2secret")
        client.login(username="tester4", password="hunter2secret")

        assert client.get(reverse("accounts:logout")).status_code == 405
        assert client.session.get("_auth_user_id"), "GET 이 405 인데 세션이 지워졌다"

        assert client.post(reverse("accounts:logout")).status_code == 302
        assert not client.session.get("_auth_user_id")


# ── ③ 펫 소유권 ─────────────────────────────────────────────────


def _make_pet(user: User, name: str = "콩이") -> Pet:
    return Pet.objects.create(
        pet_id=uuid.uuid4().hex, user=user, name=name, species="dog", size="small"
    )


class Test남의_반려동물은_보이지_않는다:
    """13 §5.2 ③ · FR-06 · FR-07. **안전 요구사항이다 — 편의 기능이 아니다.**"""

    @pytest.fixture
    def 두_사람(self):
        a = User.objects.create_user(username="ownerA", password="hunter2secret")
        b = User.objects.create_user(username="ownerB", password="hunter2secret")
        return a, b, _make_pet(a, "A의개"), _make_pet(b, "B의개")

    def test_목록에는_자기_것만_나온다(self, client, 두_사람):
        a, _b, pet_a, pet_b = 두_사람
        client.force_login(a)

        body = client.get(reverse("pets:list")).content.decode()
        assert pet_a.name in body
        assert pet_b.name not in body, "남의 반려동물이 목록에 보인다"

    def test_남의_펫_주소로_채팅에_들어가면_404(self, client, 두_사람):
        """🔒 TC-NFR-SEC-003. **403 이 아니라 404 다** — 있는지 없는지도 알려 주지 않는다."""
        a, _b, _pet_a, pet_b = 두_사람
        client.force_login(a)

        assert client.get(f"/chat/?pet_id={pet_b.pet_id}").status_code == 404

    def test_남의_펫으로_기록을_쓰면_404(self, client, 두_사람):
        a, _b, _pet_a, pet_b = 두_사람
        client.force_login(a)

        r = client.post(
            "/api/records",
            {
                "pet_id": pet_b.pet_id,
                "species": "dog",
                "recorded_at": "2026-08-27T09:00:00+00:00",
                "weight_kg": 5.0,
            },
            content_type="application/json",
        )
        assert r.status_code == 404, "남의 반려동물에 기록이 써졌다"

    def test_DB_에게_등록순으로_달라고_말한다(self):
        """🔴 **결과를 보는 것으로는 이걸 못 잡는다.**

        화면 셋이 `.first()` 로 *"첫 반려동물"* 을 고른다 (`chat/views.py` ·
        `chat/context_processors.py` · `diary/views.py`). `pet_id` 는 랜덤 UUID 라
        정렬을 안 걸면 DB 가 편한 순서로 준다. 권소라의 TC-FR-CHAT-006 이
        *"지금은 등록순과 우연히 일치하나 신규 등록 시 뒤집힐 수 있음"* 이라고 적었다.

        ⚠️ **처음에 이 테스트를 결과로 썼다가 가짜 초록을 만들었다.**
           `assert list(...) == [먼저, 나중]` 로 썼더니 `ordering` 을 **떼어도 통과**했다 —
           sqlite 가 마침 삽입 순서(rowid)로 돌려주기 때문이다. 권소라가 말한
           *"우연히 일치"* 를 테스트가 그대로 재현한 셈이고, **빨강이 될 수 없는 초록**은
           없는 것보다 나쁘다. 있다고 믿게 만들기 때문이다.

           그래서 **DB 에게 무엇을 시켰는지**를 본다. 이건 sqlite 든 MySQL 이든 같다.
        """
        u = User.objects.create_user(username="ordering", password="hunter2secret")
        first, second = _make_pet(u, "먼저"), _make_pet(u, "나중")

        assert Pet._meta.ordering == ["created_at"], "Pet.Meta.ordering 이 사라졌다"

        sql = str(Pet.objects.filter(user=u).query)
        assert (
            "ORDER BY" in sql.upper()
        ), f"정렬 없이 질의한다 — DB 가 주는 순서는 등록순이 아니다.\n{sql}"

        # 여기까지 왔으면 순서는 **약속된 것**이다. 그 약속이 실제로 지켜지는지도 본다.
        assert list(Pet.objects.filter(user=u)) == [first, second]
        assert Pet.objects.filter(user=u).first() == first


# ── ④ 기록 → 리포트 왕복 ────────────────────────────────────────


class Test기록을_쓰면_리포트가_돌려준다:
    """13 §5.2 ④ · FR-09 · FR-20 · 12 §4.4.

    **Django↔FastAPI 경계를 지나는 유일한 자리다.** 추론 서비스는 띄우지 않는다 —
    `INFERENCE_INTERNAL_URL` 이 닫힌 포트라 호출은 즉시 거절되고, 그 거절을
    **삼키지 않고 폴백 문구로 드러내는지**를 본다 (D-58 · 04 §8).
    """

    @pytest.fixture
    def 로그인한_주인(self, client):
        u = User.objects.create_user(username="diarist", password="hunter2secret")
        client.force_login(u)
        return u, _make_pet(u)

    def _기록(self, client, pet, date: str, weight: float):
        return client.post(
            "/api/records",
            {
                "pet_id": pet.pet_id,
                "species": "dog",
                "recorded_at": f"{date}T09:00:00+00:00",
                "weight_kg": weight,
                "meals": ["사료"],
                "symptoms": [],
            },
            content_type="application/json",
        )

    def test_쓴_기록이_리포트에_그대로_나온다(self, client, 로그인한_주인):
        _u, pet = 로그인한_주인
        assert self._기록(client, pet, "2026-08-25", 5.0).status_code in (200, 201)
        assert self._기록(client, pet, "2026-08-26", 5.2).status_code in (200, 201)

        r = client.get(f"/api/report?pet_id={pet.pet_id}")
        assert r.status_code == 200
        body = r.json()
        assert len(body["timeline"]) == 2
        assert [row["weight_kg"] for row in body["timeline"]] == [5.0, 5.2]

    def test_요약은_달라고_할_때만_만든다(self, client, 로그인한_주인, monkeypatch):
        """🔴 **D-109.** 예전에는 화면을 열 때마다 LLM 요약이 나갔고 결과는 버려졌다.

        2026-08-27 시연 로그에서 2분 동안 9번 호출됐는데 다운로드는 0번이었다.
        **몇 번 불렸는지를 세는 테스트가 없어서** 아무도 몰랐다.
        """
        called = []

        def 세면서_거절(*a, **kw):
            called.append(1)
            raise httpx.ConnectError("테스트: 추론 서비스는 안 떴다")

        _u, pet = 로그인한_주인
        monkeypatch.setattr(httpx, "post", 세면서_거절)
        self._기록(client, pet, "2026-08-25", 5.0)

        client.get(f"/api/report?pet_id={pet.pet_id}")
        assert called == [], "요약을 달라고 안 했는데 추론 서비스를 불렀다 (D-109)"

        client.get(f"/api/report?pet_id={pet.pet_id}&summary=1")
        assert len(called) == 1, "summary=1 인데 안 불렀다"

    def test_추론이_안_떠_있으면_숨기지_않고_말한다(self, client, 로그인한_주인):
        """폴백을 숨기지 않는다 (D-58). **기록 원본은 그대로 나가야 한다.**"""
        _u, pet = 로그인한_주인
        self._기록(client, pet, "2026-08-25", 5.0)

        body = client.get(f"/api/report?pet_id={pet.pet_id}&summary=1").json()
        assert body["summary_by"] == "code", "추론이 없는데 LLM 이 만든 척한다"
        assert body["summary"], "실패했는데 빈 문자열이라 화면이 이유를 모른다"
        assert len(body["timeline"]) == 1, "요약이 실패했다고 기록까지 잃었다"

    def test_요약을_안_부르면_이유가_남는다(self, client, 로그인한_주인):
        """빈 문자열이 아니라 `skipped` 다 — 화면이 *"실패했나"* 로 읽지 않게 (D-58)."""
        _u, pet = 로그인한_주인
        self._기록(client, pet, "2026-08-25", 5.0)

        body = client.get(f"/api/report?pet_id={pet.pet_id}").json()
        assert body["summary_by"] == "skipped"

    def test_로그인하지_않으면_리포트를_못_본다(self, client, 로그인한_주인):
        _u, pet = 로그인한_주인
        client.logout()

        assert client.get(f"/api/report?pet_id={pet.pet_id}").status_code in (401, 403)


# ── 덤: 평문 접근 ───────────────────────────────────────────────


def test_평문_http_는_https_로_넘어간다(http_client):
    """🔒 `SECURE_SSL_REDIRECT` (settings.py:217) 가 실제로 걸리는지.

    위 테스트들이 전부 https 클라이언트를 쓰기 때문에(`conftest.py`), **평문이
    막히는지는 아무도 안 본다.** 그 자리를 여기서 하나 막는다 — 안 그러면
    설정이 꺼져도 초록으로 남는다.
    """
    r = http_client.get("/accounts/login/")
    assert r.status_code == 301
    assert r["Location"].startswith("https://")
