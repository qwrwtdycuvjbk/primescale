import uuid
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .permissions import IsOwnerOrAdmin
from .serializers import UserRegistrationSerializer


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
        self.inactive_candidate = User.objects.create_user(
            email="inactive_candidate@test.com",
            password="TestPassword123!",
            full_name="Inactive Candidate",
            role=User.Role.CANDIDATE,
            is_active=False,
        )
        self.inactive_employer = User.objects.create_user(
            email="inactive_employer@test.com",
            password="TestPassword123!",
            full_name="Inactive Employer",
            role=User.Role.EMPLOYER,
            is_active=False,
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
        self.assertEqual(response.data["user"]["full_name"], "New Employer")
        self.assertFalse(response.data["user"]["email_verified"])

    def test_register_employer_with_phone(self):
        payload = {
            "email": "phone_employer@test.com",
            "password": "StrongPassword123!",
            "full_name": "Phone Employer",
            "phone": "+1 555 123 4567",
            "role": "employer",
        }
        response = self.client.post("/api/v1/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["user"]["phone"], "+1 555 123 4567")

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
        self.assertEqual(response.data["email"][0], "An account with this email already exists.")

    def test_register_duplicate_employer_email_rejected(self):
        payload = {
            "email": "employer@test.com",
            "password": "StrongPassword123!",
            "full_name": "Duplicate Employer",
            "role": "employer",
        }
        response = self.client.post("/api/v1/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertEqual(response.data["email"][0], "An account with this email already exists.")

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

    def test_register_atomic_rollback_on_failure(self):
        initial_count = User.objects.count()
        serializer = UserRegistrationSerializer(data={
            "email": "fail_email@test.com",
            "password": "StrongPassword123!",
            "full_name": "Fail User",
            "role": "employer",
        })
        self.assertTrue(serializer.is_valid())
        with patch("accounts.serializers.send_verification_email", side_effect=RuntimeError("SMTP Down")):
            with self.assertRaises(RuntimeError):
                serializer.save()

        self.assertEqual(User.objects.count(), initial_count)
        self.assertFalse(User.objects.filter(email="fail_email@test.com").exists())

    # --- Role-Based Login Tests ---
    def test_candidate_login_through_candidate_portal_success(self):
        payload = {
            "email": "candidate@test.com",
            "password": "TestPassword123!",
            "role": "candidate",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["role"], "candidate")

    def test_candidate_login_through_employer_portal_denied(self):
        payload = {
            "email": "candidate@test.com",
            "password": "TestPassword123!",
            "role": "employer",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)
        self.assertEqual(
            response.data["error"],
            "This account is registered as a candidate. Please use the Candidate Login.",
        )

    def test_employer_login_through_employer_portal_success(self):
        payload = {
            "email": "employer@test.com",
            "password": "TestPassword123!",
            "role": "employer",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["role"], "employer")

    def test_employer_login_through_candidate_portal_denied(self):
        payload = {
            "email": "employer@test.com",
            "password": "TestPassword123!",
            "role": "candidate",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)
        self.assertEqual(
            response.data["error"],
            "This account is registered as an employer. Please use the Employer Login.",
        )

    def test_admin_login_through_admin_portal_success(self):
        payload = {
            "email": "admin@test.com",
            "password": "AdminPassword123!",
            "role": "admin",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_candidate_login_through_admin_portal_denied(self):
        payload = {
            "email": "candidate@test.com",
            "password": "TestPassword123!",
            "role": "admin",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)
        self.assertEqual(response.data["error"], "This account does not have administrator access.")

    def test_employer_login_through_admin_portal_denied(self):
        payload = {
            "email": "employer@test.com",
            "password": "TestPassword123!",
            "role": "admin",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)
        self.assertEqual(response.data["error"], "This account does not have administrator access.")

    def test_admin_login_through_candidate_portal_denied(self):
        payload = {
            "email": "admin@test.com",
            "password": "AdminPassword123!",
            "role": "candidate",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)
        self.assertEqual(response.data["error"], "This account is not a candidate account.")

    def test_admin_login_through_employer_portal_denied(self):
        payload = {
            "email": "admin@test.com",
            "password": "AdminPassword123!",
            "role": "employer",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)
        self.assertEqual(response.data["error"], "This account is not an employer account.")

    def test_inactive_candidate_login_denied(self):
        payload = {
            "email": "inactive_candidate@test.com",
            "password": "TestPassword123!",
            "role": "candidate",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)
        self.assertEqual(response.data["error"], "Your access is denied by the Admin.")

    def test_inactive_employer_login_denied(self):
        payload = {
            "email": "inactive_employer@test.com",
            "password": "TestPassword123!",
            "role": "employer",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)
        self.assertEqual(response.data["error"], "Your access is denied by the Admin.")

    def test_candidate_login_invalid_password(self):
        payload = {
            "email": "candidate@test.com",
            "password": "WrongPassword123!",
            "role": "candidate",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_employer_login_invalid_password(self):
        payload = {
            "email": "employer@test.com",
            "password": "WrongPassword123!",
            "role": "employer",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_user(self):
        payload = {
            "email": "ghost@test.com",
            "password": "AnyPassword123!",
            "role": "candidate",
        }
        response = self.client.post("/api/v1/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_missing_fields(self):
        response = self.client.post("/api/v1/auth/login/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Current User (Me) Tests ---
    def test_me_authenticated(self):
        refresh = RefreshToken.for_user(self.candidate)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "candidate@test.com")

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

        response = self.client.post("/api/v1/auth/logout/", {"refresh": refresh_str}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")

        refresh_response = self.client.post("/api/v1/auth/refresh/", {"refresh": refresh_str}, format="json")
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_missing_refresh_token(self):
        response = self.client.post("/api/v1/auth/logout/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Role-Based Permission Tests ---
    def test_candidate_permission_matrix(self):
        refresh = RefreshToken.for_user(self.candidate)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        res = self.client.get("/api/v1/auth/test-candidate/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.get("/api/v1/auth/test-employer/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.client.get("/api/v1/auth/test-admin/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_employer_permission_matrix(self):
        refresh = RefreshToken.for_user(self.employer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        res = self.client.get("/api/v1/auth/test-candidate/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.client.get("/api/v1/auth/test-employer/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.get("/api/v1/auth/test-admin/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_permission_matrix(self):
        refresh = RefreshToken.for_user(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        res = self.client.get("/api/v1/auth/test-admin/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)


class ObjectLevelPermissionTests(TestCase):
    def test_is_owner_or_admin(self):
        user1 = User.objects.create_user(email="user1@test.com", password="PassWord123!")
        user2 = User.objects.create_user(email="user2@test.com", password="PassWord123!")
        admin = User.objects.create_superuser(email="adminuser@test.com", password="PassWord123!")

        permission = IsOwnerOrAdmin()

        class MockRequest:
            def __init__(self, user, method="GET"):
                self.user = user
                self.method = method

        class MockObject:
            def __init__(self, owner):
                self.owner = owner

        obj = MockObject(owner=user1)

        self.assertTrue(permission.has_object_permission(MockRequest(user1, "GET"), None, obj))
        self.assertFalse(permission.has_object_permission(MockRequest(user2, "GET"), None, obj))
        self.assertTrue(permission.has_object_permission(MockRequest(admin, "GET"), None, obj))


class GoogleOAuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.existing_candidate = User.objects.create_user(
            email="existing.candidate@example.com",
            password="StrongPassword123!",
            full_name="Existing Candidate",
            role=User.Role.CANDIDATE,
            email_verified=False,
        )
        self.existing_employer = User.objects.create_user(
            email="existing.employer@example.com",
            password="StrongPassword123!",
            full_name="Existing Employer",
            role=User.Role.EMPLOYER,
            email_verified=False,
        )
        self.inactive_candidate = User.objects.create_user(
            email="inactive.google@example.com",
            password="StrongPassword123!",
            full_name="Inactive Google User",
            role=User.Role.CANDIDATE,
            is_active=False,
        )

    def test_google_oauth_new_candidate(self):
        payload = {
            "email": "new.google.user@example.com",
            "full_name": "New Google User",
            "role": "candidate",
        }
        res = self.client.post("/api/v1/auth/oauth/google/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["created"])
        self.assertEqual(res.data["user"]["email"], "new.google.user@example.com")
        self.assertEqual(res.data["user"]["role"], "candidate")
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        self.assertIn("access_token", res.cookies)

        created_user = User.objects.get(email="new.google.user@example.com")
        self.assertTrue(created_user.email_verified)
        self.assertFalse(created_user.has_usable_password())

    def test_google_oauth_new_employer(self):
        payload = {
            "email": "new.employer@example.com",
            "full_name": "New Employer",
            "role": "employer",
        }
        res = self.client.post("/api/v1/auth/oauth/google/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["created"])
        self.assertEqual(res.data["user"]["role"], "employer")

    def test_google_oauth_candidate_in_candidate_portal_success(self):
        initial_id = self.existing_candidate.id
        initial_count = User.objects.count()

        payload = {
            "email": "existing.candidate@example.com",
            "full_name": "Existing Candidate",
            "role": "candidate",
        }
        res = self.client.post("/api/v1/auth/oauth/google/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["created"])
        self.assertEqual(res.data["user"]["id"], str(initial_id))
        self.assertEqual(User.objects.count(), initial_count)

    def test_google_oauth_candidate_in_employer_portal_denied(self):
        initial_count = User.objects.count()
        payload = {
            "email": "existing.candidate@example.com",
            "full_name": "Existing Candidate",
            "role": "employer",
        }
        res = self.client.post("/api/v1/auth/oauth/google/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", res.data)
        self.assertEqual(
            res.data["error"],
            "This account is registered as a candidate. Please use the Candidate Login.",
        )
        self.assertEqual(User.objects.count(), initial_count)

    def test_google_oauth_employer_in_employer_portal_success(self):
        initial_id = self.existing_employer.id
        initial_count = User.objects.count()

        payload = {
            "email": "existing.employer@example.com",
            "full_name": "Existing Employer",
            "role": "employer",
        }
        res = self.client.post("/api/v1/auth/oauth/google/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["created"])
        self.assertEqual(res.data["user"]["id"], str(initial_id))
        self.assertEqual(User.objects.count(), initial_count)

    def test_google_oauth_employer_in_candidate_portal_denied(self):
        initial_count = User.objects.count()
        payload = {
            "email": "existing.employer@example.com",
            "full_name": "Existing Employer",
            "role": "candidate",
        }
        res = self.client.post("/api/v1/auth/oauth/google/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", res.data)
        self.assertEqual(
            res.data["error"],
            "This account is registered as an employer. Please use the Employer Login.",
        )
        self.assertEqual(User.objects.count(), initial_count)

    def test_google_oauth_inactive_user_denied(self):
        payload = {
            "email": "inactive.google@example.com",
            "full_name": "Inactive Google User",
            "role": "candidate",
        }
        res = self.client.post("/api/v1/auth/oauth/google/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", res.data)
        self.assertEqual(res.data["error"], "Your access is denied by the Admin.")

    def test_google_oauth_invalid_email(self):
        payload = {
            "email": "not-an-email",
            "role": "candidate",
        }
        res = self.client.post("/api/v1/auth/oauth/google/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", res.data)

    def test_google_oauth_invalid_role(self):
        payload = {
            "email": "test@example.com",
            "role": "admin",
        }
        res = self.client.post("/api/v1/auth/oauth/google/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", res.data)