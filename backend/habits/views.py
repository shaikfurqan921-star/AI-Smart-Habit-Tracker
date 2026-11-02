
from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action

from rest_framework_simplejwt.tokens import RefreshToken

from .models import Habit, HabitLog
from .serializers import UserSerializer, HabitSerializer, HabitLogSerializer


# ---------------- AUTHENTICATION ----------------

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        name = request.data.get("name", "").strip()
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")

        if not name or not email or not password:
            return Response(
                {"message": "All fields are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(password) < 8:
            return Response(
                {"message": "Password must be at least 8 characters"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {"message": "Email already registered"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name
        )

        refresh = RefreshToken.for_user(user)

        return Response({
            "user": UserSerializer(user).data,
            "token": str(refresh.access_token),
            "refresh": str(refresh),
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")

        user_obj = User.objects.filter(email__iexact=email).first()

        if not user_obj:
            return Response(
                {"message": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = authenticate(
            request,
            username=user_obj.username,
            password=password
        )

        if user is None:
            return Response(
                {"message": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            "user": UserSerializer(user).data,
            "token": str(refresh.access_token),
            "refresh": str(refresh),
        })


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "user": UserSerializer(request.user).data
        })


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        name = request.data.get("name")

        if name is not None:
            name = name.strip()

            if not name:
                return Response(
                    {"message": "Name cannot be empty"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            request.user.first_name = name
            request.user.save()

        return Response({
            "user": UserSerializer(request.user).data
        })


# ---------------- HABIT MANAGEMENT ----------------

class HabitViewSet(viewsets.ModelViewSet):
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Habit.objects.filter(user=self.request.user)

        include_archived = (
            self.request.query_params.get("includeArchived") == "true"
        )

        if not include_archived:
            queryset = queryset.filter(is_archived=False)

        return queryset.order_by("order", "created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["put"])
    def archive(self, request, pk=None):
        habit = self.get_object()
        habit.is_archived = not habit.is_archived
        habit.save(update_fields=["is_archived", "updated_at"])

        return Response(self.get_serializer(habit).data)


# ---------------- HABIT LOGS ----------------

class LogListView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        habit_id = request.data.get("habitId")
        date_value = request.data.get("date")
        completed_date = parse_date(str(date_value)) if date_value else None

        if not habit_id or not completed_date:
            return Response(
                {"message": "habitId and a valid date are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        habit = Habit.objects.filter(
            id=habit_id,
            user=request.user
        ).first()

        if not habit:
            return Response(
                {"message": "Habit not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        log, created = HabitLog.objects.get_or_create(
            user=request.user,
            habit=habit,
            completed_date=completed_date
        )

        return Response(
            HabitLogSerializer(log).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    def delete(self, request):
        habit_id = request.data.get("habitId")
        date_value = request.data.get("date")
        completed_date = parse_date(str(date_value)) if date_value else None

        if not habit_id or not completed_date:
            return Response(
                {"message": "habitId and a valid date are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted, _ = HabitLog.objects.filter(
            user=request.user,
            habit_id=habit_id,
            habit__user=request.user,
            completed_date=completed_date
        ).delete()

        if not deleted:
            return Response(
                {"message": "Log not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class TodayLogsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()

        logs = HabitLog.objects.filter(
            user=request.user,
            completed_date=today
        ).order_by("created_at")

        return Response(HabitLogSerializer(logs, many=True).data)


class RangeLogsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start = parse_date(request.query_params.get("start", ""))
        end = parse_date(request.query_params.get("end", ""))

        if not start or not end or start > end:
            return Response(
                {"message": "Please provide valid start and end dates"},
                status=status.HTTP_400_BAD_REQUEST
            )

        logs = HabitLog.objects.filter(
            user=request.user,
            completed_date__range=(start, end)
        ).order_by("completed_date")

        return Response(HabitLogSerializer(logs, many=True).data)


class HeatmapView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        start_date = today - timedelta(days=89)

        logs = HabitLog.objects.filter(
            user=request.user,
            completed_date__range=(start_date, today)
        )

        counts = {}

        for log in logs:
            date_key = log.completed_date.isoformat()
            counts[date_key] = counts.get(date_key, 0) + 1

        result = []

        for i in range(90):
            day = start_date + timedelta(days=i)
            date_key = day.isoformat()

            result.append({
                "date": date_key,
                "count": counts.get(date_key, 0)
            })

        return Response(result)


# ---------------- AI WEEKLY REPORT ----------------

class WeeklyReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        today = timezone.localdate()
        start_date = today - timedelta(days=6)

        habits = Habit.objects.filter(
            user=request.user,
            is_archived=False
        )

        logs = HabitLog.objects.filter(
            user=request.user,
            completed_date__range=(start_date, today),
            habit__user=request.user
        ).select_related("habit")

        total_completions = logs.count()
        total_possible = 0
        habit_results = []

        for habit in habits:
            completed = logs.filter(habit=habit).count()

            if habit.frequency == "weekly":
                target = habit.target_days
            else:
                target = 7

            total_possible += target

            percentage = round(
                (completed / target) * 100
            ) if target else 0

            habit_results.append({
                "name": habit.name,
                "completed": completed,
                "target": target,
                "percentage": percentage,
            })

        completion_rate = round(
            (total_completions / total_possible) * 100
        ) if total_possible else 0

        daily_counts = {}

        for i in range(7):
            day = start_date + timedelta(days=i)
            daily_counts[day] = logs.filter(
                completed_date=day
            ).count()

        best_day = max(
            daily_counts,
            key=daily_counts.get
        ) if total_completions else None

        report = [
            "## Your Weekly Habit Report",
            "",
            f"**Period:** {start_date} to {today}",
            "",
            "### Overall Progress",
            f"- Total completions: **{total_completions}**",
            f"- Completion rate: **{completion_rate}%**",
            f"- Active habits: **{habits.count()}**",
            "",
            "### Habit Performance",
        ]

        if habit_results:
            for item in habit_results:
                report.append(
                    f"- **{item['name']}**: "
                    f"{item['completed']}/{item['target']} days "
                    f"({item['percentage']}%)"
                )
        else:
            report.append("No active habits found yet.")

        report.extend(["", "### Weekly Insights"])

        if best_day:
            report.append(
                f"- Your most productive day was "
                f"**{best_day.strftime('%A')}**."
            )
        else:
            report.append(
                "- No completed habits recorded this week yet."
            )

        if completion_rate >= 80:
            report.append(
                "- Great consistency! You are maintaining "
                "a strong habit routine."
            )
        elif completion_rate >= 50:
            report.append(
                "- Good progress! Try to complete a few more "
                "planned habits next week."
            )
        else:
            report.append(
                "- You have room to improve. Start with small, "
                "manageable daily goals."
            )

        report.extend(["", "### Suggestions"])

        if habit_results:
            weakest = min(
                habit_results,
                key=lambda item: item["percentage"]
            )

            report.append(
                f"- Give **{weakest['name']}** some attention "
                "next week."
            )
            report.append(
                "- Choose a consistent time for your daily habits."
            )
            report.append(
                "- Focus on consistency rather than perfection."
            )
        else:
            report.append(
                "- Add your first habit to begin tracking progress."
            )

        return Response({
            "content": "\n".join(report),
            "completionRate": completion_rate,
            "totalCompletions": total_completions,
        })


# ---------------- AI HABIT SUGGESTIONS ----------------

class SuggestHabitsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        goals = str(request.data.get("goals", "")).strip().lower()
        productive_time = str(
            request.data.get("productiveTime", "")
        ).strip()
        struggles = str(
            request.data.get("struggles", "")
        ).strip().lower()

        if not goals or not productive_time or not struggles:
            return Response(
                {"message": "Please answer all three questions"},
                status=status.HTTP_400_BAD_REQUEST
            )

        suggestions = [
            {
                "name": "Daily Reading",
                "category": "Learning",
                "frequency": "daily",
                "description": "Spend 15 minutes reading a book or useful article.",
                "icon": "📚",
                "reason": "Build a regular learning habit."
            },
            {
                "name": "Daily Planning",
                "category": "Productivity",
                "frequency": "daily",
                "description": "Spend 5 minutes planning your important tasks.",
                "icon": "📝",
                "reason": "Organise your day and manage your time."
            },
            {
                "name": "Evening Reflection",
                "category": "Personal Growth",
                "frequency": "daily",
                "description": "Spend 5 minutes reviewing what you learned today.",
                "icon": "🌟",
                "reason": "Understand your progress and improve consistency."
            }
        ]

        if "study" in goals or "learn" in goals:
            suggestions[0]["reason"] = (
                "Supports your goal of learning and studying regularly."
            )

        if "time" in struggles or "procrastination" in struggles:
            suggestions[1]["reason"] = (
                "Helps you organise tasks and build consistency."
            )

        if productive_time:
            for suggestion in suggestions:
                suggestion["reason"] += (
                    f" Try doing it during your productive time: "
                    f"{productive_time}."
                )

        return Response({
            "suggestions": suggestions
        })


from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action

from rest_framework_simplejwt.tokens import RefreshToken

from .models import Habit, HabitLog
from .serializers import UserSerializer, HabitSerializer, HabitLogSerializer


# ---------------- AUTHENTICATION ----------------

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        name = request.data.get("name", "").strip()
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")

        if not name or not email or not password:
            return Response(
                {"message": "All fields are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(password) < 8:
            return Response(
                {"message": "Password must be at least 8 characters"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {"message": "Email already registered"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=name
        )

        refresh = RefreshToken.for_user(user)

        return Response({
            "user": UserSerializer(user).data,
            "token": str(refresh.access_token),
            "refresh": str(refresh),
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")

        user_obj = User.objects.filter(email__iexact=email).first()

        if not user_obj:
            return Response(
                {"message": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = authenticate(
            request,
            username=user_obj.username,
            password=password
        )

        if user is None:
            return Response(
                {"message": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            "user": UserSerializer(user).data,
            "token": str(refresh.access_token),
            "refresh": str(refresh),
        })


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "user": UserSerializer(request.user).data
        })


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        name = request.data.get("name")

        if name is not None:
            name = name.strip()

            if not name:
                return Response(
                    {"message": "Name cannot be empty"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            request.user.first_name = name
            request.user.save()

        return Response({
            "user": UserSerializer(request.user).data
        })


# ---------------- HABIT MANAGEMENT ----------------

class HabitViewSet(viewsets.ModelViewSet):
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Habit.objects.filter(user=self.request.user)

        include_archived = (
            self.request.query_params.get("includeArchived") == "true"
        )

        if not include_archived:
            queryset = queryset.filter(is_archived=False)

        return queryset.order_by("order", "created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["put"])
    def archive(self, request, pk=None):
        habit = self.get_object()
        habit.is_archived = not habit.is_archived
        habit.save(update_fields=["is_archived", "updated_at"])

        return Response(self.get_serializer(habit).data)


# ---------------- HABIT LOGS ----------------

class LogListView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        habit_id = request.data.get("habitId")
        date_value = request.data.get("date")
        completed_date = parse_date(str(date_value)) if date_value else None

        if not habit_id or not completed_date:
            return Response(
                {"message": "habitId and a valid date are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        habit = Habit.objects.filter(
            id=habit_id,
            user=request.user
        ).first()

        if not habit:
            return Response(
                {"message": "Habit not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        log, created = HabitLog.objects.get_or_create(
            user=request.user,
            habit=habit,
            completed_date=completed_date
        )

        return Response(
            HabitLogSerializer(log).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    def delete(self, request):
        habit_id = request.data.get("habitId")
        date_value = request.data.get("date")
        completed_date = parse_date(str(date_value)) if date_value else None

        if not habit_id or not completed_date:
            return Response(
                {"message": "habitId and a valid date are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted, _ = HabitLog.objects.filter(
            user=request.user,
            habit_id=habit_id,
            habit__user=request.user,
            completed_date=completed_date
        ).delete()

        if not deleted:
            return Response(
                {"message": "Log not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class TodayLogsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()

        logs = HabitLog.objects.filter(
            user=request.user,
            completed_date=today
        ).order_by("created_at")

        return Response(HabitLogSerializer(logs, many=True).data)


class RangeLogsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start = parse_date(request.query_params.get("start", ""))
        end = parse_date(request.query_params.get("end", ""))

        if not start or not end or start > end:
            return Response(
                {"message": "Please provide valid start and end dates"},
                status=status.HTTP_400_BAD_REQUEST
            )

        logs = HabitLog.objects.filter(
            user=request.user,
            completed_date__range=(start, end)
        ).order_by("completed_date")

        return Response(HabitLogSerializer(logs, many=True).data)


class HeatmapView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        start_date = today - timedelta(days=89)

        logs = HabitLog.objects.filter(
            user=request.user,
            completed_date__range=(start_date, today)
        )

        counts = {}

        for log in logs:
            date_key = log.completed_date.isoformat()
            counts[date_key] = counts.get(date_key, 0) + 1

        result = []

        for i in range(90):
            day = start_date + timedelta(days=i)
            date_key = day.isoformat()

            result.append({
                "date": date_key,
                "count": counts.get(date_key, 0)
            })

        return Response(result)


# ---------------- AI WEEKLY REPORT ----------------

class WeeklyReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        today = timezone.localdate()
        start_date = today - timedelta(days=6)

        habits = Habit.objects.filter(
            user=request.user,
            is_archived=False
        )

        logs = HabitLog.objects.filter(
            user=request.user,
            completed_date__range=(start_date, today),
            habit__user=request.user
        ).select_related("habit")

        total_completions = logs.count()
        total_possible = 0
        habit_results = []

        for habit in habits:
            completed = logs.filter(habit=habit).count()

            if habit.frequency == "weekly":
                target = habit.target_days
            else:
                target = 7

            total_possible += target

            percentage = round(
                (completed / target) * 100
            ) if target else 0

            habit_results.append({
                "name": habit.name,
                "completed": completed,
                "target": target,
                "percentage": percentage,
            })

        completion_rate = round(
            (total_completions / total_possible) * 100
        ) if total_possible else 0

        daily_counts = {}

        for i in range(7):
            day = start_date + timedelta(days=i)
            daily_counts[day] = logs.filter(
                completed_date=day
            ).count()

        best_day = max(
            daily_counts,
            key=daily_counts.get
        ) if total_completions else None

        report = [
            "## Your Weekly Habit Report",
            "",
            f"**Period:** {start_date} to {today}",
            "",
            "### Overall Progress",
            f"- Total completions: **{total_completions}**",
            f"- Completion rate: **{completion_rate}%**",
            f"- Active habits: **{habits.count()}**",
            "",
            "### Habit Performance",
        ]

        if habit_results:
            for item in habit_results:
                report.append(
                    f"- **{item['name']}**: "
                    f"{item['completed']}/{item['target']} days "
                    f"({item['percentage']}%)"
                )
        else:
            report.append("No active habits found yet.")

        report.extend(["", "### Weekly Insights"])

        if best_day:
            report.append(
                f"- Your most productive day was "
                f"**{best_day.strftime('%A')}**."
            )
        else:
            report.append(
                "- No completed habits recorded this week yet."
            )

        if completion_rate >= 80:
            report.append(
                "- Great consistency! You are maintaining "
                "a strong habit routine."
            )
        elif completion_rate >= 50:
            report.append(
                "- Good progress! Try to complete a few more "
                "planned habits next week."
            )
        else:
            report.append(
                "- You have room to improve. Start with small, "
                "manageable daily goals."
            )

        report.extend(["", "### Suggestions"])

        if habit_results:
            weakest = min(
                habit_results,
                key=lambda item: item["percentage"]
            )

            report.append(
                f"- Give **{weakest['name']}** some attention "
                "next week."
            )
            report.append(
                "- Choose a consistent time for your daily habits."
            )
            report.append(
                "- Focus on consistency rather than perfection."
            )
        else:
            report.append(
                "- Add your first habit to begin tracking progress."
            )

        return Response({
            "content": "\n".join(report),
            "completionRate": completion_rate,
            "totalCompletions": total_completions,
        })


# ---------------- AI HABIT SUGGESTIONS ----------------

class SuggestHabitsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        goals = str(request.data.get("goals", "")).strip().lower()
        productive_time = str(
            request.data.get("productiveTime", "")
        ).strip()
        struggles = str(
            request.data.get("struggles", "")
        ).strip().lower()

        if not goals or not productive_time or not struggles:
            return Response(
                {"message": "Please answer all three questions"},
                status=status.HTTP_400_BAD_REQUEST
            )

        suggestions = [
            {
                "name": "Daily Reading",
                "category": "Learning",
                "frequency": "daily",
                "description": "Spend 15 minutes reading a book or useful article.",
                "icon": "📚",
                "reason": "Build a regular learning habit."
            },
            {
                "name": "Daily Planning",
                "category": "Productivity",
                "frequency": "daily",
                "description": "Spend 5 minutes planning your important tasks.",
                "icon": "📝",
                "reason": "Organise your day and manage your time."
            },
            {
                "name": "Evening Reflection",
                "category": "Personal Growth",
                "frequency": "daily",
                "description": "Spend 5 minutes reviewing what you learned today.",
                "icon": "🌟",
                "reason": "Understand your progress and improve consistency."
            }
        ]

        if "study" in goals or "learn" in goals:
            suggestions[0]["reason"] = (
                "Supports your goal of learning and studying regularly."
            )

        if "time" in struggles or "procrastination" in struggles:
            suggestions[1]["reason"] = (
                "Helps you organise tasks and build consistency."
            )

        if productive_time:
            for suggestion in suggestions:
                suggestion["reason"] += (
                    f" Try doing it during your productive time: "
                    f"{productive_time}."
                )

        return Response({
            "suggestions": suggestions
        })


# ---------------- HABIT STATISTICS ----------------

class StatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        start_date = today - timedelta(days=29)

        habits = Habit.objects.filter(
            user=request.user,
            is_archived=False
        )

        per_habit = []

        for habit in habits:
            all_dates = set(
                HabitLog.objects.filter(
                    user=request.user,
                    habit=habit
                ).values_list("completed_date", flat=True)
            )

            completions_30d = sum(
                1 for day in all_dates
                if start_date <= day <= today
            )

            # Calculate longest streak
            longest_streak = 0
            current_count = 0
            previous_date = None

            for day in sorted(all_dates):
                if previous_date == day - timedelta(days=1):
                    current_count += 1
                else:
                    current_count = 1

                longest_streak = max(
                    longest_streak,
                    current_count
                )
                previous_date = day

            # Calculate current streak
            current_streak = 0

            if all_dates:
                latest_date = max(all_dates)

                if latest_date >= today - timedelta(days=1):
                    check_date = latest_date

                    while check_date in all_dates:
                        current_streak += 1
                        check_date -= timedelta(days=1)

            per_habit.append({
                "habitId": str(habit.id),
                "name": habit.name,
                "icon": habit.icon,
                "color": habit.color,
                "currentStreak": current_streak,
                "longestStreak": longest_streak,
                "completions30d": completions_30d,
            })

        return Response({
            "perHabit": per_habit
        })
