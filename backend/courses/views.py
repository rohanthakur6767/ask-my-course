import json
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
from courses.services.ingest import ingest_material, ingest_structured, IngestError
from courses.services.pdf_extractor import PdfExtractionError, extract_pages
from courses.services.outliner import propose_outline, OutlineError
from courses.services.embedder import EmbeddingError
from courses.services.ask import answer_question, AskError
from courses.services.generator import GenerationError
from courses.services.suggestions import suggest_questions


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


class CourseDetailView(APIView):
    """GET/DELETE /api/v1/courses/<course_id>"""

    def get(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(CourseSerializer(course).data)

    def delete(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)
        # CASCADE removes the course's units, lessons, materials, embeddings, and chat sessions.
        course.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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


class AnalyzeView(APIView):
    """POST /api/v1/courses/<course_id>/analyze

    Upload a PDF (multipart 'file'). We save it, extract the text, and ask the
    LLM to propose an outline (units -> lessons with page ranges). We do NOT
    ingest yet. The frontend shows the outline for the teacher to edit, then
    confirms via /ingest with the same file_path and the (edited) outline.
    """
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, course_id):
        if not Course.objects.filter(id=course_id).exists():
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)

        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            file_path = _save_upload(course_id, uploaded)
        except Exception as error:
            return Response({"error": f"Could not save the upload: {error}"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            pages = extract_pages(file_path)
            outline = propose_outline(pages)
        except (PdfExtractionError, OutlineError) as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "file_path": file_path,
            "file_name": uploaded.name,
            "pages": len(pages),
            "outline": outline,
        })


class IngestView(APIView):
    """POST /api/v1/courses/<course_id>/ingest

    Two modes:
    - Single upload: multipart 'file' (or JSON 'file_path') + unit_name/lesson_name.
    - Structured: an 'outline' (list of segments) plus the file/file_path; the PDF
      is split across the outline's units and lessons.
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, course_id):
        unit_name = request.data.get("unit_name", "")
        lesson_name = request.data.get("lesson_name", "")
        material_type = request.data.get("material_type", Material.MaterialType.PDF)
        if material_type not in Material.MaterialType.values:
            material_type = Material.MaterialType.PDF

        # Where is the file? An upload, or a server path from /analyze.
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
            file_name = str(request.data.get("file_name", "")).strip()
            file_type = "pdf"

        # Optional outline -> structured ingest. It may arrive as a JSON string
        # (multipart) or an already-parsed list (JSON body).
        outline = request.data.get("outline")
        if isinstance(outline, str):
            try:
                outline = json.loads(outline)
            except json.JSONDecodeError:
                return Response({"error": "outline is not valid JSON."},
                                status=status.HTTP_400_BAD_REQUEST)

        try:
            if outline:
                result = ingest_structured(
                    str(course_id), file_path, outline,
                    file_name=file_name, file_type=file_type, material_type=material_type,
                )
            else:
                result = ingest_material(
                    str(course_id), file_path,
                    unit_name=unit_name, lesson_name=lesson_name,
                    file_name=file_name, file_type=file_type, material_type=material_type,
                )
        except (IngestError, PdfExtractionError, EmbeddingError) as error:
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
                conversation_id=data.get("conversation_id"),
            )
        except (AskError, EmbeddingError, GenerationError) as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)


class SuggestionsView(APIView):
    """GET /api/v1/courses/<course_id>/suggestions -> a few starter questions"""

    def get(self, request, course_id):
        if not Course.objects.filter(id=course_id).exists():
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"questions": suggest_questions(str(course_id))})


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
