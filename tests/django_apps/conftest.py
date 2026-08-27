"""Django 앱 테스트 공용 설정.

🔴 **테스트 요청을 https 로 보낸다.**

   실물 설정은 `DEBUG=false` 일 때 `SECURE_SSL_REDIRECT` 를 켠다 (`settings.py:217`).
   그래서 평문 http 요청은 무엇을 부르든 **301 로 https 에 넘겨진다** — 뷰까지 가지도
   못한다. 처음에 이걸 모르고 12건이 전부 `assert 301 in (401, 403)` 로 죽었다.

   길이 둘이었다 —

     ① 테스트 설정에서 `SECURE_SSL_REDIRECT = False` 로 끈다
     ② 테스트 클라이언트를 https 로 보낸다   ← **이쪽을 골랐다**

   ①은 편하지만 **테스트가 배포와 다른 설정에서 돈다.** `SESSION_COOKIE_SECURE` ·
   `CSRF_COOKIE_SECURE` 도 같이 무력화되므로, 쿠키가 secure 로 나가는지를
   영영 확인하지 못한다. 검사를 통과시키려고 검사 대상을 바꾸는 셈이다.

   ②는 실물 설정 그대로 돌면서 **배포와 같은 경로**(https)를 쓴다. 대신 평문 접근이
   실제로 막히는지는 `test_평문_http_는_https_로_넘어간다` 가 따로 못박는다.
"""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.fixture
def client() -> Client:
    """pytest-django 의 `client` 를 **nginx 를 지나온 요청**처럼 만든다.

    이 픽스처가 없으면 모든 요청이 301 에서 멈춘다. 위 머리말 참조.

    🔴 **`Client(secure=True)` 로는 안 된다.** 그건 환경 기본값에 `secure` 라는
       쓸모없는 키를 넣을 뿐이고 `wsgi.url_scheme` 은 http 로 남는다 (실측).

       대신 `X-Forwarded-Proto: https` 를 보낸다 — 이것이 **배포에서 실제로 일어나는
       일**이다. nginx 가 이 헤더를 붙이고, Django 는 `SECURE_PROXY_SSL_HEADER`
       (settings.py:230) 로 그걸 읽는다. 테스트가 그 경로를 그대로 탄다.
    """
    return Client(HTTP_X_FORWARDED_PROTO="https")


@pytest.fixture
def http_client() -> Client:
    """평문 http 클라이언트. **리다이렉트가 실제로 걸리는지 보는 데만 쓴다.**"""
    return Client(secure=False)
