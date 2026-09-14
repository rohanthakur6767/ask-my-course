"""Edit a course's structure: create, rename, move, and delete units, lessons,
and materials.

The important subtlety: each Embedding chunk stores the unit / lesson / file
names DENORMALIZED (copied onto the row) so citations are fast. So whenever we
rename or move something, we must update those copies too, or citations would
show stale names. Every function below keeps them in sync.
"""

from django.db import transaction

from courses.models import Unit, Lesson, Material, Embedding


class StructureError(Exception):
    """Raised when a structure edit is invalid (e.g. empty name)."""
    pass


def _clean(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise StructureError("Name cannot be empty.")
    return name


# ---------------- Units ----------------
def create_unit(course, name: str) -> Unit:
    name = _clean(name)
    last = Unit.objects.filter(course=course).order_by("-sort_order").first()
    order = (last.sort_order + 1) if last else 0
    return Unit.objects.create(course=course, name=name, sort_order=order)


def rename_unit(unit: Unit, name: str) -> Unit:
    unit.name = _clean(name)
    unit.save(update_fields=["name"])
    # Keep the denormalized citation copies in sync for every chunk under this unit.
    Embedding.objects.filter(material__lesson__unit=unit).update(unit_name=unit.name)
    return unit


def delete_unit(unit: Unit) -> None:
    unit.delete()   # cascades to lessons -> materials -> embeddings


# ---------------- Lessons ----------------
def create_lesson(unit: Unit, name: str) -> Lesson:
    name = _clean(name)
    last = Lesson.objects.filter(unit=unit).order_by("-sort_order").first()
    order = (last.sort_order + 1) if last else 0
    return Lesson.objects.create(unit=unit, name=name, sort_order=order)


def rename_lesson(lesson: Lesson, name: str) -> Lesson:
    lesson.name = _clean(name)
    lesson.save(update_fields=["name"])
    Embedding.objects.filter(material__lesson=lesson).update(lesson_name=lesson.name)
    return lesson


@transaction.atomic
def move_lesson(lesson: Lesson, new_unit: Unit) -> Lesson:
    lesson.unit = new_unit
    lesson.save(update_fields=["unit"])
    # The unit changed, so refresh the denormalized unit name on its chunks.
    Embedding.objects.filter(material__lesson=lesson).update(unit_name=new_unit.name)
    return lesson


def delete_lesson(lesson: Lesson) -> None:
    lesson.delete()   # cascades to materials -> embeddings


# ---------------- Materials ----------------
def rename_material(material: Material, file_name: str) -> Material:
    material.file_name = _clean(file_name)
    material.save(update_fields=["file_name"])
    Embedding.objects.filter(material=material).update(file_name=material.file_name)
    return material


@transaction.atomic
def move_material(material: Material, new_lesson: Lesson) -> Material:
    material.lesson = new_lesson
    material.save(update_fields=["lesson"])
    # Both lesson and unit names may change, so refresh both on the chunks.
    Embedding.objects.filter(material=material).update(
        lesson_name=new_lesson.name, unit_name=new_lesson.unit.name,
    )
    return material


def delete_material(material: Material) -> None:
    material.delete()   # cascades to embeddings
