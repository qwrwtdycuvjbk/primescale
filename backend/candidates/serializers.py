from rest_framework import serializers
from accounts.models import User
from accounts.serializers import UserSerializer
from .models import CandidateProfile
from .utils import calculate_profile_completeness, is_candidate_profile_complete, parse_skills_list


class CandidateProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()
    user_full_name = serializers.SerializerMethodField()
    user_is_active = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    user_id = serializers.UUIDField(source="user.id", read_only=True)

    class Meta:
        model = CandidateProfile
        fields = (
            "id",
            "user",
            "user_id",
            "user_email",
            "user_full_name",
            "user_is_active",
            "email",
            "full_name",
            "name",
            "is_active",
            "headline",
            "phone",
            "current_title",
            "years_experience",
            "skills",
            "role_categories",
            "experience_level",
            "salary_min",
            "salary_max",
            "work_authorization",
            "us_state",
            "remote_preference",
            "preferred_work_type",
            "resume_url",
            "github_url",
            "portfolio_url",
            "linkedin_url",
            "bio",
            "availability_status",
            "privacy_visibility",
            "profile_completeness",
            "open_to_matching",
            "profile_complete",
            "source",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "user",
            "profile_completeness",
            "profile_complete",
            "created_at",
            "updated_at",
        )

    def get_user_full_name(self, obj) -> str:
        user = getattr(obj, "user", None)
        if not user:
            return ""
        name = (getattr(user, "full_name", "") or "").strip()
        if name:
            return name
        first = (getattr(user, "first_name", "") or "").strip()
        last = (getattr(user, "last_name", "") or "").strip()
        combined = f"{first} {last}".strip()
        return combined

    def get_full_name(self, obj) -> str:
        return self.get_user_full_name(obj)

    def get_name(self, obj) -> str:
        return self.get_user_full_name(obj)

    def get_user_email(self, obj) -> str:
        user = getattr(obj, "user", None)
        if not user:
            return ""
        return (getattr(user, "email", "") or "").strip()

    def get_email(self, obj) -> str:
        return self.get_user_email(obj)

    def get_user_is_active(self, obj) -> bool:
        user = getattr(obj, "user", None)
        if not user:
            return True
        return bool(getattr(user, "is_active", True))

    def get_is_active(self, obj) -> bool:
        return self.get_user_is_active(obj)


class CandidateProfileInputSerializer(serializers.Serializer):
    headline = serializers.CharField(max_length=255, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    current_title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    years_experience = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    skills = serializers.JSONField(required=False)
    role_categories = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    experience_level = serializers.ChoiceField(
        choices=CandidateProfile.ExperienceLevel.choices, required=False, allow_null=True
    )
    salary_min = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    salary_max = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    work_authorization = serializers.ChoiceField(
        choices=CandidateProfile.WorkAuthorization.choices, required=False, allow_null=True
    )
    us_state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    remote_preference = serializers.CharField(max_length=50, required=False, default="remote")
    preferred_work_type = serializers.ChoiceField(
        choices=CandidateProfile.PreferredWorkType.choices,
        required=False,
        default=CandidateProfile.PreferredWorkType.REMOTE,
    )
    resume_url = serializers.CharField(max_length=500, required=False, allow_blank=True)
    github_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    portfolio_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    linkedin_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    availability_status = serializers.ChoiceField(
        choices=CandidateProfile.AvailabilityStatus.choices,
        required=False,
        default=CandidateProfile.AvailabilityStatus.ACTIVELY_LOOKING,
    )
    privacy_visibility = serializers.ChoiceField(
        choices=CandidateProfile.PrivacyVisibility.choices,
        required=False,
        default=CandidateProfile.PrivacyVisibility.PUBLIC,
    )

    def validate_skills(self, value):
        return parse_skills_list(value)


class PublicTalentShowcaseSerializer(serializers.ModelSerializer):
    """
    Publicly safe serialized candidate profile for landing page talent showcase.
    Omits personally identifiable information (email, phone, full real name).
    """
    displayName = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    bioSnippet = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()
    hiddenSkillCount = serializers.SerializerMethodField()
    roleCategories = serializers.SerializerMethodField()
    availabilityLabel = serializers.SerializerMethodField()
    salaryRange = serializers.SerializerMethodField()

    class Meta:
        model = CandidateProfile
        fields = (
            "id",
            "displayName",
            "initials",
            "title",
            "bioSnippet",
            "experience_level",
            "years_experience",
            "skills",
            "hiddenSkillCount",
            "roleCategories",
            "work_authorization",
            "us_state",
            "availabilityLabel",
            "salaryRange",
        )

    def get_displayName(self, obj) -> str:
        full_name = obj.user.full_name or ""
        parts = [p for p in full_name.strip().split() if p]
        if not parts:
            return "Engineer"
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]} {parts[-1][0]}."

    def get_initials(self, obj) -> str:
        full_name = obj.user.full_name or ""
        parts = [p for p in full_name.strip().split() if p]
        if not parts:
            return "PE"
        return "".join(p[0].upper() for p in parts[:2])

    def get_title(self, obj) -> str:
        return obj.current_title or obj.headline or "Remote Engineer"

    def get_bioSnippet(self, obj) -> str:
        bio = (obj.bio or obj.headline or "").strip()
        if len(bio) <= 180:
            return bio
        return f"{bio[:180].rstrip()}…"

    def get_skills(self, obj) -> list:
        skills = obj.skills or []
        return skills[:3]

    def get_hiddenSkillCount(self, obj) -> int:
        skills = obj.skills or []
        return max(0, len(skills) - 3)

    def get_roleCategories(self, obj) -> list:
        cats = obj.role_categories or []
        return cats[:2]

    def get_availabilityLabel(self, obj) -> str:
        labels = {
            "actively_looking": "Actively looking",
            "open": "Open to roles",
            "not_looking": "Not looking",
        }
        return labels.get(obj.availability_status, "Available")

    def get_salaryRange(self, obj) -> str:
        min_sal = obj.salary_min
        max_sal = obj.salary_max
        if not min_sal and not max_sal:
            return ""
        def fmt(val):
            return f"${round(val / 1000)}k" if val >= 1000 else f"${val}"
        if min_sal and max_sal:
            return f"{fmt(min_sal)}–{fmt(max_sal)}"
        if min_sal:
            return f"{fmt(min_sal)}+"
        return f"Up to {fmt(max_sal)}"


