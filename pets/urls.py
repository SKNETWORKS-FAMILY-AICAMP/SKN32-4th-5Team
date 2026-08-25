from django.urls import path

from . import views

app_name = "pets"

urlpatterns = [
    path("", views.pet_list, name="list"),
    path("new/", views.pet_create, name="create"),
    path("<str:pet_id>/edit/", views.pet_edit, name="edit"),
    path("<str:pet_id>/delete/", views.pet_delete, name="delete"),
    path("<str:pet_id>/photo/delete/", views.pet_photo_delete, name="photo_delete"),
]