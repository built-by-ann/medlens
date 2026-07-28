from io import BytesIO

from pypdf import PdfReader


class PdfExtractionError(Exception):
    pass


def extract_text_from_pdf(contents: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(contents))
        pages_text = [page.extract_text() or "" for page in reader.pages]
    except Exception as error:
        raise PdfExtractionError("Could not read PDF file") from error

    return "\n".join(pages_text).strip()