# Alias for backward compatibility
PublicTalentCardSerializer = PublicTalentShowcaseSerializer


class AdminCandidateProfileUserNestedSerializer(serializers.ModelSerializer):
    """
    Nested user profile representation matching profiles!inner in CandidateRegistryTable.
    """
    class Meta:
        model = User
        fields = ("id", "full_name", "email", "phone", "created_at", "role", "is_active")


class AdminCandidateListSerializer(serializers.ModelSerializer):
    """
    Serializer for the Admin Candidate Registry table.
    Includes both top-level and nested user identity fields.
    """
    profiles = AdminCandidateProfileUserNestedSerializer(source="user", read_only=True)
    user = AdminCandidateProfileUserNestedSerializer(read_only=True)
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_email = serializers.SerializerMethodField()
    user_full_name = serializers.SerializerMethodField()
    user_is_active = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = CandidateProfile
        fields = (
            "id",
            "user_id",
            "user_email",
            "user_full_name",
            "user_is_active",
            "email",
            "full_name",
            "name",
            "is_active",
            "headline",
            "phone",
            "current_title",
            "years_experience",
            "skills",
            "role_categories",
            "experience_level",
            "work_authorization",
            "us_state",
            "availability_status",
            "profile_completeness",
            "open_to_matching",
            "profile_complete",
            "resume_url",
            "github_url",
            "linkedin_url",
            "source",
            "created_at",
            "updated_at",
            "profiles",
            "user",
        )

    def get_user_full_name(self, obj) -> str:
        user = getattr(obj, "user", None)
        if not user:
            return ""
        name = (getattr(user, "full_name", "") or "").strip()
        if name:
            return name
        first = (getattr(user, "first_name", "") or "").strip()
        last = (getattr(user, "last_name", "") or "").strip()
        combined = f"{first} {last}".strip()
        return combined

    def get_full_name(self, obj) -> str:
        return self.get_user_full_name(obj)

    def get_name(self, obj) -> str:
        return self.get_user_full_name(obj)

    def get_user_email(self, obj) -> str:
        user = getattr(obj, "user", None)
        if not user:
            return ""
        return (getattr(user, "email", "") or "").strip()

    def get_email(self, obj) -> str:
        return self.get_user_email(obj)

    def get_user_is_active(self, obj) -> bool:
        user = getattr(obj, "user", None)
        if not user:
            return True
        return bool(getattr(user, "is_active", True))

    def get_is_active(self, obj) -> bool:
        return self.get_user_is_active(obj)


class AdminCreateCandidateSerializer(serializers.Serializer):
    """
    Serializer for single admin candidate creation.
    Creates User (with unusable password) + CandidateProfile atomically.
    """
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    fullName = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    email = serializers.EmailField(max_length=255)
    phone = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True, default=None)
    headline = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    current_title = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    currentTitle = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    years_experience = serializers.IntegerField(required=False, allow_null=True, min_value=0, default=None)
    yearsExperience = serializers.IntegerField(required=False, allow_null=True, min_value=0, default=None)
    skills = serializers.JSONField(required=False, default=list)
    role_categories = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    roleCategories = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    experience_level = serializers.CharField(max_length=50, required=False, default="mid")
    experienceLevel = serializers.CharField(max_length=50, required=False, default="mid")
    salary_min = serializers.IntegerField(required=False, allow_null=True, min_value=0, default=None)
    salaryMin = serializers.IntegerField(required=False, allow_null=True, min_value=0, default=None)
    salary_max = serializers.IntegerField(required=False, allow_null=True, min_value=0, default=None)
    salaryMax = serializers.IntegerField(required=False, allow_null=True, min_value=0, default=None)
    work_authorization = serializers.CharField(max_length=50, required=False, default="international_remote")
    workAuthorization = serializers.CharField(max_length=50, required=False, default="international_remote")
    us_state = serializers.CharField(max_length=100, required=False, allow_blank=True, default="Remote")
    usState = serializers.CharField(max_length=100, required=False, allow_blank=True, default="Remote")
    location = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    preferred_work_type = serializers.CharField(max_length=50, required=False, default="remote")
    preferredWorkType = serializers.CharField(max_length=50, required=False, default="remote")
    availability_status = serializers.CharField(max_length=50, required=False, default="actively_looking")
    availabilityStatus = serializers.CharField(max_length=50, required=False, default="actively_looking")
    privacy_visibility = serializers.CharField(max_length=50, required=False, default="employers_only")
    privacyVisibility = serializers.CharField(max_length=50, required=False, default="employers_only")
    bio = serializers.CharField(required=False, allow_blank=True, default="")
    github_url = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    githubUrl = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    portfolio_url = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    portfolioUrl = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    linkedin_url = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    linkedinUrl = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    resume_url = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    resumeUrl = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    source = serializers.CharField(max_length=50, required=False, default="people_prime")

    def validate_email(self, value):
        normalized = value.strip().lower()
        if not normalized or "@" not in normalized:
            raise serializers.ValidationError("A valid email is required.")
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError(f"An account with this email already exists.")
        return normalized