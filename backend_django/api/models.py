from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class TimestampedModel(models.Model):
    """
    Abstract model to add created_at and updated_at timestamps.
    """
    created_at = models.DateTimeField(auto_now_add=True, help_text="Record creation timestamp")
    updated_at = models.DateTimeField(auto_now=True, help_text="Record last update timestamp")

    class Meta:
        abstract = True


class Crossword(TimestampedModel):
    """
    Represents a crossword puzzle. Contains metadata and publication window.
    """
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True, help_text="When this crossword becomes available")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When this crossword is no longer available")
    is_active = models.BooleanField(default=True, help_text="Admin toggle to make crossword visible")
    # Optional JSON definition for grid/entries payload that the frontend can render quickly
    # Frontend may also fetch entries separately
    metadata = models.JSONField(default=dict, blank=True, help_text="Arbitrary metadata for UI (e.g., size, theme)")

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self) -> str:
        return self.title

    @property
    def is_currently_available(self) -> bool:
        """
        Returns True if the crossword is within its availability window and active.
        """
        now = timezone.now()
        if not self.is_active:
            return False
        if self.published_at and now < self.published_at:
            return False
        if self.expires_at and now > self.expires_at:
            return False
        return True


class CrosswordEntry(TimestampedModel):
    """
    A single answer entry in a crossword with clue and answer.
    Positioning fields allow the frontend to place the word in a grid.
    """
    crossword = models.ForeignKey(Crossword, on_delete=models.CASCADE, related_name="entries")
    number = models.PositiveIntegerField(help_text="Clue number")
    # Direction string must fit the longest choice ("across" = 6)
    direction = models.CharField(max_length=6, choices=(("across", "Across"), ("down", "Down")))
    clue = models.TextField()
    answer = models.CharField(max_length=128, help_text="Correct answer in uppercase A-Z only")
    row = models.PositiveIntegerField(help_text="Top-left row index for this entry (0-based)")
    col = models.PositiveIntegerField(help_text="Top-left col index for this entry (0-based)")
    length = models.PositiveIntegerField(help_text="Number of letters in the answer")

    class Meta:
        unique_together = (("crossword", "number", "direction"),)

    def __str__(self) -> str:
        return f"{self.crossword.title} #{self.number} {self.direction}"

    def clean_answer(self) -> str:
        """
        Normalizes the answer to uppercase alphanumeric (letters only) for comparison.
        """
        return "".join([c for c in self.answer.upper() if c.isalpha()])


class PuzzleSession(TimestampedModel):
    """
    Represents a user's timed solving session for a given crossword.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="puzzle_sessions")
    crossword = models.ForeignKey(Crossword, on_delete=models.CASCADE, related_name="puzzle_sessions")
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    time_limit_seconds = models.PositiveIntegerField(default=0, help_text="0 means no enforced time limit")

    class Meta:
        unique_together = (("user", "crossword"),)
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"Session {self.user} - {self.crossword}"

    @property
    def is_active(self) -> bool:
        return self.ended_at is None

    @property
    def elapsed_seconds(self) -> int:
        end = self.ended_at or timezone.now()
        delta = end - self.started_at
        return int(delta.total_seconds())


class AnswerSubmission(TimestampedModel):
    """
    Stores a user's submitted answer for a specific entry in a puzzle during a session.
    """
    session = models.ForeignKey(PuzzleSession, on_delete=models.CASCADE, related_name="submissions")
    entry = models.ForeignKey(CrosswordEntry, on_delete=models.CASCADE, related_name="submissions")
    submitted_answer = models.CharField(max_length=128)
    correct = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("session", "entry"),)
        ordering = ["submitted_at"]

    def __str__(self) -> str:
        return f"Submission {self.session_id}-{self.entry_id}"

    def normalized_submitted(self) -> str:
        return "".join([c for c in self.submitted_answer.upper() if c.isalpha()])


class LeaderboardEntry(TimestampedModel):
    """
    Denormalized leaderboard records per user per crossword.
    Tracks fastest completion time, accuracy, and completion status.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="leaderboard_entries")
    crossword = models.ForeignKey(Crossword, on_delete=models.CASCADE, related_name="leaderboard_entries")
    total_entries = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    fastest_seconds = models.PositiveIntegerField(default=0, help_text="0 means not completed yet")
    completed = models.BooleanField(default=False)
    accuracy = models.FloatField(default=0.0)

    class Meta:
        unique_together = (("user", "crossword"),)
        ordering = ["-completed", "fastest_seconds", "-accuracy", "-updated_at"]

    def __str__(self) -> str:
        return f"LB {self.user} - {self.crossword}"

    def recalc_accuracy(self) -> None:
        if self.total_entries > 0:
            self.accuracy = round(self.correct_count / self.total_entries, 4)
        else:
            self.accuracy = 0.0

    def update_from_session(self, session: PuzzleSession) -> None:
        """
        Update leaderboard from a session aggregate.
        """
        from django.db.models import Count, Sum

        self.total_entries = self.crossword.entries.count()
        agg = session.submissions.aggregate(
            correct_count=Sum(models.Case(models.When(correct=True, then=1), default=0, output_field=models.IntegerField())),
            attempts=Count("id"),
        )
        self.correct_count = int(agg.get("correct_count") or 0)
        self.attempts = int(agg.get("attempts") or 0)
        self.completed = self.correct_count >= self.total_entries and self.total_entries > 0 and session.ended_at is not None
        # Track fastest completion time
        if self.completed:
            elapsed = session.elapsed_seconds
            if self.fastest_seconds == 0 or (elapsed > 0 and elapsed < self.fastest_seconds):
                self.fastest_seconds = elapsed
        self.recalc_accuracy()
        self.save()
