
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Habit, HabitLog


class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'avatar']

    def get_name(self, obj):
        return obj.first_name or obj.username

    def get_avatar(self, obj):
        name = obj.first_name or obj.username
        return name[0].upper() if name else "U"


class HabitSerializer(serializers.ModelSerializer):
    _id = serializers.IntegerField(source='id', read_only=True)
    userId = serializers.IntegerField(source='user_id', read_only=True)

    targetDays = serializers.IntegerField(
        source='target_days',
        required=False,
        default=7
    )

    isArchived = serializers.BooleanField(
        source='is_archived',
        required=False,
        default=False
    )

    createdAt = serializers.DateTimeField(
        source='created_at',
        read_only=True
    )

    updatedAt = serializers.DateTimeField(
        source='updated_at',
        read_only=True
    )

    class Meta:
        model = Habit
        fields = [
            '_id',
            'userId',
            'name',
            'description',
            'category',
            'frequency',
            'targetDays',
            'color',
            'icon',
            'isArchived',
            'order',
            'createdAt',
            'updatedAt',
        ]

        read_only_fields = [
            '_id',
            'userId',
            'createdAt',
            'updatedAt'
        ]

        extra_kwargs = {
            'description': {'required': False},
            'category': {'required': False, 'default': 'Other'},
            'frequency': {'required': False, 'default': 'daily'},
            'color': {'required': False, 'default': '#6366f1'},
            'icon': {'required': False, 'default': '🎯'},
            'order': {'required': False, 'default': 0},
        }


class HabitLogSerializer(serializers.ModelSerializer):
    _id = serializers.IntegerField(source='id', read_only=True)
    userId = serializers.IntegerField(source='user_id', read_only=True)
    habitId = serializers.IntegerField(source='habit_id')
    completedDate = serializers.DateField(source='completed_date')

    class Meta:
        model = HabitLog
        fields = [
            '_id',
            'userId',
            'habitId',
            'completedDate',
        ]
        read_only_fields = ['_id', 'userId']
