from django.contrib import admin
from .models import Crossword, CrosswordEntry, PuzzleSession, AnswerSubmission, LeaderboardEntry


@admin.register(Crossword)
class CrosswordAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "is_active", "published_at", "expires_at", "created_at")
    list_filter = ("is_active",)
    search_fields = ("title",)


@admin.register(CrosswordEntry)
class CrosswordEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "crossword", "number", "direction", "length", "row", "col")
    list_filter = ("direction", "crossword")
    search_fields = ("clue", "answer")


@admin.register(PuzzleSession)
class PuzzleSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "crossword", "started_at", "ended_at", "time_limit_seconds")
    list_filter = ("crossword", "ended_at")
    search_fields = ("user__username",)


@admin.register(AnswerSubmission)
class AnswerSubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "entry", "submitted_answer", "correct", "submitted_at")
    list_filter = ("correct", "entry__crossword")
    search_fields = ("session__user__username", "submitted_answer")


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "crossword", "completed", "fastest_seconds", "accuracy", "correct_count", "total_entries", "attempts", "updated_at")
    list_filter = ("completed", "crossword")
    search_fields = ("user__username",)
