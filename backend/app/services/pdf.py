import re

import pymupdf

from app.core.errors import DocumentError
from app.schemas.documents import DocumentContent, DocumentPage


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


class PdfParsingService:
    def parse(self, content: bytes) -> DocumentContent:
        if not content.lstrip().startswith(b"%PDF-"):
            raise DocumentError("MALFORMED_PDF", "The file is not a valid PDF.")
        try:
            with pymupdf.open(stream=content, filetype="pdf") as document:
                if document.needs_pass:
                    raise DocumentError("ENCRYPTED_PDF", "Password-protected PDFs are not supported.")
                if document.page_count == 0:
                    raise DocumentError("MALFORMED_PDF", "The PDF contains no pages.")
                pages = [DocumentPage(page_number=index + 1, text=normalize_text(page.get_text()))
                         for index, page in enumerate(document)]
                return DocumentContent(pages=pages, page_count=len(pages),
                                       character_count=sum(len(page.text) for page in pages))
        except DocumentError:
            raise
        except (pymupdf.FileDataError, pymupdf.EmptyFileError) as exc:
            raise DocumentError("MALFORMED_PDF", "The PDF is malformed or corrupted.") from exc
        except Exception as exc:
            raise DocumentError("PARSING_FAILED", "The PDF could not be parsed.") from exc
