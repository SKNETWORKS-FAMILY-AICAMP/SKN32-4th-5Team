from zoneinfo import ZoneInfo

from django.utils import timezone

_KST = ZoneInfo("Asia/Seoul")


class KSTMiddleware:
    """DB·내부 계산은 UTC(TIME_ZONE 설정)를 유지하고, 템플릿에 찍히는 시각만 KST로 바꾼다.

    activate() 는 스레드 로컬이다. 되돌리지 않으면 같은 워커 스레드를 물려받는
    요청 외 작업(관리 명령·백그라운드 스레드)까지 KST 로 물든다. 응답을 만든 뒤
    반드시 deactivate() 해서 요청 경계 밖으로 새지 않게 한다.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        timezone.activate(_KST)
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
