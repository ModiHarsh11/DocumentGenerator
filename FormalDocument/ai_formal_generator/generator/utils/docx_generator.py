from docx import Document

def generate_docx(content, file_path):
    doc = Document()
    for line in content.split("\n"):
        doc.add_paragraph(line)
    doc.save(file_path)
