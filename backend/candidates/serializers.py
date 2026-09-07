from rest_framework import serializers
from accounts.serializers import UserSerializer
from .models import CandidateProfile
from .utils import calculate_profile_completeness, is_candidate_profile_complete, parse_skills_list


class CandidateProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = CandidateProfile
        fields = (
            "id",
            "user",
            "user_email",
            "user_full_name",
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


class CandidateProfileInputSerializer(serializers.Serializer):
    headline = serializers.CharField(max_length=255, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    current_title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    years_experience = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    skills = serializers.CharField(required=False, allow_blank=True)
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
    resume_url = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)
    github_url = serializers.URLField(max_length=500, required=False, allow_blank=True, allow_null=True)
    portfolio_url = serializers.URLField(max_length=500, required=False, allow_blank=True, allow_null=True)
    linkedin_url = serializers.URLField(max_length=500, required=False, allow_blank=True, allow_null=True)
    bio = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    availability_status = serializers.ChoiceField(
        choices=CandidateProfile.AvailabilityStatus.choices,
        required=False,
        default=CandidateProfile.AvailabilityStatus.ACTIVELY_LOOKING,
    )
    privacy_visibility = serializers.ChoiceField(
        choices=CandidateProfile.PrivacyVisibility.choices,
        required=False,
        default=CandidateProfile.PrivacyVisibility.EMPLOYERS_ONLY,
    )

    def validate_skills(self, value):
        parsed = parse_skills_list(value)
        return parsed

    def validate(self, attrs):
        salary_min = attrs.get("salary_min")
        salary_max = attrs.get("salary_max")
        if salary_min and salary_max and salary_min > salary_max:
            raise serializers.ValidationError({"salary_min": "Minimum salary cannot exceed maximum salary."})
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        validated_data = dict(self.validated_data)

        # Phone sync to user if provided
        phone = validated_data.get("phone")
        if phone and phone.strip():
            user.phone = phone.strip()
            user.save(update_fields=["phone", "updated_at"])

        skills = validated_data.get("skills", [])
        if isinstance(skills, str):
            skills = parse_skills_list(skills)

        completeness_data = dict(validated_data)
        completeness_data["skills"] = skills

        completeness = calculate_profile_completeness(completeness_data)
        is_complete = is_candidate_profile_complete(completeness_data)
        open_to_matching = validated_data.get("availability_status") != CandidateProfile.AvailabilityStatus.NOT_LOOKING

        profile, _ = CandidateProfile.objects.update_or_create(
            user=user,
            defaults={
                "headline": validated_data.get("headline"),
                "phone": phone,
                "current_title": validated_data.get("current_title"),
                "years_experience": validated_data.get("years_experience"),
                "skills": skills,
                "role_categories": validated_data.get("role_categories", []),
                "experience_level": validated_data.get("experience_level"),
                "salary_min": validated_data.get("salary_min"),
                "salary_max": validated_data.get("salary_max"),
                "work_authorization": validated_data.get("work_authorization"),
                "us_state": validated_data.get("us_state"),
                "remote_preference": validated_data.get("remote_preference", "remote"),
                "preferred_work_type": validated_data.get("preferred_work_type", "remote"),
                "resume_url": validated_data.get("resume_url"),
                "github_url": validated_data.get("github_url"),
                "portfolio_url": validated_data.get("portfolio_url"),
                "linkedin_url": validated_data.get("linkedin_url"),
                "bio": validated_data.get("bio"),
                "availability_status": validated_data.get("availability_status", "actively_looking"),
                "privacy_visibility": validated_data.get("privacy_visibility", "employers_only"),
                "profile_completeness": completeness,
                "open_to_matching": open_to_matching,
                "profile_complete": is_complete,
            },
        )
        return profile


class PublicTalentCardSerializer(serializers.ModelSerializer):
    """
    Sanitized anonymized public talent showcase serializer matching src/lib/public-talent.ts.
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
