from django.db import models

class WorkflowError(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error = models.CharField('Error', max_length=50)
    description = models.TextField('Description')
