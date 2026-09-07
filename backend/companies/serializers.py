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
        read_only_fields = (
            "id",
            "owner",
            "domain_verified",
            "profile_complete",
            "created_at",
            "updated_at",
        )


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
            "remote_culture_statement",
            "badge_remote_first",
            "badge_visa_sponsor",
            "badge_gcc",
        )


class CompanyInputSerializer(serializers.ModelSerializer):
    work_email = serializers.EmailField(required=False, write_only=True)

    class Meta:
        model = Company
        fields = (
            "name",
            "website",
            "size",
            "country",
            "logo_url",
            "description",
            "hq_city",
            "industry",
            "remote_culture_statement",
            "badge_remote_first",
            "badge_visa_sponsor",
            "badge_gcc",
            "work_email",
        )

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Company name is required.")
        return value.strip()

    def create(self, validated_data):
        work_email = validated_data.pop("work_email", None)
        user = self.context["request"].user
        email_to_check = work_email or user.email

        website = validated_data.get("website")
        domain_verified = is_work_email_domain_verified(email_to_check, website)
        profile_complete = is_company_profile_complete(validated_data)

        company = Company.objects.create(
            owner=user,
            domain_verified=domain_verified,
            profile_complete=profile_complete,
            **validated_data,
        )
        # Automatically create admin membership
        CompanyMember.objects.get_or_create(
            company=company,
            user=user,
            defaults={"member_role": CompanyMember.MemberRole.ADMIN},
        )
        return company

    def update(self, instance, validated_data):
        work_email = validated_data.pop("work_email", None)
        user = self.context["request"].user
        email_to_check = work_email or user.email

        website = validated_data.get("website", instance.website)
        if "website" in validated_data or work_email:
            instance.domain_verified = is_work_email_domain_verified(email_to_check, website)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Re-check profile completeness
        merged_data = {
            "name": instance.name,
            "size": instance.size,
            "description": instance.description,
            "hq_city": instance.hq_city,
            "industry": instance.industry,
        }
        instance.profile_complete = is_company_profile_complete(merged_data)
        instance.save()
        return instance
