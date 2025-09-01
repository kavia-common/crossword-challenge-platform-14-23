from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from .models import Crossword, CrosswordEntry, PuzzleSession, AnswerSubmission, LeaderboardEntry


class BaseAPITestCase(APITestCase):
    def setUp(self):
        # Users
        self.user = User.objects.create_user(username="user1", password="pass1234")
        self.admin = User.objects.create_user(username="admin1", password="pass1234", is_staff=True, is_superuser=True)

        # Common URLs
        self.url_health = reverse("Health")
        self.url_login = reverse("auth-login")
        self.url_logout = reverse("auth-logout")
        self.url_me = reverse("auth-me")
        self.url_leaderboard = reverse("leaderboard")

        # Routers
        # Note: DRF DefaultRouter names follow pattern: <basename>-list and <basename>-detail
        self.crosswords_list = reverse("crosswords-list")
        self.admin_crosswords_list = reverse("admin-crosswords-list")
        self.sessions_list = reverse("sessions-list")

        # Clients
        self.client_user = APIClient()
        self.client_admin = APIClient()

        # Login helpers
        self.assertTrue(self.client_user.login(username="user1", password="pass1234"))
        self.assertTrue(self.client_admin.login(username="admin1", password="pass1234"))

    def create_crossword_with_entries(self, title="Daily", is_active=True, published=True):
        now = timezone.now()
        published_at = now if published else now + timezone.timedelta(days=1)
        cw = Crossword.objects.create(
            title=title,
            description="desc",
            is_active=is_active,
            published_at=published_at,
            metadata={"rows": 3, "cols": 3},
        )
        # two entries: across and down
        e1 = CrosswordEntry.objects.create(
            crossword=cw,
            number=1,
            direction="across",
            clue="First",
            answer="CAT",
            row=0,
            col=0,
            length=3,
        )
        e2 = CrosswordEntry.objects.create(
            crossword=cw,
            number=1,
            direction="down",
            clue="Second",
            answer="CAR",
            row=0,
            col=0,
            length=3,
        )
        return cw, [e1, e2]


class HealthTests(BaseAPITestCase):
    def test_health(self):
        response = self.client.get(self.url_health)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"message": "Server is up!"})


class AuthTests(BaseAPITestCase):
    def test_login_logout_and_me(self):
        # Validate /auth/me requires auth
        response = self.client.get(self.url_me)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Login with bad creds
        response = self.client.post(self.url_login, {"username": "user1", "password": "wrong"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Login with correct creds
        response = self.client.post(self.url_login, {"username": "user1", "password": "pass1234"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "user1")

        # Now /auth/me should work using the same client (session-based)
        response = self.client.get(self.url_me)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "user1")

        # Logout
        response = self.client.post(self.url_logout)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Access after logout should be forbidden
        response = self.client.get(self.url_me)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CrosswordReadTests(BaseAPITestCase):
    def test_crossword_list_filters_availability(self):
        # One active+published, one not yet published, one inactive
        active_published, _ = self.create_crossword_with_entries(title="A", is_active=True, published=True)
        not_published, _ = self.create_crossword_with_entries(title="B", is_active=True, published=False)
        inactive, _ = self.create_crossword_with_entries(title="C", is_active=False, published=True)

        # List endpoint (AllowAny) should return only currently available crosswords
        response = self.client.get(self.crosswords_list)
        self.assertEqual(response.status_code, 200)
        ids = [c["id"] for c in response.data]
        self.assertIn(active_published.id, ids)
        self.assertNotIn(not_published.id, ids)
        self.assertNotIn(inactive.id, ids)

        # Retrieve detail for available crossword
        detail_url = reverse("crosswords-detail", args=[active_published.id])
        resp2 = self.client.get(detail_url)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data["id"], active_published.id)
        self.assertTrue("entries" in resp2.data)
        # Ensure answer fields not exposed
        for entry in resp2.data["entries"]:
            self.assertNotIn("answer", entry)


class CrosswordAdminCrudTests(BaseAPITestCase):
    def test_admin_crud(self):
        # Non-admin should be forbidden
        resp_forbidden = self.client_user.get(self.admin_crosswords_list)
        self.assertEqual(resp_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        # Admin list (initially empty)
        resp = self.client_admin.get(self.admin_crosswords_list)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])

        # Admin create crossword with entries
        payload = {
            "title": "Admin CW",
            "description": "D",
            "is_active": True,
            "metadata": {"rows": 2, "cols": 2},
            "entries": [
                {
                    "number": 1,
                    "direction": "across",
                    "clue": "Clue A",
                    "answer": "AB",
                    "row": 0,
                    "col": 0,
                    "length": 2,
                },
                {
                    "number": 1,
                    "direction": "down",
                    "clue": "Clue B",
                    "answer": "AD",
                    "row": 0,
                    "col": 0,
                    "length": 2,
                },
            ],
        }
        resp_create = self.client_admin.post(self.admin_crosswords_list, payload, format="json")
        self.assertEqual(resp_create.status_code, status.HTTP_201_CREATED)
        cw_id = resp_create.data["id"]

        # Retrieve
        detail_url = reverse("admin-crosswords-detail", args=[cw_id])
        resp_get = self.client_admin.get(detail_url)
        self.assertEqual(resp_get.status_code, 200)
        self.assertEqual(resp_get.data["title"], "Admin CW")
        self.assertEqual(len(Crossword.objects.get(id=cw_id).entries.all()), 2)

        # Update (replace entries)
        update_payload = {
            "title": "Updated CW",
            "description": "D2",
            "is_active": True,
            "metadata": {"rows": 3, "cols": 3},
            "entries": [
                {
                    "number": 2,
                    "direction": "across",
                    "clue": "Clue C",
                    "answer": "CAT",
                    "row": 1,
                    "col": 0,
                    "length": 3,
                }
            ],
        }
        resp_put = self.client_admin.put(detail_url, update_payload, format="json")
        self.assertEqual(resp_put.status_code, 200)
        cw = Crossword.objects.get(id=cw_id)
        self.assertEqual(cw.title, "Updated CW")
        self.assertEqual(cw.entries.count(), 1)

        # Delete
        resp_delete = self.client_admin.delete(detail_url)
        self.assertEqual(resp_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Crossword.objects.filter(id=cw_id).exists())


