from django.contrib import admin
from .models import DocumentLog

@admin.register(DocumentLog)
class DocumentLogAdmin(admin.ModelAdmin):
    list_display = ("document_type", "language", "reference_id", "created_at")
    search_fields = ("reference_id", "content")
    list_filter = ("document_type", "language", "created_at")
