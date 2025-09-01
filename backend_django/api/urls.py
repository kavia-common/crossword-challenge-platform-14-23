from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    health,
    AuthLoginView,
    AuthLogoutView,
    MeView,
    CrosswordViewSet,
    CrosswordAdminViewSet,
    SessionViewSet,
    LeaderboardView,
)

router = DefaultRouter()
router.register(r"crosswords", CrosswordViewSet, basename="crosswords")
router.register(r"admin/crosswords", CrosswordAdminViewSet, basename="admin-crosswords")
router.register(r"sessions", SessionViewSet, basename="sessions")

urlpatterns = [
    path("health/", health, name="Health"),
    path("auth/login/", AuthLoginView.as_view(), name="auth-login"),
    path("auth/logout/", AuthLogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("", include(router.urls)),
]
