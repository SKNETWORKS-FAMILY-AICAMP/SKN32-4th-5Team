from django.urls import path

from .views import RecordCreateView

urlpatterns = [
    path("records", RecordCreateView.as_view(), name="record-create"),
]
