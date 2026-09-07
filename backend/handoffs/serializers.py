from rest_framework import serializers
from matching.serializers import AdminMatchSerializer
from .models import HandoffRequest


class HandoffRequestSerializer(serializers.ModelSerializer):
    match = AdminMatchSerializer(read_only=True)

    class Meta:
        model = HandoffRequest
        fields = (
            "id",
            "match",
            "status",
            "notes",
            "notified_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "match", "notified_at", "created_at", "updated_at")


class HandoffStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=HandoffRequest.Status.choices, required=False
    )
    notes = serializers.CharField(required=False, allow_blank=True)
