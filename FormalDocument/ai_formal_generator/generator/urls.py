from django.urls import path
from . import views

urlpatterns = [
    # Home page with integrated selector
    path("", views.home, name="home"),

    # OFFICE ORDER
    path("generate-body/", views.generate_body, name="generate_body"),
    path("result/", views.result_office_order, name="result"),
    path("download/pdf/", views.download_pdf, name="download_pdf"),
    path("download/docx/", views.download_docx, name="download_docx"),

    # CIRCULAR
    path("circular/generate-body/", views.generate_circular_body, name="generate_circular_body"),
    path("circular/result/", views.result_circular, name="result_circular"),
    path("circular/pdf/", views.download_circular_pdf, name="download_circular_pdf"),
    path("circular/docx/", views.download_circular_docx, name="download_circular_docx"),

    # POLICY
    path("policy/generate-body/", views.generate_policy_body, name="generate_policy_body"),
    path("policy/result/", views.result_policy, name="result_policy"),
    path("policy/pdf/", views.download_policy_pdf, name="download_policy_pdf"),
    path("policy/docx/", views.download_policy_docx, name="download_policy_docx"),
]
