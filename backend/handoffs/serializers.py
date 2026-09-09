from rest_framework import serializers
from matching.serializers import AdminMatchSerializer
from .models import HandoffRequest


class HandoffEmployerSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    phone = serializers.CharField(read_only=True, allow_null=True)


class HandoffRequestSerializer(serializers.ModelSerializer):
    match = AdminMatchSerializer(read_only=True)
    matches = AdminMatchSerializer(source="match", read_only=True)
    match_id = serializers.UUIDField(source="match.id", read_only=True)
    employer = serializers.SerializerMethodField()

    class Meta:
        model = HandoffRequest
        fields = (
            "id",
            "match_id",
            "match",
            "matches",
            "employer",
            "status",
            "notes",
            "notified_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "match_id", "match", "matches", "employer", "notified_at", "created_at", "updated_at")

    def get_employer(self, obj):
        posted_by = getattr(obj.match.job, "posted_by", None)
        if not posted_by:
            return None
        return {
            "id": str(posted_by.id),
            "full_name": posted_by.full_name,
            "email": posted_by.email,
            "phone": getattr(posted_by, "phone", None),
        }


class HandoffStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=HandoffRequest.Status.choices, required=False
    )
    notes = serializers.CharField(required=False, allow_blank=True)
