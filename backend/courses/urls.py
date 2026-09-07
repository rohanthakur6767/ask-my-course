from django.urls import path
from courses.views import (
    IngestView,
    AskView,
    CourseStructureView,
    MaterialsView,
    HistoryView,
)

urlpatterns = [
    # <uuid:...> makes Django validate the id is a real UUID for us.
    path("courses/<uuid:course_id>/ingest", IngestView.as_view(), name="ingest"),
    path("courses/<uuid:course_id>/ask", AskView.as_view(), name="ask"),
    path("courses/<uuid:course_id>/structure", CourseStructureView.as_view(), name="structure"),
    path("courses/<uuid:course_id>/materials", MaterialsView.as_view(), name="materials"),
    path("courses/<uuid:course_id>/history", HistoryView.as_view(), name="history"),
]
