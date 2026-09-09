from django.db import models
import uuid #unique user ID
from pgvector.django import VectorField, HnswIndex

# Create your models here.
class Course(models.Model):
    """A course, e.g. 'IB Biology'. 
    The top level students ask questions about."""
    id = models.UUIDField(primary_key=True, #UUid primary key(non guessable and safe to show in url..)
                          default=uuid.uuid4, editable=False) # cannot edit the primary key
    name = models.CharField(max_length=225) #VARCHAR
    description = models.TextField(blank=True) # long text and can be blank
    tenant_id = models.UUIDField() # which school owns this course (multi tenant) or data
    created_at = models.DateTimeField(auto_now_add=True) # automatically save the data on creation of data

    def __str__(self):
        return self.name

class Unit(models.Model):
        """A unit inside a course, e.g. 'Cell Biology'."""
        id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        course = models.ForeignKey(Course, on_delete=models.CASCADE # foreign key: a link to another table. a unit belongs to one course, and if the course is deleted, its units go too
                                   , related_name="units") # used to get the course's units
        name = models.CharField(max_length=255)
        sort_order = models.PositiveIntegerField(default=0) # it is used to order the units and keep it positive

        def __str__(self):
            return self.name

class Lesson(models.Model):
        """A lesson inside a unit, e.g. 'Organelles and their functions'."""
        id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="lessons")
        name = models.CharField(max_length=255)
        sort_order = models.PositiveIntegerField(default=0)

        def __str__(self):
            return self.name
        
class Material(models.Model):
        """A file or note a teacher adds to a lesson:
        a PDF, the syllabus, or a typed note."""
        # A fixed, safe set of allowed types (the syllabus + important-topics feature).
        class MaterialType(models.TextChoices): # TextChoices is used to create a fixed list of options for a Django field, like a dropdown.
            PDF = "pdf", "PDF document"
            SYLLABUS = "syllabus", "Syllabus"
            NOTE = "note", "Important topics note"
        
        id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="materials")
        file_name = models.CharField(max_length=255)
        file_path = models.CharField(max_length=500, blank=True)  # blank for typed notes (no file)
        file_type = models.CharField(max_length=50, blank=True)   # pdf, txt, docx
        material_type = models.CharField(
            max_length=20, choices=MaterialType.choices, default=MaterialType.PDF
            )
        uploaded_at = models.DateTimeField(auto_now_add=True)
        
        def __str__(self):
            return self.file_name

class Embedding(models.Model):
        """One chunk of a material, stored as text AND as a vector.
        When a student asks something, we turn the question into a vector too,
        then ask Postgres which chunks are closest in meaning."""

        id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
        # Which material this chunk came from. Delete the material, its chunks go too.
        material = models.ForeignKey(
        Material, on_delete=models.CASCADE, related_name="embeddings"
        )

        # Copied here on purpose (denormalized) so "all chunks for course X" is one
        # fast filter at answer time, not going back to other table 
        course = models.ForeignKey(
            Course, on_delete=models.CASCADE, related_name="embeddings"
        )

        chunk_text = models.TextField()               # the actual words of this chunk
        chunk_index = models.PositiveIntegerField()   # tells us the position/order of a chunk inside the original material.

        # Where the chunk lives, used to build the citation. A typed note has no page.
        page_number = models.PositiveIntegerField(null=True, blank=True)

        # Copied here so we can write "Unit -> Lesson -> Page" without extra lookups.
        unit_name = models.CharField(max_length=255, blank=True)
        lesson_name = models.CharField(max_length=255, blank=True)

        # The vector itself: 1536 numbers from OpenAI's text-embedding-3-small.
        embedding = VectorField(dimensions=1536)

        created_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            indexes = [
            # HNSW graph index: great recall, works on an empty table,+
            # m = neighbours per node (16 = standard default).
            # ef_construction = build effort (higher = better index, slower build).
            # vector_cosine_ops = compare by cosine, what OpenAI embeddings expect.
            HnswIndex(
                name="embedding_vector_idx",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]

        def __str__(self):
            return f"{self.material.file_name} - chunk {self.chunk_index}"

class ChatSession(models.Model):
        """One question-and-answer exchange with a student.
        A history log: one row = one ask. Powers the /history endpoint and,
        later, our evaluation numbers. (Not conversation memory; that is a
        separate stretch feature.)
        """
        id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

        course = models.ForeignKey(
            Course, on_delete=models.CASCADE, related_name="chat_sessions"
        )

        # Who asked, as sent by the LMS. Optional for now while we build and test.
        user_id = models.CharField(max_length=255, blank=True)

        # Groups turns into one chat thread, so follow-up questions have context.
        conversation_id = models.UUIDField(null=True, blank=True, db_index=True)

        question = models.TextField()
        answer = models.TextField()

        # The citations we returned, stored as JSON so the shape stays flexible:
        # e.g. [{"unit": "...", "lesson": "...", "page": 4, "score": 0.82}].
        # default=list means a new row starts as an empty list [].
        sources = models.JSONField(default=list, blank=True)

        confidence = models.FloatField(default=0.0)          # 0.0 to 1.0, how sure we are
        guardrail_triggered = models.BooleanField(default=False)  # True when we refused

        created_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            ordering = ["-created_at"]   # newest first, which the history endpoint wants

        def __str__(self):
            return self.question[:50]
        