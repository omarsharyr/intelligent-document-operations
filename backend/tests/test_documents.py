import shutil
from uuid import uuid4
import pymupdf
import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app
from app.services.pdf import normalize_text

@pytest.fixture
def client(tmp_path):
    settings = Settings(document_storage_path=tmp_path / "documents", max_upload_size_mb=0.01, _env_file=None)
    try:
        with TestClient(create_app(settings)) as client:
            yield client
    finally:
        if settings.document_storage_path.exists():
            shutil.rmtree(settings.document_storage_path)

def pdf(text="Insurance policy", encrypted=False):
    with pymupdf.open() as doc:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
        if encrypted:
            return doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
        return doc.tobytes()

def upload(client, content=None, filename="Policy.pdf", mime="application/pdf"):
    return client.post("/api/v1/documents/upload", files={"file": (filename, pdf() if content is None else content, mime)})

def test_health(client):
    assert client.get("/health").json() == {"status": "healthy", "service": "intelligent-document-operations"}

def test_valid_upload(client):
    data = pdf()
    response = upload(client, data, "Insurance Policy 2026.pdf")
    assert response.status_code == 201
    result = response.json()
    assert result["size_bytes"] == len(data)
    assert result["original_filename"] == "Insurance Policy 2026.pdf"
    assert result["status"] == "uploaded"
    root = client.app.state.document_service.storage.root
    assert (root / (result["document_id"] + ".pdf")).read_bytes() == data
    assert len(list(root.iterdir())) == 1

@pytest.mark.parametrize("filename,mime,data,status,code", [
    ("a.txt", "application/pdf", b"a", 415, "UNSUPPORTED_FILE_TYPE"),
    ("a.pdf", "text/plain", b"a", 415, "UNSUPPORTED_CONTENT_TYPE"),
    ("a.pdf", "application/pdf", b"x" * 11000, 413, "UPLOAD_TOO_LARGE"),
    ("a.pdf", "application/pdf", b"", 400, "EMPTY_UPLOAD"),
    ("../a.pdf", "application/pdf", b"a", 400, "UNSAFE_FILENAME"),
    ("..\\a.pdf", "application/pdf", b"a", 400, "UNSAFE_FILENAME"),
    ("C:/a.pdf", "application/pdf", b"a", 400, "UNSAFE_FILENAME"),
    ("CON.pdf", "application/pdf", b"a", 400, "UNSAFE_FILENAME"),
    ("bad?.pdf", "application/pdf", b"a", 400, "UNSAFE_FILENAME"),
])
def test_invalid_upload(client, filename, mime, data, status, code):
    response = upload(client, data, filename, mime)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert not client.app.state.document_service.storage.root.exists()

@pytest.mark.parametrize("data,status,code", [
    (pdf(), 200, "processed"), (pdf(""), 200, "OCR_REQUIRED"),
    (pdf("..."), 200, "OCR_REQUIRED"),
    (b"broken", 422, "MALFORMED_PDF"),
    (b"%PDF-1.7\ncorrupted", 422, "MALFORMED_PDF"),
    (pdf(encrypted=True), 422, "ENCRYPTED_PDF"),
])
def test_processing(client, data, status, code):
    identifier = upload(client, data).json()["document_id"]
    response = client.post(f"/api/v1/documents/{identifier}/process")
    assert response.status_code == status
    result = response.json()
    if status == 200:
        assert result["status"] == code
        assert result["page_count"] == 1
        assert result["character_count"] >= 0
        assert "text" not in result and "pages" not in result
    else:
        assert result["error"]["code"] == code

def test_missing_document(client):
    response = client.post(f"/api/v1/documents/{uuid4()}/process")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"

def test_invalid_id(client):
    assert client.post("/api/v1/documents/not-a-uuid/process").status_code == 422

def test_normalization():
    assert normalize_text("  First   paragraph. \r\n\r\n\r\n Second\tparagraph.  ") == "First paragraph.\n\nSecond paragraph."

def test_multiple_pages(client):
    with pymupdf.open() as document:
        for text in ["First page", "Second page"]:
            document.new_page().insert_text((72, 72), text)
        content = client.app.state.document_service.parser.parse(document.tobytes())
    assert [p.page_number for p in content.pages] == [1, 2]
    assert content.page_count == 2
    assert content.character_count == len("First pageSecond page")

def test_parsing_failure(client, monkeypatch):
    identifier = upload(client).json()["document_id"]
    def fail(*args, **kwargs):
        raise RuntimeError("internal details")
    monkeypatch.setattr(pymupdf, "open", fail)
    response = client.post(f"/api/v1/documents/{identifier}/process")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PARSING_FAILED"
    assert "internal details" not in response.text

def test_storage_failure(client, monkeypatch):
    def fail(*args):
        raise OSError("private filesystem path")
    monkeypatch.setattr(client.app.state.document_service.storage, "save", fail)
    with TestClient(client.app, raise_server_exceptions=False) as safe_client:
        response = upload(safe_client)
    assert response.status_code == 500
    assert "private filesystem path" not in response.text
