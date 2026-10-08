"""Shared validation for private project and course attachments."""

import io
import zipfile
from pathlib import Path
from rest_framework.exceptions import ValidationError


TEXT_EXTENSIONS = {".txt", ".md", ".csv"}
OFFICE_EXTENSIONS = {".docx", ".pptx"}
SIGNATURES = {
    ".pdf": b"%PDF-",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
}


def validate_attachment(upload):
    ext = Path(upload.name).suffix.lower()
    if ext not in TEXT_EXTENSIONS | OFFICE_EXTENSIONS | set(SIGNATURES):
        raise ValidationError(
            {"file": "Поддерживаются TXT, MD, CSV, DOCX, PPTX, PDF, PNG, JPG"}
        )
    limit = 20 * 1024 * 1024
    if upload.size > limit:
        raise ValidationError({"file": "Максимум 20 МБ"})
    content = upload.read(limit + 1)
    if len(content) > limit:
        raise ValidationError({"file": "Максимум 20 МБ"})
    text = ""
    if ext in TEXT_EXTENSIONS:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValidationError({"file": "Текст должен быть в UTF-8"})
    elif ext in SIGNATURES:
        if not content.startswith(SIGNATURES[ext]):
            raise ValidationError({"file": "Содержимое не соответствует формату файла"})
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                if (
                    len(entries) > 5000
                    or sum(item.file_size for item in entries) > 50 * 1024 * 1024
                ):
                    raise ValidationError("Слишком большой распакованный документ")
                required = (
                    "word/document.xml" if ext == ".docx" else "ppt/presentation.xml"
                )
                if required not in archive.namelist():
                    raise ValidationError("Неверный формат документа")
                for item in entries:
                    if item.filename.lower().endswith((".xml", ".rels")):
                        xml = archive.read(item)
                        if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
                            raise ValidationError("XML с DTD/ENTITY не принимается")
        except zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError:
            raise ValidationError("Повреждённый документ")
    return content, ext, text
