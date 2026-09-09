import uuid
import io
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from .models import CandidateProfile
from .utils import calculate_profile_completeness, is_candidate_profile_complete, parse_skills_list


class CandidateUtilsTests(TestCase):
    def test_completeness_calculation(self):
        # 15 items total. 3 filled = 3/15 = 20%
        data = {
            "headline": "Fullstack Engineer",
            "phone": "+1234567890",
            "current_title": "Senior Dev",
        }
        score = calculate_profile_completeness(data)
        self.assertEqual(score, 20)

        # All 15 filled = 100%
        full_data = {
            "headline": "Lead Python Engineer",
            "phone": "+1234567890",
            "current_title": "Lead Dev",
            "years_experience": 8,
            "skills": ["Python", "Django", "PostgreSQL"],
            "role_categories": ["Backend", "Full-stack"],
            "experience_level": "senior",
            "work_authorization": "us_citizen",
            "us_state": "California",
            "salary_min": 140000,
            "salary_max": 180000,
            "bio": "Experienced backend architect.",
            "resume_url": "https://storage/resume.pdf",
            "github_url": "https://github.com/alice",
            "availability_status": "actively_looking",
            "preferred_work_type": "remote",
        }
        self.assertEqual(calculate_profile_completeness(full_data), 100)
        self.assertTrue(is_candidate_profile_complete(full_data))


class CandidateApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.candidate1 = User.objects.create_user(
            email="candidate1@test.com",
            password="Password123!",
            full_name="Alice Candidate",
            role=User.Role.CANDIDATE,
        )
        self.candidate2 = User.objects.create_user(
            email="candidate2@test.com",
            password="Password123!",
            full_name="Bob Candidate",
            role=User.Role.CANDIDATE,
        )
        self.employer = User.objects.create_user(
            email="employer@test.com",
            password="Password123!",
            full_name="Employer User",
            role=User.Role.EMPLOYER,
        )
        self.admin = User.objects.create_superuser(
            email="admin@test.com",
            password="AdminPassword123!",
            full_name="Staff Admin",
        )

    def _auth(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_and_retrieve_profile(self):
        self._auth(self.candidate1)
        payload = {
            "headline": "Senior Backend Architect",
            "phone": "+1555123456",
            "current_title": "Staff Engineer",
            "years_experience": 10,
            "skills": "Python, Django, Celery, Redis",
            "role_categories": ["Backend", "DevOps"],
            "experience_level": "lead",
            "salary_min": 160000,
            "salary_max": 200000,
            "work_authorization": "us_citizen",
            "us_state": "New York",
            "resume_url": "https://bucket/resumes/alice.pdf",
            "bio": "Passionate distributed systems engineer.",
            "availability_status": "actively_looking",
            "privacy_visibility": "public",
        }
        res = self.client.post("/api/v1/candidates/me/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["ok"])
        self.assertTrue(res.data["profileComplete"])
        self.assertGreater(res.data["profileCompleteness"], 80)

        # GET /me
        get_res = self.client.get("/api/v1/candidates/me/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["current_title"], "Staff Engineer")
        self.assertEqual(get_res.data["skills"], ["Python", "Django", "Celery", "Redis"])

    def test_employer_cannot_create_candidate_profile(self):
        self._auth(self.employer)
        res = self.client.post("/api/v1/candidates/me/", {"headline": "Test"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_public_talent_showcase(self):
        # Candidate 1: Public and complete
        CandidateProfile.objects.create(
            user=self.candidate1,
            headline="Full Stack Pro",
            current_title="Senior Developer",
            years_experience=6,
            skills=["React", "Node", "TypeScript", "GraphQL"],
            role_categories=["Full-stack", "Frontend"],
            privacy_visibility="public",
            profile_complete=True,
            open_to_matching=True,
            availability_status="actively_looking",
        )
        # Candidate 2: Invite only / hidden
        CandidateProfile.objects.create(
            user=self.candidate2,
            headline="Hidden Engineer",
            privacy_visibility="invite_only",
            profile_complete=True,
            open_to_matching=True,
        )

        self.client.credentials()  # Unauthenticated
        res = self.client.get("/api/v1/candidates/public-showcase/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        card = res.data[0]
        self.assertEqual(card["displayName"], "Alice C.")
        self.assertEqual(card["initials"], "AC")
        self.assertEqual(card["skills"], ["React", "Node", "TypeScript"])
        self.assertEqual(card["hiddenSkillCount"], 1)

    def test_admin_candidate_lookup(self):
        profile = CandidateProfile.objects.create(
            user=self.candidate1,
            headline="Private Profile",
            privacy_visibility="invite_only",
        )
        # Admin can view
        self._auth(self.admin)
        res = self.client.get(f"/api/v1/candidates/{profile.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["user_email"], "candidate1@test.com")

        # Candidate2 cannot view admin endpoint
        self._auth(self.candidate2)
        res = self.client.get(f"/api/v1/candidates/{profile.id}/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_candidate_registry_listing_and_filtering(self):
        # Setup candidate profiles
        p1 = CandidateProfile.objects.create(
            user=self.candidate1,
            headline="Python Wizard",
            experience_level="senior",
            work_authorization="us_citizen",
            availability_status="actively_looking",
            profile_complete=True,
            source="people_prime",
        )
        p2 = CandidateProfile.objects.create(
            user=self.candidate2,
            headline="Junior React Dev",
            experience_level="junior",
            work_authorization="international_remote",
            availability_status="not_looking",
            profile_complete=False,
            source="platform",
        )

        # Admin access
        self._auth(self.admin)
        res = self.client.get("/api/v1/admin/candidates/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("candidates", res.data)
        self.assertEqual(res.data["totalCount"], 2)
        self.assertEqual(res.data["completeCount"], 1)
        self.assertEqual(res.data["activeCount"], 1)

        # Filter by experience
        res_exp = self.client.get("/api/v1/admin/candidates/?experience=senior")
        self.assertEqual(len(res_exp.data["candidates"]), 1)
        self.assertEqual(res_exp.data["candidates"][0]["headline"], "Python Wizard")

        # Search by query
        res_q = self.client.get("/api/v1/admin/candidates/?q=alice")
        self.assertEqual(len(res_q.data["candidates"]), 1)
        self.assertEqual(res_q.data["candidates"][0]["profiles"]["email"], "candidate1@test.com")

        # Candidate denied
        self._auth(self.candidate1)
        res_cand = self.client.get("/api/v1/admin/candidates/")
        self.assertEqual(res_cand.status_code, status.HTTP_403_FORBIDDEN)

        # Employer denied
        self._auth(self.employer)
        res_emp = self.client.get("/api/v1/admin/candidates/")
        self.assertEqual(res_emp.status_code, status.HTTP_403_FORBIDDEN)

        # Unauthenticated denied
        self.client.credentials()
        res_unauth = self.client.get("/api/v1/admin/candidates/")
        self.assertEqual(res_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_candidate_create_and_duplicate_rejection(self):
        self._auth(self.admin)
        payload = {
            "fullName": "Admin Added User",
            "email": "admin_added@test.com",
            "headline": "Lead Platform Engineer",
            "skills": ["Docker", "Kubernetes", "AWS"],
            "roleCategories": ["DevOps", "Infrastructure"],
            "experienceLevel": "lead",
            "workAuthorization": "us_citizen",
        }
        res = self.client.post("/api/v1/admin/candidates/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["ok"])
        self.assertTrue(User.objects.filter(email="admin_added@test.com").exists())

        # Duplicate email rejected
        res_dup = self.client.post("/api/v1/admin/candidates/", payload, format="json")
        self.assertEqual(res_dup.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already exists", str(res_dup.data))

        # Non-admin forbidden
        self._auth(self.candidate1)
        res_cand = self.client.post("/api/v1/admin/candidates/", payload, format="json")
        self.assertEqual(res_cand.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_candidate_bulk_import_csv(self):
        self._auth(self.admin)
        csv_content = (
            "full_name,email,headline,skills,role_categories,experience_level,work_authorization\n"
            "Imported One,import1@test.com,Go Developer,Go;Kubernetes,Backend,mid,us_citizen\n"
            "Imported Two,import2@test.com,Frontend Architect,React;CSS,Frontend,senior,green_card\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))
        file_obj.name = "candidates.csv"

        res = self.client.post(
            "/api/v1/admin/candidates/import/",
            {"file": file_obj},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["created"], 2)
        self.assertEqual(res.data["failed"], 0)
        self.assertTrue(User.objects.filter(email="import1@test.com").exists())
        self.assertTrue(User.objects.filter(email="import2@test.com").exists())

