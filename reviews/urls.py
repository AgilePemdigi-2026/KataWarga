from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("reviews/import/", views.import_csv_view, name="import_csv"),
    path("reviews/import/template/", views.csv_template_view, name="csv_template"),
]
