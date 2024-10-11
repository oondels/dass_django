from django.urls import path
from . import views
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)


urlpatterns = [
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("", views.home, name="home"),
    path("lista_func", views.lista_funcionarios, name="lista_funcionarios"),
    path("download", views.download_file, name="download_file"),
    path("login", views.login, name="login"),
    path("logout", views.logout, name="logout"),
]
