from django.contrib import admin
from .models import Company, CompanyMember


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "industry", "hq_city", "domain_verified", "profile_complete", "created_at")
    list_filter = ("domain_verified", "profile_complete", "badge_remote_first", "badge_visa_sponsor")
    search_fields = ("name", "owner__email", "industry", "hq_city")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CompanyMember)
class CompanyMemberAdmin(admin.ModelAdmin):
    list_display = ("company", "user", "member_role", "created_at")
    list_filter = ("member_role",)
    search_fields = ("company__name", "user__email")
    readonly_fields = ("created_at",)
