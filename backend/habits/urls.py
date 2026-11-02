
from django.urls import path, include
from rest_framework.routers import SimpleRouter

from .views import (
    RegisterView,
    LoginView,
    CurrentUserView,
    ProfileView,
    HabitViewSet,
    LogListView,
    TodayLogsView,
    RangeLogsView,
    HeatmapView,
    WeeklyReportView,
    SuggestHabitsView,
    StatsView,
)

router = SimpleRouter(trailing_slash=False)
router.register("habits", HabitViewSet, basename="habit")

urlpatterns = [
    # Authentication
    path("auth/register", RegisterView.as_view()),
    path("auth/login", LoginView.as_view()),
    path("auth/me", CurrentUserView.as_view()),
    path("auth/profile", ProfileView.as_view()),

    # Habit logs
    path("logs", LogListView.as_view()),
    path("logs/today", TodayLogsView.as_view()),
    path("logs/range", RangeLogsView.as_view()),
    path("logs/heatmap", HeatmapView.as_view()),
    path("logs/stats", StatsView.as_view()),

    # AI features
    path("ai/weekly-report", WeeklyReportView.as_view()),
    path("ai/suggest-habits", SuggestHabitsView.as_view()),

    # Habit management
    path("", include(router.urls)),
]
