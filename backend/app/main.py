from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.documents import router
from app.core.config import Settings
from app.core.errors import DocumentError
from app.services.documents import DocumentService
from app.services.pdf import PdfParsingService
from app.services.storage import DocumentStorage, LocalDocumentStorage


def create_app(settings: Settings | None = None, storage: DocumentStorage | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Intelligent Document Operations", version="0.1.0", debug=False)
    app.state.document_service = DocumentService(
        storage if storage is not None else LocalDocumentStorage(settings.document_storage_path),
        PdfParsingService(), settings,
    )

    @app.exception_handler(DocumentError)
    async def document_error_handler(request: Request, exc: DocumentError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": "The request could not be completed."}})

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": "intelligent-document-operations"}

    app.include_router(router)
    return app


app = create_app()
