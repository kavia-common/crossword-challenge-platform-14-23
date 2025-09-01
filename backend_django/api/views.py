from django.contrib.auth import login as django_login, logout as django_logout, authenticate
from django.contrib.auth.models import User
from django.db import transaction, models as dj_models
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets, mixins
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Crossword, CrosswordEntry, PuzzleSession, AnswerSubmission, LeaderboardEntry
from .serializers import (
    LoginSerializer,
    UserSerializer,
    CrosswordSerializer,
    CrosswordAdminWriteSerializer,
    SessionSerializer,
    SubmissionSerializer,
    StartSessionSerializer,
    LeaderboardEntrySerializer,
)


# PUBLIC_INTERFACE
@api_view(['GET'])
def health(request):
    """Health check endpoint for CI test and readiness."""
    return Response({"message": "Server is up!"})


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Skips CSRF enforcement for API views where session auth is used.
    Keep in mind CSRF is recommended for browser session-based auth, but
    for this exercise we disable to simplify.
    """
    def enforce_csrf(self, request):
        return  # disable CSRF checks


# PUBLIC_INTERFACE
class AuthLoginView(APIView):
    """
    Login endpoint using Django session authentication.
    """
    authentication_classes = [CsrfExemptSessionAuthentication, BasicAuthentication]
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_id="auth_login",
        operation_summary="User login",
        operation_description="Authenticate with username and password. Creates a session.",
        request_body=LoginSerializer,
        responses={200: UserSerializer, 400: "Invalid credentials"},
        tags=["auth"],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(username=serializer.validated_data['username'], password=serializer.validated_data['password'])
        if not user:
            return Response({"detail": "Invalid username or password"}, status=status.HTTP_400_BAD_REQUEST)
        django_login(request, user)
        return Response(UserSerializer(user).data, status=200)


# PUBLIC_INTERFACE
class AuthLogoutView(APIView):
    """
    Logout endpoint: clears the current session.
    """
    authentication_classes = [CsrfExemptSessionAuthentication, BasicAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_id="auth_logout",
        operation_summary="User logout",
        operation_description="Logs out the current user and clears session.",
        tags=["auth"],
        responses={204: "Logged out"},
    )
    def post(self, request):
        django_logout(request)
        return Response(status=204)


# PUBLIC_INTERFACE
class MeView(APIView):
    """
    Returns the current logged-in user.
    """
    authentication_classes = [CsrfExemptSessionAuthentication, BasicAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_id="auth_me",
        operation_summary="Get current user",
        operation_description="Returns information on the authenticated user.",
        tags=["auth"],
        responses={200: UserSerializer},
    )
    def get(self, request):
        return Response(UserSerializer(request.user).data)


# PUBLIC_INTERFACE
class CrosswordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read endpoints for crosswords available to users.
    """
    authentication_classes = [CsrfExemptSessionAuthentication, BasicAuthentication]
    permission_classes = [permissions.AllowAny]
    queryset = Crossword.objects.all()
    serializer_class = CrosswordSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # filter only currently available crosswords
        now = timezone.now()
        return qs.filter(is_active=True).filter(dj_models.Q(published_at__isnull=True) | dj_models.Q(published_at__lte=now)).filter(
            dj_models.Q(expires_at__isnull=True) | dj_models.Q(expires_at__gte=now)
        ).order_by("-published_at", "-created_at")

    @swagger_auto_schema(
        operation_id="crossword_list",
        operation_summary="List available crosswords",
        tags=["crosswords"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_id="crossword_retrieve",
        operation_summary="Get crossword detail",
        tags=["crosswords"],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


# PUBLIC_INTERFACE
class CrosswordAdminViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD for crosswords with nested entries.
    Only staff members are allowed.
    """
    authentication_classes = [CsrfExemptSessionAuthentication, BasicAuthentication]
    permission_classes = [permissions.IsAdminUser]
    queryset = Crossword.objects.all()
    serializer_class = CrosswordAdminWriteSerializer

    @swagger_auto_schema(operation_summary="Admin list crosswords", tags=["admin"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Admin create crossword", tags=["admin"])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Admin retrieve crossword", tags=["admin"])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Admin update crossword", tags=["admin"])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Admin partial update crossword", tags=["admin"])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary="Admin delete crossword", tags=["admin"])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


def _get_or_create_leaderboard(user: User, crossword: Crossword) -> LeaderboardEntry:
    lb, _ = LeaderboardEntry.objects.get_or_create(user=user, crossword=crossword)
    return lb


def _normalize(s: str) -> str:
    return "".join([c for c in (s or "").upper() if c.isalpha()])


# PUBLIC_INTERFACE
class SessionViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.ListModelMixin):
    """
    Manage puzzle sessions per user.
    """
    authentication_classes = [CsrfExemptSessionAuthentication, BasicAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    queryset = PuzzleSession.objects.select_related("crossword", "user").all()
    serializer_class = SessionSerializer

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    @swagger_auto_schema(
        operation_id="sessions_start",
        operation_summary="Start or resume a session",
        request_body=StartSessionSerializer,
        responses={200: SessionSerializer},
        tags=["sessions"],
    )
    @action(methods=["post"], detail=False, url_path="start")
    def start_session(self, request):
        """
        Start a session for a crossword, or return existing session if not ended.
        """
        serializer = StartSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        crossword = get_object_or_404(Crossword, id=serializer.validated_data["crossword_id"])
        session, created = PuzzleSession.objects.get_or_create(
            user=request.user,
            crossword=crossword,
            defaults={"time_limit_seconds": serializer.validated_data.get("time_limit_seconds", 0)},
        )
        if not created and session.ended_at is None:
            # already active
            pass
        else:
            # if previous ended, start a new session
            if not created and session.ended_at is not None:
                session.started_at = timezone.now()
                session.ended_at = None
                session.time_limit_seconds = serializer.validated_data.get("time_limit_seconds", 0)
                session.save()

        return Response(SessionSerializer(session).data, status=200)

    @swagger_auto_schema(
        operation_id="sessions_end",
        operation_summary="End current session",
        responses={200: SessionSerializer},
        tags=["sessions"],
    )
    @action(methods=["post"], detail=True, url_path="end")
    def end_session(self, request, pk=None):
        """
        End session and update leaderboard.
        """
        session = self.get_object()
        if session.ended_at is None:
            session.ended_at = timezone.now()
            session.save()
        lb = _get_or_create_leaderboard(request.user, session.crossword)
        lb.update_from_session(session)
        return Response(SessionSerializer(session).data, status=200)

    @swagger_auto_schema(
        operation_id="sessions_submit",
        operation_summary="Submit an answer",
        request_body=SubmissionSerializer,
        tags=["sessions"],
        responses={200: "Submission stored"},
    )
    @action(methods=["post"], detail=True, url_path="submit")
    @transaction.atomic
    def submit_answer(self, request, pk=None):
        """
        Submit an answer for an entry within a session. Upserts a submission for a given entry.
        """
        session = self.get_object()
        if session.ended_at is not None:
            return Response({"detail": "Session has ended"}, status=400)

        sub_ser = SubmissionSerializer(data=request.data)
        sub_ser.is_valid(raise_exception=True)
        entry = get_object_or_404(CrosswordEntry, id=sub_ser.validated_data["entry_id"], crossword=session.crossword)

        normalized_correct = _normalize(entry.answer)
        normalized_sub = _normalize(sub_ser.validated_data["answer"])
        is_correct = normalized_correct == normalized_sub and len(normalized_correct) == entry.length

        submission, created = AnswerSubmission.objects.update_or_create(
            session=session,
            entry=entry,
            defaults={
                "submitted_answer": sub_ser.validated_data["answer"],
                "correct": is_correct,
            },
        )

        # Update leaderboard progressively
        lb = _get_or_create_leaderboard(request.user, session.crossword)
        lb.update_from_session(session)

        return Response(
            {
                "entry_id": entry.id,
                "correct": is_correct,
                "submitted_answer": submission.submitted_answer,
            },
            status=200,
        )


# PUBLIC_INTERFACE
class LeaderboardView(APIView):
    """
    Public leaderboard for a crossword, sorted by completion and fastest time.
    """
    authentication_classes = [CsrfExemptSessionAuthentication, BasicAuthentication]
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        operation_id="leaderboard_get",
        operation_summary="Get leaderboard for a crossword",
        manual_parameters=[
            openapi.Parameter("crossword_id", openapi.IN_QUERY, description="Crossword ID", type=openapi.TYPE_INTEGER, required=True)
        ],
        tags=["leaderboard"],
        responses={200: LeaderboardEntrySerializer(many=True)},
    )
    def get(self, request):
        crossword_id = request.query_params.get("crossword_id")
        if not crossword_id:
            return Response({"detail": "crossword_id required"}, status=400)
        crossword = get_object_or_404(Crossword, id=crossword_id)
        qs = LeaderboardEntry.objects.filter(crossword=crossword).select_related("user").order_by(
            "-completed", "fastest_seconds", "-accuracy", "attempts"
        )[:100]
        data = LeaderboardEntrySerializer(qs, many=True).data
        return Response(data, status=200)
