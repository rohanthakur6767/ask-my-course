from rest_framework import serializers
from courses.models import Material


class IngestSerializer(serializers.Serializer):
    """Checks the POST body for /ingest."""
    file_path = serializers.CharField()
    unit_name = serializers.CharField(required=False, allow_blank=True, default="")
    lesson_name = serializers.CharField(required=False, allow_blank=True, default="")
    material_type = serializers.ChoiceField(
        choices=Material.MaterialType.choices,
        required=False, default=Material.MaterialType.PDF,
    )