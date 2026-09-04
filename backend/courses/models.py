from django.db import models
import uuid #unique user ID

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

    