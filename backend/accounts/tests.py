import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .permissions import IsOwnerOrAdmin


class UserModelTests(TestCase):
    def test_create_user_candidate(self):
        user = User.objects.create_user(
            email="candidate@example.com",
            password="SecurePassword123!",
            full_name="Alice Candidate",
            phone="+1234567890",
            role=User.Role.CANDIDATE,
        )
        self.assertIsInstance(user.id, uuid.UUID)
        self.assertEqual(user.email, "candidate@example.com")
        self.assertEqual(user.full_name, "Alice Candidate")
        self.assertEqual(user.phone, "+1234567890")
        self.assertEqual(user.role, User.Role.CANDIDATE)
        self.assertTrue(user.is_candidate)
        self.assertFalse(user.is_employer)
        self.assertFalse(user.is_admin_user)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("SecurePassword123!"))
        self.assertNotEqual(user.password, "SecurePassword123!")

    def test_create_user_employer(self):
        user = User.objects.create_user(
            email="employer@example.com",
            password="SecurePassword123!",
            full_name="Bob Employer",
            role=User.Role.EMPLOYER,
        )
        self.assertEqual(user.role, User.Role.EMPLOYER)
        self.assertTrue(user.is_employer)
        self.assertFalse(user.is_candidate)
        self.assertFalse(user.is_admin_user)

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email="admin@example.com",
            password="AdminPassword123!",
            full_name="System Admin",
        )
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_admin_user)

    def test_create_superuser_invalid_flags(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="badadmin@example.com",
                password="AdminPassword123!",
                is_staff=False,
            )
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="badadmin2@example.com",
                password="AdminPassword123!",
                is_superuser=False,
            )

    def test_create_user_no_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="password123")

    def test_email_normalization(self):
        user = User.objects.create_user(email="Test.User@EXAMPLE.COM", password="password123")
        self.assertEqual(user.email, "Test.User@example.com")


class AuthenticationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.candidate = User.objects.create_user(
            email="candidate@test.com",
            password="TestPassword123!",
            full_name="Candidate One",
            role=User.Role.CANDIDATE,
        )
        self.employer = User.objects.create_user(
            email="employer@test.com",
            password="TestPassword123!",
            full_name="Employer One",
            role=User.Role.EMPLOYER,
        )
        self.admin = User.objects.create_superuser(
            email="admin@test.com",
            password="AdminPassword123!",
            full_name="Admin One",
        )

    # --- Registration Tests ---
    def test_register_candidate_success(self):
        payload = {
            "email": "newcandidate@test.com",
            "password": "StrongPassword123!",
            "full_name": "New Candidate",
            "phone": "+1999888777",
            "role": "candidate",
        }
        response = self.client.post("/api/v1/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["email"], "newcandidate@test.com")
        self.assertEqual(response.data["user"]["role"], "candidate")

        # Verify UUID primary key
        user_id = response.data["user"]["id"]
        self.assertTrue(uuid.UUID(user_id))

    def test_register_employer_success(self):
        payload = {
            "email": "newemployer@test.com",
            "password": "StrongPassword123!",
            "full_name": "New Employer",
            "role": "employer",
        }
        response = self.client.post("/api/v1/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["role"], "employer")

    def test_register_admin_rejected(self):
        payload = {
            "email": "hacker@test.com",
            "password": "StrongPassword123!",
            "full_name": "Fake Admin",
            "role": "admin",
        }
        response = self.client.post("/api/v1/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)

    def test_register_duplicate_email_rejected(self):
        payload = {
            "email": "candidate@test.com",
            "password": "StrongPassword123!",
            "full_name": "Duplicate Candidate",
            "role": "candidate",
        }
        response = self.client.post("/api/v1/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_register_invalid_email_rejected(self):
        payload = {
            "email": "not-an-email",
            "password": "StrongPassword123!",
            "role": "candidate",
        }
        response = self.client.post("/api/v1/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_weak_password_rejected(self):
        payload = {
            "email": "weakpass@test.com",
            "password": "123",
            "role": "candidate",
        }
        response = self.client.post("/api/v1/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Login Tests ---
    def test_login_success(self):
        payload = {
            "email": "candidate@test.com",
            "password": "TestPassword123!",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["email"], "candidate@test.com")

    def test_login_invalid_password(self):
        payload = {
            "email": "candidate@test.com",
            "password": "WrongPassword!",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", response.data)

    def test_login_unknown_email(self):
        payload = {
            "email": "unknown@test.com",
            "password": "SomePassword123!",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_inactive_user(self):
        self.candidate.is_active = False
        self.candidate.save()
        payload = {
            "email": "candidate@test.com",
            "password": "TestPassword123!",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Current User (/me) Tests ---
    def test_me_authenticated_candidate(self):
        refresh = RefreshToken.for_user(self.candidate)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "candidate@test.com")
        self.assertEqual(response.data["role"], "candidate")

    def test_me_unauthenticated(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token-string")
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Refresh Token Tests ---
    def test_refresh_token_success(self):
        refresh = RefreshToken.for_user(self.candidate)
        payload = {"refresh": str(refresh)}
        response = self.client.post("/api/v1/auth/refresh/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_refresh_token_invalid(self):
        payload = {"refresh": "invalid-refresh-token"}
        response = self.client.post("/api/v1/auth/refresh/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Logout & Blacklist Tests ---
    def test_logout_and_blacklisting(self):
        refresh = RefreshToken.for_user(self.candidate)
        refresh_str = str(refresh)

        # Call logout
        response = self.client.post("/api/v1/auth/logout/", {"refresh": refresh_str}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")

        # Re-using the blacklisted refresh token must now fail
        refresh_response = self.client.post("/api/v1/auth/refresh/", {"refresh": refresh_str}, format="json")
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_missing_refresh_token(self):
        response = self.client.post("/api/v1/auth/logout/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Role-Based Permission Tests ---
    def test_candidate_permission_matrix(self):
        refresh = RefreshToken.for_user(self.candidate)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        # Candidate accessing candidate endpoint -> 200
        res = self.client.get("/api/v1/auth/test-candidate/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Candidate accessing employer endpoint -> 403
        res = self.client.get("/api/v1/auth/test-employer/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Candidate accessing admin endpoint -> 403
        res = self.client.get("/api/v1/auth/test-admin/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_employer_permission_matrix(self):
        refresh = RefreshToken.for_user(self.employer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        # Employer accessing candidate endpoint -> 403
        res = self.client.get("/api/v1/auth/test-candidate/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Employer accessing employer endpoint -> 200
        res = self.client.get("/api/v1/auth/test-employer/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Employer accessing admin endpoint -> 403
        res = self.client.get("/api/v1/auth/test-admin/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_permission_matrix(self):
        refresh = RefreshToken.for_user(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        # Admin accessing admin endpoint -> 200
        res = self.client.get("/api/v1/auth/test-admin/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)


class ObjectLevelPermissionTests(TestCase):
    def test_is_owner_or_admin(self):
        user1 = User.objects.create_user(email="user1@test.com", password="PassWord123!")
        user2 = User.objects.create_user(email="user2@test.com", password="PassWord123!")
        admin = User.objects.create_superuser(email="adminuser@test.com", password="PassWord123!")

        permission = IsOwnerOrAdmin()

        class MockRequest:
            def __init__(self, user):
                self.user = user

        class MockObject:
            def __init__(self, owner):
                self.owner = owner

        obj = MockObject(owner=user1)

        # Owner accessing own object -> True
        self.assertTrue(permission.has_object_permission(MockRequest(user1), None, obj))

        # Non-owner accessing object -> False
        self.assertFalse(permission.has_object_permission(MockRequest(user2), None, obj))

        # Admin accessing object -> True
        self.assertTrue(permission.has_object_permission(MockRequest(admin), None, obj))
