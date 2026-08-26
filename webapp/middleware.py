from zoneinfo import ZoneInfo

from django.utils import timezone

_KST = ZoneInfo("Asia/Seoul")


class KSTMiddleware:
    """DB·내부 계산은 UTC(TIME_ZONE 설정)를 유지하고, 템플릿에 찍히는 시각만 KST로 바꾼다."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        timezone.activate(_KST)
        return self.get_response(request)
