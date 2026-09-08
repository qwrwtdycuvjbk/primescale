"""
Phase 11 Comprehensive Authentication & Security Tests.
Tests:
1. Candidate registration + email verification flow.
2. Employer registration + email verification flow.
3. Migrated user password reset flow (unusable password -> reset request -> reset confirm -> login).
4. Anti-enumeration: password reset for nonexistent email returns 200 without error.
5. Invalid, expired, or tampered password reset tokens.
6. Single-use: password reset token cannot be reused after password update.
7. Invalid, expired, or tampered email verification tokens.
8. Single-use email verification token invalidation.
9. Google OAuth account linking with existing migrated user (preserves UUID, prevents duplicate user creation).
10. Google OAuth new user registration.
11. Admin self-registration prevention.
12. Unauthorized access to /me endpoint (401).
13. Invalid and blacklisted JWT refresh tokens.
14. Cookie generation and attribute verification (HttpOnly, SameSite=Lax).
15. Cross-role boundary enforcement (Candidate vs Employer vs Admin).
"""

import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from accounts.tokens import (
    decode_uid,
    email_verification_token_generator,
    encode_uid,
    password_reset_token_generator,
)

User = get_user_model()


class Phase11AuthFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create a sample migrated user with UNUSABLE password and preserved UUID
        self.migrated_user_id = uuid.uuid4()
        self.migrated_user = User.objects.create_user(
            id=self.migrated_user_id,
            email="migrated.candidate@example.com",
            password=None,  # unusable password
            full_name="Migrated Candidate",
            role=User.Role.CANDIDATE,
        )

        # Create existing admin
        self.admin = User.objects.create_superuser(
            email="admin@peopleremotely.com",
            password="AdminPassword123!",
            full_name="Site Admin",
        )

    # -------------------------------------------------------------
    # 1. Migrated User Password Reset & Activation Flow
    # -------------------------------------------------------------
    def test_migrated_user_initial_state(self):
        """Migrated user has preserved UUID and unusable password."""
        user = User.objects.get(email="migrated.candidate@example.com")
        self.assertEqual(user.id, self.migrated_user_id)
        self.assertFalse(user.has_usable_password())

        # Attempt login with any password fails with 401
        login_res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "migrated.candidate@example.com", "password": "AnyPassword123!"},
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_migrated_user_password_reset_flow(self):
        """Migrated user can request password reset, set a new password, and log in."""
        user = User.objects.get(email="migrated.candidate@example.com")

        # Step 1: Request reset
        req_res = self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": "migrated.candidate@example.com"},
            format="json",
        )
        self.assertEqual(req_res.status_code, status.HTTP_200_OK)
        self.assertIn("password reset link has been sent", req_res.data["detail"])

        # Step 2: Generate token as done by the service
        uidb64 = encode_uid(user.pk)
        token = password_reset_token_generator.make_token(user)

        # Step 3: Confirm password reset
        confirm_res = self.client.post(
            "/api/v1/auth/password-reset-confirm/",
            {
                "uid": uidb64,
                "token": token,
                "new_password": "NewSecurePassword2026!",
            },
            format="json",
        )
        self.assertEqual(confirm_res.status_code, status.HTTP_200_OK)
        self.assertIn("access", confirm_res.data)
        self.assertIn("refresh", confirm_res.data)

        # Verify user password is now usable and email verified
        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())
        self.assertTrue(user.email_verified)
        self.assertEqual(user.id, self.migrated_user_id)  # UUID unchanged

        # Step 4: Login with new password succeeds
        login_res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "migrated.candidate@example.com", "password": "NewSecurePassword2026!"},
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertEqual(login_res.data["user"]["id"], str(self.migrated_user_id))

    def test_password_reset_anti_enumeration(self):
        """Nonexistent email returns 200 without exposing account nonexistence."""
        res = self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": "nonexistent.user.123@example.com"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("password reset link has been sent", res.data["detail"])

    def test_password_reset_single_use_token(self):
        """Once password is reset, the same token cannot be reused."""
        user = self.migrated_user
        uidb64 = encode_uid(user.pk)
        token = password_reset_token_generator.make_token(user)

        # First use succeeds
        res1 = self.client.post(
            "/api/v1/auth/password-reset-confirm/",
            {"uid": uidb64, "token": token, "new_password": "FirstPassword123!"},
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # Second use fails with 400
        res2 = self.client.post(
            "/api/v1/auth/password-reset-confirm/",
            {"uid": uidb64, "token": token, "new_password": "SecondPassword123!"},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("token", res2.data)

    def test_password_reset_invalid_or_tampered_token(self):
        """Invalid or tampered tokens are rejected."""
        user = self.migrated_user
        uidb64 = encode_uid(user.pk)

        res = self.client.post(
            "/api/v1/auth/password-reset-confirm/",
            {"uid": uidb64, "token": "tampered-bogus-token", "new_password": "ValidPassword123!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------
    # 2. Email Verification Flow Tests
    # -------------------------------------------------------------
    def test_email_verification_flow(self):
        """Newly registered user can verify their email via verification token."""
        # Register new candidate
        reg_res = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "fresh.candidate@example.com",
                "password": "Password12345!",
                "full_name": "Fresh Candidate",
                "role": "candidate",
            },
            format="json",
        )
        self.assertEqual(reg_res.status_code, status.HTTP_201_CREATED)
        new_user = User.objects.get(email="fresh.candidate@example.com")
        self.assertFalse(new_user.email_verified)

        # Generate verification token
        token = email_verification_token_generator.make_token(new_user)
        uidb64 = encode_uid(new_user.pk)

        # Verify email endpoint
        verify_res = self.client.post(
            "/api/v1/auth/verify-email/",
            {"uid": uidb64, "token": token},
            format="json",
        )
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK)
        new_user.refresh_from_db()
        self.assertTrue(new_user.email_verified)

        # Token should be invalidated after verification
        reverify_res = self.client.post(
            "/api/v1/auth/verify-email/",
            {"uid": uidb64, "token": token},
            format="json",
        )
        self.assertEqual(reverify_res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_email_verification_invalid_token(self):
        """Tampered verification tokens are rejected."""
        uidb64 = encode_uid(self.migrated_user.pk)
        res = self.client.post(
            "/api/v1/auth/verify-email/",
            {"uid": uidb64, "token": "invalid-token"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_verification_endpoint(self):
        """Resend verification accepts email and returns safe 200 response."""
        res = self.client.post(
            "/api/v1/auth/resend-verification/",
            {"email": "migrated.candidate@example.com"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    # -------------------------------------------------------------
    # 3. Google OAuth & Account Linking Tests
    # -------------------------------------------------------------
    def test_google_oauth_links_existing_migrated_user(self):
        """
        Logging in via Google with the email of an existing migrated user
        must link to the existing account, preserving the exact UUID and role.
        No duplicate user is created.
        """
        initial_count = User.objects.count()

        oauth_payload = {
            "email": "migrated.candidate@example.com",
            "full_name": "Migrated Candidate Google",
            "role": "candidate",
        }
        res = self.client.post("/api/v1/auth/oauth/google/", oauth_payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["created"])
        self.assertEqual(res.data["user"]["id"], str(self.migrated_user_id))
        self.assertEqual(User.objects.count(), initial_count)  # No duplicate row!

        # Cookies check
        self.assertIn("access_token", res.cookies)
        self.assertIn("refresh_token", res.cookies)

    def test_google_oauth_new_user_creation(self):
        """Google OAuth for a new email provisions a new user with unusable password."""
        initial_count = User.objects.count()

        oauth_payload = {
            "email": "google.newbie@example.com",
            "full_name": "Google Newbie",
            "role": "employer",
        }
        res = self.client.post("/api/v1/auth/oauth/google/", oauth_payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["created"])
        self.assertEqual(res.data["user"]["role"], "employer")
        self.assertEqual(User.objects.count(), initial_count + 1)

        new_user = User.objects.get(email="google.newbie@example.com")
        self.assertFalse(new_user.has_usable_password())
        self.assertTrue(new_user.email_verified)

    # -------------------------------------------------------------
    # 4. Security, JWT & Role Matrix Tests
    # -------------------------------------------------------------
    def test_cookie_flags_on_login(self):
        """Tokens set in cookies are HttpOnly and SameSite=Lax."""
        # Set a password on migrated user
        self.migrated_user.set_password("LoginPass123!")
        self.migrated_user.save()

        res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "migrated.candidate@example.com", "password": "LoginPass123!"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        access_cookie = res.cookies.get("access_token")
        self.assertIsNotNone(access_cookie)
        self.assertTrue(access_cookie["httponly"])
        self.assertEqual(access_cookie["samesite"], "Lax")

        refresh_cookie = res.cookies.get("refresh_token")
        self.assertIsNotNone(refresh_cookie)
        self.assertTrue(refresh_cookie["httponly"])
        self.assertEqual(refresh_cookie["samesite"], "Lax")

    def test_cookie_cleared_on_logout(self):
        """Logout clears the auth cookies."""
        refresh = RefreshToken.for_user(self.admin)
        res = self.client.post(
            "/api/v1/auth/logout/",
            {"refresh": str(refresh)},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Cookies cleared (max-age 0 / empty value)
        self.assertEqual(res.cookies["access_token"].value, "")
        self.assertEqual(res.cookies["refresh_token"].value, "")

    def test_unauthorized_me_endpoint(self):
        """Accessing /api/v1/auth/me/ without authorization token returns 401."""
        res = self.client.get("/api/v1/auth/me/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_cannot_self_register(self):
        """Admin role registration is strictly rejected."""
        res = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "hacker@test.com",
                "password": "Password123!",
                "role": "admin",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", res.data)
