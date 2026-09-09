from rest_framework import serializers
from courses.models import Course, Unit, Lesson, Material, ChatSession


class IngestSerializer(serializers.Serializer):
    """Checks the POST body for /ingest."""
    file_path = serializers.CharField()
    unit_name = serializers.CharField(required=False, allow_blank=True, default="")
    lesson_name = serializers.CharField(required=False, allow_blank=True, default="")
    material_type = serializers.ChoiceField(
        choices=Material.MaterialType.choices,
        required=False, default=Material.MaterialType.PDF,
    )


class AskSerializer(serializers.Serializer):
    """Checks the POST body for /ask."""
    question = serializers.CharField()
    top_k = serializers.IntegerField(required=False, default=5, min_value=1, max_value=20)
    conversation_id = serializers.UUIDField(required=False, allow_null=True)


class CourseSerializer(serializers.ModelSerializer):
    """Read and create a course. tenant_id is set on the server, not by the client."""
    class Meta:
        model = Course
        fields = ["id", "name", "description", "created_at"]
        read_only_fields = ["id", "created_at"]


# --- Course structure (nested tree for the teacher dashboard) ---
class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ["id", "file_name", "material_type", "uploaded_at"]


class LessonSerializer(serializers.ModelSerializer):
    materials = MaterialSerializer(many=True, read_only=True)   # Lesson.materials
    class Meta:
        model = Lesson
        fields = ["id", "name", "sort_order", "materials"]


class UnitSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)       # Unit.lessons
    class Meta:
        model = Unit
        fields = ["id", "name", "sort_order", "lessons"]


class CourseStructureSerializer(serializers.ModelSerializer):
    units = UnitSerializer(many=True, read_only=True)           # Course.units
    class Meta:
        model = Course
        fields = ["id", "name", "description", "units"]


# --- Flat materials list ---
class MaterialListSerializer(serializers.ModelSerializer):
    unit = serializers.CharField(source="lesson.unit.name", read_only=True)
    lesson = serializers.CharField(source="lesson.name", read_only=True)
    chunk_count = serializers.IntegerField(read_only=True)      # annotated in the view
    class Meta:
        model = Material
        fields = ["id", "file_name", "material_type", "file_type",
                  "unit", "lesson", "chunk_count", "uploaded_at"]


# --- History ---
class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ["id", "user_id", "question", "answer", "sources",
                  "confidence", "guardrail_triggered", "created_at"]
