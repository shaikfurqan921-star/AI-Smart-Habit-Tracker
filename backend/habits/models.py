
from django.db import models
from django.contrib.auth.models import User


class Habit(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="habits"
    )

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    category = models.CharField(max_length=100, default="Other")

    frequency = models.CharField(
        max_length=20,
        choices=[
            ("daily", "Daily"),
            ("weekly", "Weekly"),
        ],
        default="daily"
    )

    target_days = models.PositiveIntegerField(default=7)

    color = models.CharField(max_length=20, default="#6366f1")
    icon = models.CharField(max_length=20, default="🎯")

    is_archived = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class HabitLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="habit_logs"
    )

    habit = models.ForeignKey(
        Habit,
        on_delete=models.CASCADE,
        related_name="logs"
    )

    completed_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["habit", "completed_date"],
                name="unique_habit_completion_per_day"
            )
        ]

    def __str__(self):
        return f"{self.habit.name} - {self.completed_date}"
