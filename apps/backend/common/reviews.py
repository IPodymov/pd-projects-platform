from rest_framework.exceptions import ValidationError


def validate_work_review(result, feedback):
    """Shared decision vocabulary for course and project work reviews."""
    if result not in ("accepted", "revision") or (
        result == "revision" and not feedback.strip()
    ):
        raise ValidationError({"feedback": "Для доработки обязательно замечание"})
