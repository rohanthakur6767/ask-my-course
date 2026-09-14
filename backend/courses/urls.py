from django.urls import path
from courses.views import (
    CourseListCreateView,
    CourseDetailView,
    StatsView,
    HealthView,
    AnalyzeView,
    IngestView,
    IngestFolderView,
    AskView,
    SuggestionsView,
    CourseStructureView,
    MaterialsView,
    HistoryView,
    InsightsView,
    UnitCreateView,
    UnitDetailView,
    LessonCreateView,
    LessonDetailView,
    MaterialDetailView,
)

urlpatterns = [
    # Liveness + DB check.
    path("health", HealthView.as_view(), name="health"),

    # Dashboard totals.
    path("stats", StatsView.as_view(), name="stats"),

    # Course management (list + create).
    path("courses", CourseListCreateView.as_view(), name="course-list-create"),
    path("courses/<uuid:course_id>", CourseDetailView.as_view(), name="course-detail"),

    # Course-scoped actions. <uuid:...> makes Django validate the id for us.
    path("courses/<uuid:course_id>/analyze", AnalyzeView.as_view(), name="analyze"),
    path("courses/<uuid:course_id>/ingest", IngestView.as_view(), name="ingest"),
    path("courses/<uuid:course_id>/ingest-folder", IngestFolderView.as_view(), name="ingest-folder"),
    path("courses/<uuid:course_id>/ask", AskView.as_view(), name="ask"),
    path("courses/<uuid:course_id>/suggestions", SuggestionsView.as_view(), name="suggestions"),
    path("courses/<uuid:course_id>/structure", CourseStructureView.as_view(), name="structure"),
    path("courses/<uuid:course_id>/materials", MaterialsView.as_view(), name="materials"),
    path("courses/<uuid:course_id>/history", HistoryView.as_view(), name="history"),
    path("courses/<uuid:course_id>/insights", InsightsView.as_view(), name="insights"),

    # Structure editing (rename / add / move / delete)
    path("courses/<uuid:course_id>/units", UnitCreateView.as_view(), name="unit-create"),
    path("units/<uuid:unit_id>", UnitDetailView.as_view(), name="unit-detail"),
    path("units/<uuid:unit_id>/lessons", LessonCreateView.as_view(), name="lesson-create"),
    path("lessons/<uuid:lesson_id>", LessonDetailView.as_view(), name="lesson-detail"),
    path("materials/<uuid:material_id>", MaterialDetailView.as_view(), name="material-detail"),
]
