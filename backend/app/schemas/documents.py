from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class UploadResult(BaseModel):
    document_id: UUID
    original_filename: str
    content_type: Literal["application/pdf"] = "application/pdf"
    size_bytes: int
    status: Literal["uploaded"] = "uploaded"


class DocumentPage(BaseModel):
    page_number: int
    text: str


class DocumentContent(BaseModel):
    pages: list[DocumentPage]
    page_count: int
    character_count: int


class ProcessingResult(BaseModel):
    document_id: UUID
    page_count: int
    character_count: int
    status: Literal["processed", "OCR_REQUIRED"]