class SessionAndSubmissionTests(BaseAPITestCase):
    def test_session_start_submit_end_and_leaderboard(self):
        # Create crossword available now
        cw, entries = self.create_crossword_with_entries(title="Play", is_active=True, published=True)
        e_across = entries[0]  # "CAT" length 3
        e_down = entries[1]    # "CAR" length 3

        # Unauthenticated cannot access sessions list
        resp_anon = self.client.get(self.sessions_list)
        self.assertEqual(resp_anon.status_code, status.HTTP_403_FORBIDDEN)

        # Start session as authenticated user
        start_url = reverse("sessions-start")  # action on viewset (detail=False)
        resp_start = self.client_user.post(start_url, {"crossword_id": cw.id, "time_limit_seconds": 0}, format="json")
        self.assertEqual(resp_start.status_code, 200)
        session_id = resp_start.data["id"]
        session = PuzzleSession.objects.get(id=session_id)
        self.assertIsNone(session.ended_at)
        self.assertEqual(session.crossword_id, cw.id)

        # Submit incorrect answer for across
        submit_url = reverse("sessions-submit", args=[session_id])  # action detail=True
        resp_incorrect = self.client_user.post(
            submit_url, {"entry_id": e_across.id, "answer": "DOG"}, format="json"
        )
        self.assertEqual(resp_incorrect.status_code, 200)
        self.assertEqual(resp_incorrect.data["entry_id"], e_across.id)
        self.assertFalse(resp_incorrect.data["correct"])

        # Submit correct answer for across with different case and extra non-letters
        resp_correct_across = self.client_user.post(
            submit_url, {"entry_id": e_across.id, "answer": " c-aT "}, format="json"
        )
        self.assertEqual(resp_correct_across.status_code, 200)
        self.assertTrue(resp_correct_across.data["correct"])

        # Submit correct down
        resp_correct_down = self.client_user.post(
            submit_url, {"entry_id": e_down.id, "answer": "CAR"}, format="json"
        )
        self.assertEqual(resp_correct_down.status_code, 200)
        self.assertTrue(resp_correct_down.data["correct"])

        # Leaderboard should reflect attempts and correct counts (but not completed until ended)
        lb_before = LeaderboardEntry.objects.get(user=self.user, crossword=cw)
        self.assertEqual(lb_before.total_entries, 2)
        self.assertEqual(lb_before.correct_count, 2)
        # attempts is count of submissions (update_or_create keeps a single row per entry),
        # but update_from_session aggregates Count("id") across submissions. Since we updated both entries once after incorrect,
        # we should have 3 AnswerSubmission rows total (incorrect across replaced by correct -> still one row per entry).
        # So attempts equals the number of AnswerSubmission records, which should be 2 at this point.
        self.assertEqual(AnswerSubmission.objects.filter(session=session).count(), 2)
        self.assertEqual(lb_before.attempts, 2)
        self.assertFalse(lb_before.completed)
        self.assertGreaterEqual(lb_before.accuracy, 0.0)

        # End the session and verify leaderboard completion and fastest time
        end_url = reverse("sessions-end", args=[session_id])
        resp_end = self.client_user.post(end_url)
        self.assertEqual(resp_end.status_code, 200)
        session.refresh_from_db()
        self.assertIsNotNone(session.ended_at)

        lb_after = LeaderboardEntry.objects.get(user=self.user, crossword=cw)
        self.assertTrue(lb_after.completed)
        self.assertEqual(lb_after.correct_count, 2)
        self.assertEqual(lb_after.total_entries, 2)
        self.assertGreaterEqual(lb_after.fastest_seconds, 0)

        # Leaderboard API should show entry
        resp_lb_api = self.client.get(self.url_leaderboard, {"crossword_id": cw.id})
        self.assertEqual(resp_lb_api.status_code, 200)
        self.assertGreaterEqual(len(resp_lb_api.data), 1)
        usernames = [row["user"]["username"] for row in resp_lb_api.data]
        self.assertIn(self.user.username, usernames)

    def test_cannot_submit_after_session_end(self):
        cw, entries = self.create_crossword_with_entries()
        e1 = entries[0]

        # Start session
        start_url = reverse("sessions-start")
        resp_start = self.client_user.post(start_url, {"crossword_id": cw.id}, format="json")
        self.assertEqual(resp_start.status_code, 200)
        session_id = resp_start.data["id"]

        # End session
        end_url = reverse("sessions-end", args=[session_id])
        self.assertEqual(self.client_user.post(end_url).status_code, 200)

        # Submitting after end should be rejected
        submit_url = reverse("sessions-submit", args=[session_id])
        resp = self.client_user.post(submit_url, {"entry_id": e1.id, "answer": "CAT"}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Session has ended", str(resp.data))


class LeaderboardOrderingTests(BaseAPITestCase):
    def test_ordering_completed_then_fastest_then_accuracy(self):
        # Create crossword
        cw, entries = self.create_crossword_with_entries(title="Race")
        e1, e2 = entries

        # Two users play: user1 (self.user) and a second user2
        User.objects.create_user(username="user2", password="pass1234")
        client2 = APIClient()
        self.assertTrue(client2.login(username="user2", password="pass1234"))

        # Start sessions
        start_url = reverse("sessions-start")
        s1 = self.client_user.post(start_url, {"crossword_id": cw.id}).data["id"]
        s2 = client2.post(start_url, {"crossword_id": cw.id}).data["id"]

        # user1 answers all correctly quickly
        submit1 = reverse("sessions-submit", args=[s1])
        self.client_user.post(submit1, {"entry_id": e1.id, "answer": "CAT"})
        self.client_user.post(submit1, {"entry_id": e2.id, "answer": "CAR"})
        # Simulate earlier start for better fastest time for user1
        ps1 = PuzzleSession.objects.get(id=s1)
        ps1.started_at = timezone.now() - timezone.timedelta(seconds=5)
        ps1.save()
        self.client_user.post(reverse("sessions-end", args=[s1]))

        # user2 answers correctly but slower and with some wrong attempts to lower accuracy
        submit2 = reverse("sessions-submit", args=[s2])
        client2.post(submit2, {"entry_id": e1.id, "answer": "WRONG"})
        client2.post(submit2, {"entry_id": e1.id, "answer": "CAT"})
        client2.post(submit2, {"entry_id": e2.id, "answer": "CAR"})
        ps2 = PuzzleSession.objects.get(id=s2)
        ps2.started_at = timezone.now() - timezone.timedelta(seconds=10)
        ps2.save()
        client2.post(reverse("sessions-end", args=[s2]))

        # Leaderboard API ordering
        resp = self.client.get(self.url_leaderboard, {"crossword_id": cw.id})
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        # both completed; order by fastest_seconds ascending then accuracy desc then attempts asc
        self.assertEqual(len(data), 2)
        # Build comparable list (username, fastest_seconds, accuracy, attempts)
        structured = [
            (row["user"]["username"], row["fastest_seconds"], row["accuracy"], row["attempts"])
            for row in data
        ]
        # user1 should be ahead due to faster time or better accuracy if tie
        self.assertEqual(structured[0][0], "user1")
        self.assertEqual(structured[1][0], "user2")
