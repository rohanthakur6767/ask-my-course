from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from courses.serializers import IngestSerializer
from courses.services.ingest import ingest_material, IngestError
from courses.services.pdf_extractor import PdfExtractionError
from courses.services.embedder import EmbeddingError


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