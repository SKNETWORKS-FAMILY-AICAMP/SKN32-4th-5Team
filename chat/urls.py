from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('chat/', views.chat_room, name='room'),
    path('history/', views.session_list, name='session_list'),
    path('history/<str:session_id>/', views.session_detail, name='session_detail'),
]