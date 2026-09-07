import os

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import connection
from django.db.models import Count

from courses.models import Course, Material, ChatSession
from courses.serializers import (
    AskSerializer,
    CourseSerializer,
    CourseStructureSerializer,
    MaterialListSerializer,
    ChatSessionSerializer,
)
from courses.services.ingest import ingest_material, IngestError
from courses.services.pdf_extractor import PdfExtractionError
from courses.services.embedder import EmbeddingError
from courses.services.ask import answer_question, AskError
from courses.services.generator import GenerationError


def _save_upload(course_id, uploaded_file):
    """Save an uploaded file under media/uploads/<course_id>/ and return its full path."""
    rel_path = os.path.join("uploads", str(course_id), uploaded_file.name)
    saved_name = default_storage.save(rel_path, uploaded_file)   # adds a suffix if the name exists
    return default_storage.path(saved_name)


class CourseListCreateView(APIView):
    """GET  /api/v1/courses  -> list courses for the demo tenant
       POST /api/v1/courses  -> create a course"""

    def get(self, request):
        courses = (
            Course.objects
            .filter(tenant_id=settings.DEMO_TENANT_ID)
            .order_by("-created_at")
        )
        return Response(CourseSerializer(courses, many=True).data)

    def post(self, request):
        serializer = CourseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course = serializer.save(tenant_id=settings.DEMO_TENANT_ID)
        return Response(CourseSerializer(course).data, status=status.HTTP_201_CREATED)


class StatsView(APIView):
    """GET /api/v1/stats -> totals for the demo tenant (powers the dashboard KPIs)."""

    def get(self, request):
        tenant = settings.DEMO_TENANT_ID
        return Response({
            "courses": Course.objects.filter(tenant_id=tenant).count(),
            "materials": Material.objects.filter(lesson__unit__course__tenant_id=tenant).count(),
            "questions": ChatSession.objects.filter(course__tenant_id=tenant).count(),
        })


class HealthView(APIView):
    """GET /api/v1/health -> liveness + database connectivity check."""

    def get(self, request):
        try:
            connection.ensure_connection()
            db_ok = True
        except Exception:
            db_ok = False
        return Response(
            {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "error"},
            status=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class IngestView(APIView):
    """POST /api/v1/courses/<course_id>/ingest

    Accepts either a multipart file upload (field 'file'), used by the dashboard,
    or a JSON body with 'file_path', used by scripts. Plus unit_name, lesson_name,
    material_type.
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, course_id):
        unit_name = request.data.get("unit_name", "")
        lesson_name = request.data.get("lesson_name", "")
        material_type = request.data.get("material_type", Material.MaterialType.PDF)

        # material_type must be a known choice, else fall back to the default.
        if material_type not in Material.MaterialType.values:
            material_type = Material.MaterialType.PDF

        uploaded = request.FILES.get("file")
        if uploaded:
            file_name = uploaded.name
            file_type = os.path.splitext(file_name)[1].lstrip(".").lower() or "pdf"
            try:
                file_path = _save_upload(course_id, uploaded)
            except Exception as error:
                return Response({"error": f"Could not save the upload: {error}"},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            file_path = str(request.data.get("file_path", "")).strip()
            if not file_path:
                return Response({"error": "Provide a file upload or a file_path."},
                                status=status.HTTP_400_BAD_REQUEST)
            file_name = ""
            file_type = "pdf"

        try:
            result = ingest_material(
                course_id=str(course_id),
                file_path=file_path,
                unit_name=unit_name,
                lesson_name=lesson_name,
                file_name=file_name,
                file_type=file_type,
                material_type=material_type,
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
