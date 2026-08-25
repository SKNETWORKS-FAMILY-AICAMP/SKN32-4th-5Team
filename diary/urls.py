from django.urls import path

from .views import RecordCreateView, ReportView

urlpatterns = [
    path("records", RecordCreateView.as_view(), name="record-create"),
    path("report", ReportView.as_view(), name="report"),
]
