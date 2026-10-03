import re
from uuid import UUID, uuid4

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.errors import DocumentError
from app.schemas.documents import ProcessingResult, UploadResult
from app.services.pdf import PdfParsingService
from app.services.storage import DocumentStorage


class DocumentService:
    def __init__(self, storage: DocumentStorage, parser: PdfParsingService, settings: Settings) -> None:
        self.storage = storage
        self.parser = parser
        self.settings = settings

    async def upload(self, file: UploadFile) -> UploadResult:
        try:
            filename = file.filename or ""
            if (not filename.strip() or len(filename) > 255 or filename != filename.strip()
                    or any(ord(char) < 32 or ord(char) == 127 for char in filename)
                    or re.search(r'[<>:"/\\|?*]', filename) or ".." in filename
                    or filename.endswith((".", " "))
                    or filename.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}):
                raise DocumentError("UNSAFE_FILENAME", "A safe, nonempty filename is required.", 400)
            if not filename.lower().endswith(".pdf"):
                raise DocumentError("UNSUPPORTED_FILE_TYPE", "Only PDF files are supported.", 415)
            if file.content_type != "application/pdf":
                raise DocumentError("UNSUPPORTED_CONTENT_TYPE", "Content type must be application/pdf.", 415)
            chunks: list[bytes] = []
            size = 0
            while chunk := await file.read(min(64 * 1024, self.settings.max_upload_bytes + 1)):
                size += len(chunk)
                if size > self.settings.max_upload_bytes:
                    raise DocumentError("UPLOAD_TOO_LARGE", "The upload exceeds the configured size limit.", 413)
                chunks.append(chunk)
            if size == 0:
                raise DocumentError("EMPTY_UPLOAD", "The uploaded file is empty.", 400)
            document_id = uuid4()
            await run_in_threadpool(self.storage.save, document_id, b"".join(chunks))
            return UploadResult(document_id=document_id, original_filename=filename, size_bytes=size)
        finally:
            await file.close()

    def process(self, document_id: UUID) -> ProcessingResult:
        content = self.parser.parse(self.storage.read(document_id))
        meaningful = any(char.isalnum() for page in content.pages for char in page.text)
        return ProcessingResult(document_id=document_id, page_count=content.page_count,
                                character_count=content.character_count,
                                status="processed" if meaningful else "OCR_REQUIRED")
