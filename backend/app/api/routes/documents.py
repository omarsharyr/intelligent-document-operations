from uuid import UUID

from fastapi import APIRouter, Request, UploadFile

from app.schemas.documents import ProcessingResult, UploadResult

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResult, status_code=201)
async def upload_document(request: Request, file: UploadFile) -> UploadResult:
    return await request.app.state.document_service.upload(file)


@router.post("/{document_id}/process", response_model=ProcessingResult)
def process_document(document_id: UUID, request: Request) -> ProcessingResult:
    return request.app.state.document_service.process(document_id)
