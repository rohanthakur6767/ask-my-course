from django.urls import path
from courses.views import IngestView, AskView

urlpatterns = [
    # <uuid:...> makes Django validate the id is a real UUID for us.
    path("courses/<uuid:course_id>/ingest", IngestView.as_view(), name="ingest"),
    path("courses/<uuid:course_id>/ask", AskView.as_view()),
]