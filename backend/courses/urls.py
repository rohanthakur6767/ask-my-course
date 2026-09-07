from django.urls import path
from courses.views import (
    CourseListCreateView,
    StatsView,
    HealthView,
    IngestView,
    AskView,
    CourseStructureView,
    MaterialsView,
    HistoryView,
)

urlpatterns = [
    # Liveness + DB check.
    path("health", HealthView.as_view(), name="health"),

    # Dashboard totals.
    path("stats", StatsView.as_view(), name="stats"),

    # Course management (list + create).
    path("courses", CourseListCreateView.as_view(), name="course-list-create"),

    # Course-scoped actions. <uuid:...> makes Django validate the id for us.
    path("courses/<uuid:course_id>/ingest", IngestView.as_view(), name="ingest"),
    path("courses/<uuid:course_id>/ask", AskView.as_view(), name="ask"),
    path("courses/<uuid:course_id>/structure", CourseStructureView.as_view(), name="structure"),
    path("courses/<uuid:course_id>/materials", MaterialsView.as_view(), name="materials"),
    path("courses/<uuid:course_id>/history", HistoryView.as_view(), name="history"),
]
