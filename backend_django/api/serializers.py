from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Crossword, CrosswordEntry, PuzzleSession, AnswerSubmission, LeaderboardEntry


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "is_staff", "is_superuser"]


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="Username for login")
    password = serializers.CharField(write_only=True, help_text="Password for login")


class CrosswordEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CrosswordEntry
        fields = ["id", "number", "direction", "clue", "length", "row", "col"]  # do not expose actual answer


class CrosswordSerializer(serializers.ModelSerializer):
    entries = CrosswordEntrySerializer(many=True, read_only=True)

    class Meta:
        model = Crossword
        fields = ["id", "title", "description", "published_at", "expires_at", "is_active", "metadata", "entries"]


class CrosswordAdminEntryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrosswordEntry
        fields = ["id", "number", "direction", "clue", "answer", "row", "col", "length"]


class CrosswordAdminWriteSerializer(serializers.ModelSerializer):
    entries = CrosswordAdminEntryWriteSerializer(many=True, required=False)

    class Meta:
        model = Crossword
        fields = ["id", "title", "description", "published_at", "expires_at", "is_active", "metadata", "entries"]

    def create(self, validated_data):
        entries_data = validated_data.pop("entries", [])
        crossword = Crossword.objects.create(**validated_data)
        for e in entries_data:
            CrosswordEntry.objects.create(crossword=crossword, **e)
        return crossword

    def update(self, instance, validated_data):
        entries_data = validated_data.pop("entries", None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if entries_data is not None:
            # naive update: replace all
            instance.entries.all().delete()
            for e in entries_data:
                CrosswordEntry.objects.create(crossword=instance, **e)
        return instance


class StartSessionSerializer(serializers.Serializer):
    crossword_id = serializers.IntegerField(help_text="ID of crossword to start a session for")
    time_limit_seconds = serializers.IntegerField(required=False, default=0, help_text="0 for no limit")


class SubmissionSerializer(serializers.Serializer):
    entry_id = serializers.IntegerField(help_text="ID of crossword entry being answered")
    answer = serializers.CharField(help_text="User provided answer")


class AnswerSubmissionReadSerializer(serializers.ModelSerializer):
    entry = CrosswordEntrySerializer()

    class Meta:
        model = AnswerSubmission
        fields = ["id", "entry", "submitted_answer", "correct", "submitted_at"]


class SessionSerializer(serializers.ModelSerializer):
    crossword = CrosswordSerializer(read_only=True)
    submissions = AnswerSubmissionReadSerializer(many=True, read_only=True)
    elapsed_seconds = serializers.IntegerField(read_only=True)

    class Meta:
        model = PuzzleSession
        fields = ["id", "crossword", "started_at", "ended_at", "time_limit_seconds", "elapsed_seconds", "submissions"]


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    user = UserSerializer()
    crossword = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = LeaderboardEntry
        fields = ["id", "user", "crossword", "total_entries", "correct_count", "attempts", "fastest_seconds", "completed", "accuracy"]
