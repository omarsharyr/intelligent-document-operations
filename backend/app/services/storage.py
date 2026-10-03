import os
import tempfile
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.core.errors import DocumentError


class DocumentStorage(Protocol):
    def save(self, document_id: UUID, content: bytes) -> None: ...
    def read(self, document_id: UUID) -> bytes: ...


class LocalDocumentStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, document_id: UUID) -> Path:
        # Only a validated UUID is ever used to construct a storage key.
        return self.root / f"{document_id}.pdf"

    def save(self, document_id: UUID, content: bytes) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, delete=False) as file:
                temporary = file.name
                file.write(content)
            os.replace(temporary, self._path(document_id))
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)

    def read(self, document_id: UUID) -> bytes:
        try:
            return self._path(document_id).read_bytes()
        except FileNotFoundError as exc:
            raise DocumentError("DOCUMENT_NOT_FOUND", "Document not found.", 404) from exc
