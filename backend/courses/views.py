from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from django.db.models import Count

from courses.models import Course, Material, ChatSession
from courses.serializers import (
    IngestSerializer,
    AskSerializer,
    CourseStructureSerializer,
    MaterialListSerializer,
    ChatSessionSerializer,
)
from courses.services.ingest import ingest_material, IngestError
from courses.services.pdf_extractor import PdfExtractionError
from courses.services.embedder import EmbeddingError
from courses.services.ask import answer_question, AskError
from courses.services.generator import GenerationError


class IngestView(APIView):
    """POST /api/v1/courses/<course_id>/ingest"""

    def post(self, request, course_id):
        # Validate the body. Bad input becomes an automatic 400 with details.
        serializer = IngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = ingest_material(
                course_id=str(course_id),
                file_path=data["file_path"],
                unit_name=data["unit_name"],
                lesson_name=data["lesson_name"],
                material_type=data["material_type"],
            )
        except (IngestError, PdfExtractionError, EmbeddingError) as error:
            # Known failures return a clean message, not a 500 stack trace.
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_201_CREATED)


class AskView(APIView):
    """POST /api/v1/courses/<course_id>/ask"""

    def post(self, request, course_id):
        serializer = AskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = answer_question(
                course_id=str(course_id),
                question=data["question"],
                user_id=request.data.get("user_id", ""),
                top_k=data["top_k"],
            )
        except (AskError, EmbeddingError, GenerationError) as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)


class CourseStructureView(APIView):
    """GET /api/v1/courses/<course_id>/structure -> the unit/lesson/material tree"""

    def get(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(CourseStructureSerializer(course).data)


class MaterialsView(APIView):
    """GET /api/v1/courses/<course_id>/materials -> flat list with chunk counts"""

    def get(self, request, course_id):
        if not Course.objects.filter(id=course_id).exists():
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)

        materials = (
            Material.objects
            .filter(lesson__unit__course_id=course_id)
            .select_related("lesson", "lesson__unit")        # avoid extra queries (no N+1)
            .annotate(chunk_count=Count("embeddings"))       # count chunks in the database
            .order_by("lesson__unit__sort_order", "lesson__sort_order", "uploaded_at")
        )
        return Response(MaterialListSerializer(materials, many=True).data)


class HistoryView(APIView):
    """GET /api/v1/courses/<course_id>/history?limit=20 -> recent questions"""

    def get(self, request, course_id):
        if not Course.objects.filter(id=course_id).exists():
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)

        # Read and clamp the limit so a bad or huge value cannot hurt us.
        try:
            limit = int(request.query_params.get("limit", 20))
        except ValueError:
            limit = 20
        limit = max(1, min(limit, 100))

        # ChatSession is already ordered newest-first (Meta.ordering).
        sessions = ChatSession.objects.filter(course_id=course_id)[:limit]
        return Response(ChatSessionSerializer(sessions, many=True).data)
