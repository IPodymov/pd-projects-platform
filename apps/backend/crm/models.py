from django.db import models
from common.models import Entity


class LearningActivity(Entity):
    actor = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    classroom = models.ForeignKey("institutions.Classroom", on_delete=models.PROTECT)
    kind = models.CharField(max_length=40)
    target = models.CharField(max_length=100)
