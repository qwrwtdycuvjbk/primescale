from rest_framework import serializers
from .models import Company, CompanyMember
from .utils import is_work_email_domain_verified, is_company_profile_complete


class CompanyMemberSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = CompanyMember
        fields = (
            "id",
            "company",
            "user",
            "user_email",
            "user_full_name",
            "member_role",
            "created_at",
        )
        read_only_fields = ("id", "company", "created_at")


class CompanySerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    members = CompanyMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Company
        fields = (
            "id",
            "owner",
            "owner_email",
            "name",
            "website",
            "size",
            "country",
            "logo_url",
            "description",
            "hq_city",
            "industry",
            "remote_culture_statement",
            "domain_verified",
            "badge_remote_first",
            "badge_visa_sponsor",
            "badge_gcc",
            "profile_complete",
            "members",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "owner", "created_at", "updated_at")


class CompanyPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "website",
            "size",
            "country",
            "logo_url",
            "description",
            "hq_city",
            "industry",
            "badge_remote_first",
            "badge_visa_sponsor",
            "badge_gcc",
        )


class CompanyInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    website = serializers.URLField(max_length=500, required=False, allow_blank=True, allow_null=True)
    size = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    country = serializers.CharField(max_length=100, required=False, default="US")
    logo_url = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    hq_city = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    industry = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    remote_culture_statement = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    work_email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)


class AdminEmployerListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    website = serializers.SerializerMethodField()
    company_website = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    company_hq_city = serializers.SerializerMethodField()
    company_country = serializers.SerializerMethodField()
    industry = serializers.SerializerMethodField()
    company_industry = serializers.SerializerMethodField()
    company_size = serializers.SerializerMethodField()
    profile_complete = serializers.SerializerMethodField()
    company_profile_complete = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    company_logo_url = serializers.SerializerMethodField()
    jobs_count = serializers.SerializerMethodField()
    posted_jobs_count = serializers.SerializerMethodField()
    members_count = serializers.SerializerMethodField()
    primary_contact_name = serializers.SerializerMethodField()
    primary_contact_email = serializers.SerializerMethodField()
    primary_contact_active = serializers.SerializerMethodField()

    class Meta:
        from accounts.models import User
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "role",
            "is_active",
            "email_verified",
            "created_at",
            "updated_at",
            "name",
            "company_name",
            "website",
            "company_website",
            "location",
            "company_hq_city",
            "company_country",
            "industry",
            "company_industry",
            "company_size",
            "profile_complete",
            "company_profile_complete",
            "logo_url",
            "company_logo_url",
            "jobs_count",
            "posted_jobs_count",
            "members_count",
            "primary_contact_name",
            "primary_contact_email",
            "primary_contact_active",
        )

    def _get_company(self, obj):
        if hasattr(obj, "owned_company") and obj.owned_company:
            return obj.owned_company
        membership = obj.company_memberships.select_related("company").first()
        return membership.company if membership else None

    def get_name(self, obj):
        comp = self._get_company(obj)
        if comp and comp.name and comp.name.strip():
            return comp.name.strip()
        if obj.full_name and obj.full_name.strip():
            return obj.full_name.strip()
        if obj.email and obj.email.strip():
            return obj.email.strip().split("@")[0].capitalize()
        return "Employer Account"

    def get_company_name(self, obj):
        return self.get_name(obj)

    def get_website(self, obj):
        comp = self._get_company(obj)
        return comp.website if comp else None

    def get_company_website(self, obj):
        return self.get_website(obj)

    def get_location(self, obj):
        comp = self._get_company(obj)
        if comp and comp.hq_city and comp.hq_city.strip():
            return comp.hq_city.strip()
        if comp and comp.country and comp.country.strip():
            return comp.country.strip()
        return "Remote / US"

    def get_company_hq_city(self, obj):
        return self.get_location(obj)

    def get_company_country(self, obj):
        comp = self._get_company(obj)
        return comp.country if comp else "US"

    def get_industry(self, obj):
        comp = self._get_company(obj)
        return comp.industry if comp and comp.industry else "General"

    def get_company_industry(self, obj):
        return self.get_industry(obj)

    def get_company_size(self, obj):
        comp = self._get_company(obj)
        return comp.size if comp and comp.size else "Not specified"

    def get_profile_complete(self, obj):
        comp = self._get_company(obj)
        return comp.profile_complete if comp else False

    def get_company_profile_complete(self, obj):
        return self.get_profile_complete(obj)

    def get_logo_url(self, obj):
        comp = self._get_company(obj)
        return comp.logo_url if comp else None

    def get_company_logo_url(self, obj):
        return self.get_logo_url(obj)

    def get_jobs_count(self, obj):
        comp = self._get_company(obj)
        if comp:
            return comp.jobs.count()
        return obj.posted_jobs.count()

    def get_posted_jobs_count(self, obj):
        return self.get_jobs_count(obj)

    def get_members_count(self, obj):
        comp = self._get_company(obj)
        if comp:
            count = comp.members.count()
            return max(1, count)
        return 1

    def get_primary_contact_name(self, obj):
        if obj.full_name and obj.full_name.strip():
            return obj.full_name.strip()
        comp = self._get_company(obj)
        if comp and comp.owner and comp.owner.full_name and comp.owner.full_name.strip():
            return comp.owner.full_name.strip()
        return "Primary Contact"

    def get_primary_contact_email(self, obj):
        return obj.email or ""

    def get_primary_contact_active(self, obj):
        return bool(obj.is_active)


class AdminEmployerDetailSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    website = serializers.SerializerMethodField()
    company_website = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    industry = serializers.SerializerMethodField()
    company_size = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    profile_complete = serializers.SerializerMethodField()
    primary_contact_name = serializers.SerializerMethodField()
    primary_contact_email = serializers.SerializerMethodField()
    primary_contact_active = serializers.SerializerMethodField()
    jobs_count = serializers.SerializerMethodField()
    members_count = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    jobs = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()

    class Meta:
        from accounts.models import User
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "role",
            "is_active",
            "email_verified",
            "created_at",
            "updated_at",
            "name",
            "company_name",
            "website",
            "company_website",
            "location",
            "industry",
            "company_size",
            "description",
            "logo_url",
            "profile_complete",
            "primary_contact_name",
            "primary_contact_email",
            "primary_contact_active",
            "jobs_count",
            "members_count",
            "members",
            "jobs",
            "company",
        )

    def _get_company(self, obj):
        if hasattr(obj, "owned_company") and obj.owned_company:
            return obj.owned_company
        membership = obj.company_memberships.select_related("company").first()
        return membership.company if membership else None

    def get_name(self, obj):
        comp = self._get_company(obj)
        if comp and comp.name and comp.name.strip():
            return comp.name.strip()
        if obj.full_name and obj.full_name.strip():
            return obj.full_name.strip()
        if obj.email and obj.email.strip():
            return obj.email.strip().split("@")[0].capitalize()
        return "Employer Account"

    def get_company_name(self, obj):
        return self.get_name(obj)

    def get_website(self, obj):
        comp = self._get_company(obj)
        return comp.website if comp else None

    def get_company_website(self, obj):
        return self.get_website(obj)

    def get_location(self, obj):
        comp = self._get_company(obj)
        if comp and comp.hq_city and comp.hq_city.strip():
            return comp.hq_city.strip()
        if comp and comp.country and comp.country.strip():
            return comp.country.strip()
        return "Remote / US"

    def get_industry(self, obj):
        comp = self._get_company(obj)
        return comp.industry if comp and comp.industry else "General"

    def get_company_size(self, obj):
        comp = self._get_company(obj)
        return comp.size if comp and comp.size else "Not specified"

    def get_description(self, obj):
        comp = self._get_company(obj)
        if comp:
            return comp.description or comp.remote_culture_statement or ""
        return ""

    def get_logo_url(self, obj):
        comp = self._get_company(obj)
        return comp.logo_url if comp else None

    def get_profile_complete(self, obj):
        comp = self._get_company(obj)
        return comp.profile_complete if comp else False

    def get_primary_contact_name(self, obj):
        if obj.full_name and obj.full_name.strip():
            return obj.full_name.strip()
        comp = self._get_company(obj)
        if comp and comp.owner and comp.owner.full_name and comp.owner.full_name.strip():
            return comp.owner.full_name.strip()
        return "Primary Contact"

    def get_primary_contact_email(self, obj):
        return obj.email or ""

    def get_primary_contact_active(self, obj):
        return bool(obj.is_active)

    def get_jobs_count(self, obj):
        comp = self._get_company(obj)
        if comp:
            return comp.jobs.count()
        return obj.posted_jobs.count()

    def get_members_count(self, obj):
        comp = self._get_company(obj)
        if comp:
            count = comp.members.count()
            return max(1, count)
        return 1

    def get_company(self, obj):
        comp = self._get_company(obj)
        if comp:
            return CompanySerializer(comp).data
        return None

    def get_members(self, obj):
        comp = self._get_company(obj)
        members_list = []
        if comp:
            for m in comp.members.select_related("user").all():
                members_list.append({
                    "id": str(m.id),
                    "user_id": str(m.user.id),
                    "email": m.user.email,
                    "full_name": m.user.full_name,
                    "role": m.member_role,
                    "is_active": m.user.is_active,
                    "created_at": m.created_at.isoformat(),
                })
        if not members_list:
            members_list.append({
                "id": str(obj.id),
                "user_id": str(obj.id),
                "email": obj.email,
                "full_name": obj.full_name or "Employer",
                "role": "Owner / Administrator",
                "is_active": obj.is_active,
                "created_at": obj.created_at.isoformat(),
            })
        return members_list

    def get_jobs(self, obj):
        comp = self._get_company(obj)
        from jobs.models import Job
        if comp:
            jobs_qs = Job.objects.filter(company=comp).order_by("-created_at")
        else:
            jobs_qs = Job.objects.filter(posted_by=obj).order_by("-created_at")

        return [
            {
                "id": str(j.id),
                "title": j.title,
                "role_type": j.role_type,
                "employment_type": j.role_type,
                "experience_level": j.experience_level,
                "location": (comp.hq_city if comp else "Remote") or "Remote",
                "work_location_type": j.work_type,
                "status": j.status,
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs_qs
        ]