from django.db import models

class DocumentLog(models.Model):
    DOCUMENT_TYPES = [
        ("Office Order", "Office Order"),
        ("Notice", "Notice"),
        ("Circular", "Circular"),
        ("Other", "Other"),
    ]

    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    language = models.CharField(max_length=20)
    reference_id = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document_type} | {self.reference_id}"
