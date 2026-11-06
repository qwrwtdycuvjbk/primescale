import uuid
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from companies.models import Company


class EmployerAndCompanyNameValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    # =========================================================================
    # 1. Employer Registration Tests (UserRegistrationSerializer)
    # =========================================================================

    def test_employer_registration_valid_names(self):
        valid_names = [
            "Jane Doe",
            "Acme Tech Solutions",
            "1Password Technologies",
            "3M Innovations",
            "AT&T Recruiting",
            "A-1 Software LLC",
            "O'Connor & Sons Staffing",
            "Société Générale HR",
            "Jean-Luc Picard",
        ]
        for idx, name in enumerate(valid_names):
            payload = {
                "email": f"valid_employer_{idx}@example.com",
                "password": "SecurePassword123!",
                "full_name": name,
                "role": "employer",
            }
            res = self.client.post("/api/v1/auth/register/", payload, format="json")
            self.assertEqual(
                res.status_code,
                status.HTTP_201_CREATED,
                f"Failed for valid name '{name}': {res.data}",
            )
            user = User.objects.get(email=payload["email"])
            self.assertEqual(user.full_name, name)

    def test_employer_registration_rejects_urls_and_google_share(self):
        spam_names = [
            "3500 USD PROMO GET >> https://www.google.com/share.google?q=w8eJSz8rIWaeKlLBd",
            "Visit us at https://spam-domain.xyz",
            "Check www.freepromo.com for deals",
            "drive.google.com/open?id=12345",
            "See details at promo.live/bonus",
        ]
        for idx, name in enumerate(spam_names):
            payload = {
                "email": f"url_spammer_{idx}@example.com",
                "password": "SecurePassword123!",
                "full_name": name,
                "role": "employer",
            }
            res = self.client.post("/api/v1/auth/register/", payload, format="json")
            self.assertEqual(
                res.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"URL spam name '{name}' was not rejected!",
            )
            self.assertIn("full_name", res.data)

    def test_employer_registration_rejects_casino_and_gambling(self):
        casino_names = [
            "3500 USD CASINO PROMOCODE GET",
            "Best Slot Machine Deals",
            "Poker Night Live Tournament",
            "Online Roulette Bonus Club",
            "Mega Jackpot Winners",
        ]
        for idx, name in enumerate(casino_names):
            payload = {
                "email": f"casino_spammer_{idx}@example.com",
                "password": "SecurePassword123!",
                "full_name": name,
                "role": "employer",
            }
            res = self.client.post("/api/v1/auth/register/", payload, format="json")
            self.assertEqual(
                res.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Casino spam name '{name}' was not rejected!",
            )
            self.assertIn("full_name", res.data)

    def test_employer_registration_rejects_promotional_and_monetary_spam(self):
        promo_names = [
            "$4000 PROMOCODE! GET NOW",
            "$$4000 PROMOCODE from ROCKSTAR!",
            "3500$ PROMO SIGN UP",
            "500 USD CLAIM BONUS",
            "Free Spins and Deposit Bonus Code",
        ]
        for idx, name in enumerate(promo_names):
            payload = {
                "email": f"promo_spammer_{idx}@example.com",
                "password": "SecurePassword123!",
                "full_name": name,
                "role": "employer",
            }
            res = self.client.post("/api/v1/auth/register/", payload, format="json")
            self.assertEqual(
                res.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Promo spam name '{name}' was not rejected!",
            )
            self.assertIn("full_name", res.data)

    def test_employer_registration_rejects_repeated_chars_and_symbols_only(self):
        invalid_names = [
            "Aaaaaaaa Corp",
            "!!!!!!!!!!",
            "123456789",
            "--- ___ ---",
            "X",  # Too short (< 2 chars)
            "A" * 105,  # Too long (> 100 chars)
        ]
        for idx, name in enumerate(invalid_names):
            payload = {
                "email": f"invalid_spammer_{idx}@example.com",
                "password": "SecurePassword123!",
                "full_name": name,
                "role": "employer",
            }
            res = self.client.post("/api/v1/auth/register/", payload, format="json")
            self.assertEqual(
                res.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Invalid name '{name}' was not rejected!",
            )
            self.assertIn("full_name", res.data)

    def test_employer_registration_requires_full_name(self):
        payload = {
            "email": "empty_name_employer@example.com",
            "password": "SecurePassword123!",
            "full_name": "   ",
            "role": "employer",
        }
        res = self.client.post("/api/v1/auth/register/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("full_name", res.data)

    # =========================================================================
    # 2. Candidate Registration Validation Tests
    # =========================================================================

    def test_candidate_registration_valid_names(self):
        candidate_names = [
            "John Doe",
            "Alice O'Connor",
            "Jean-Luc Picard",
            "María José Carreño Quiroga",
            "René François-Auguste Rodin",
            "Dr. Martin Luther King Jr.",
            "Li Wei",
            "A. Kumar",
            "Søren Kierkegaard",
        ]
        for idx, name in enumerate(candidate_names):
            payload = {
                "email": f"candidate_{idx}@example.com",
                "password": "SecurePassword123!",
                "full_name": name,
                "role": "candidate",
            }
            res = self.client.post("/api/v1/auth/register/", payload, format="json")
            self.assertEqual(
                res.status_code,
                status.HTTP_201_CREATED,
                f"Candidate name '{name}' was rejected unexpectedly: {res.data}",
            )
            user = User.objects.get(email=payload["email"])
            self.assertEqual(user.full_name, name)
            self.assertTrue(user.is_candidate)
            self.assertTrue(hasattr(user, "candidate_profile"))

    def test_candidate_registration_rejects_urls_and_google_share(self):
        spam_names = [
            "3500 USD PROMO GET >> https://www.google.com/share.google?q=w8eJSz8rIWaeKlLBd",
            "Visit us at https://spam-domain.xyz",
            "Check www.freepromo.com for deals",
            "drive.google.com/open?id=12345",
            "promo.live/bonus",
        ]
        for idx, name in enumerate(spam_names):
            payload = {
                "email": f"candidate_url_spammer_{idx}@example.com",
                "password": "SecurePassword123!",
                "full_name": name,
                "role": "candidate",
            }
            res = self.client.post("/api/v1/auth/register/", payload, format="json")
            self.assertEqual(
                res.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"URL spam candidate name '{name}' was not rejected!",
            )
            self.assertIn("full_name", res.data)

    def test_candidate_registration_rejects_promotional_and_monetary_spam(self):
        promo_names = [
            "$4000 PROMOCODE! GET NOW",
            "$$4000 PROMOCODE from ROCKSTAR!",
            "3500$ PROMO SIGN UP",
            "500 USD CLAIM BONUS",
            "Free Spins and Deposit Bonus Code",
        ]
        for idx, name in enumerate(promo_names):
            payload = {
                "email": f"candidate_promo_spammer_{idx}@example.com",
                "password": "SecurePassword123!",
                "full_name": name,
                "role": "candidate",
            }
            res = self.client.post("/api/v1/auth/register/", payload, format="json")
            self.assertEqual(
                res.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Promo spam candidate name '{name}' was not rejected!",
            )
            self.assertIn("full_name", res.data)

    def test_candidate_registration_rejects_repeated_chars_and_symbols_only(self):
        invalid_names = [
            "Aaaaaaaa",
            "!!!!!!!!!!",
            "123456789",
            "--- ___ ---",
            "X",  # Too short (< 2 chars)
            "A" * 85,  # Too long (> 80 chars for candidates)
        ]
        for idx, name in enumerate(invalid_names):
            payload = {
                "email": f"candidate_invalid_spammer_{idx}@example.com",
                "password": "SecurePassword123!",
                "full_name": name,
                "role": "candidate",
            }
            res = self.client.post("/api/v1/auth/register/", payload, format="json")
            self.assertEqual(
                res.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Invalid candidate name '{name}' was not rejected!",
            )
            self.assertIn("full_name", res.data)

    def test_candidate_registration_requires_full_name(self):
        payload = {
            "email": "empty_name_candidate@example.com",
            "password": "SecurePassword123!",
            "full_name": "   ",
            "role": "candidate",
        }
        res = self.client.post("/api/v1/auth/register/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("full_name", res.data)

    # =========================================================================
    # 3. Company Name Validation Tests (CompanyInputSerializer)
    # =========================================================================

    def test_company_creation_valid_names(self):
        employer = User.objects.create_user(
            email="legit_company_owner@acme.com",
            password="SecurePassword123!",
            full_name="Acme Hiring",
            role=User.Role.EMPLOYER,
        )
        token = str(RefreshToken.for_user(employer).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        valid_companies = [
            "Acme Innovations Inc.",
            "1Password",
            "3M Health Care",
            "AT&T Services",
            "Figma, Inc.",
            "Basecamp / 37signals",
            "Hedgehog & Fox Co.",
        ]
        for cname in valid_companies:
            res = self.client.post("/api/v1/companies/me/", {"name": cname}, format="json")
            self.assertIn(
                res.status_code,
                [status.HTTP_200_OK, status.HTTP_201_CREATED],
                f"Valid company name '{cname}' was rejected: {res.data}",
            )
            company = Company.objects.get(owner=employer)
            self.assertEqual(company.name, cname)

    def test_company_creation_rejects_urls_and_promotions(self):
        employer = User.objects.create_user(
            email="spammer_employer@example.com",
            password="SecurePassword123!",
            full_name="Legit Name",
            role=User.Role.EMPLOYER,
        )
        token = str(RefreshToken.for_user(employer).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        spam_companies = [
            "https://www.google.com/share.google?q=promo",
            "3500$ CASINO BONUSES",
            "$$4000 PROMOCODE CLAIM",
            "Aaaaaaaa Tech",
            "1234567890",
            "C",  # Too short
            "X" * 105,  # Too long
        ]
        for cname in spam_companies:
            res = self.client.post("/api/v1/companies/me/", {"name": cname}, format="json")
            self.assertEqual(
                res.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Spam company name '{cname}' was not rejected!",
            )
            self.assertIn("name", res.data)
