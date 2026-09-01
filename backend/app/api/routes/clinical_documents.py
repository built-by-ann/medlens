import logging
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_owned_patient
from app.core.pdf import PdfExtractionError, extract_text_from_pdf
from app.db.session import get_db
from app.models.patient import Patient
from app.schemas.clinical_document import ClinicalDocumentCreate, ClinicalDocumentResponse
from app.services.clinical_document_service import (
    CSV_FILE_TYPE,
    PDF_FILE_TYPE,
    TXT_FILE_TYPE,
    DocumentHasNoStoredFileError,
    create_clinical_document,
    create_clinical_document_from_file,
    delete_clinical_document,
    get_clinical_document,
    get_clinical_document_content,
    get_clinical_documents_for_patient,
)
from app.storage.base import ObjectNotFoundError, StorageError, StorageService
from app.storage.service import get_storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients/{patient_id}/clinical-documents", tags=["clinical-documents"])

NOT_FOUND_DETAIL = "Clinical document not found"
NO_STORED_FILE_DETAIL = "This document has no stored file to download"
STORAGE_UNAVAILABLE_DETAIL = "File storage is currently unavailable"

# The canonical content type for each upload route's file, not
# file.content_type (what the client claims in the multipart request),
# which is unreliable: browsers and API clients frequently send a generic
# or empty value even for a file that otherwise passes this route's own
# extension/content-type validation below. Since each route already only
# accepts one file type, the type it stores is simply that type, not
# whatever the client happened to send.
TXT_CONTENT_TYPE = "text/plain"
PDF_CONTENT_TYPE = "application/pdf"
CSV_CONTENT_TYPE = "text/csv"


@router.post(
    "",
    response_model=ClinicalDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    document_in: ClinicalDocumentCreate,
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> ClinicalDocumentResponse:
    return create_clinical_document(db, patient, document_in)


@router.post(
    "/upload-txt",
    response_model=ClinicalDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload TXT document",
)
def upload_txt_document(
    document_type: str = Form(min_length=1),
    title: str = Form(min_length=1),
    file: UploadFile = File(...),
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> ClinicalDocumentResponse:
    started_at = time.monotonic()
    is_txt_extension = (file.filename or "").lower().endswith(".txt")
    is_plain_text_content_type = file.content_type == "text/plain"

    if not (is_txt_extension or is_plain_text_content_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only .txt or text/plain files are supported",
        )

    contents = file.file.read()

    extraction_started_at = time.monotonic()
    try:
        raw_text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File must be valid UTF-8 encoded text",
        ) from None
    _log_text_extracted(patient.id, TXT_FILE_TYPE, extraction_started_at)

    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded file is empty",
        )

    return _create_from_file(
        db,
        storage,
        patient,
        document_type=document_type,
        title=title,
        raw_text=raw_text,
        file_name=file.filename,
        file_type=TXT_FILE_TYPE,
        content=contents,
        content_type=TXT_CONTENT_TYPE,
        started_at=started_at,
    )


@router.post(
    "/upload-pdf",
    response_model=ClinicalDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload PDF document",
)
def upload_pdf_document(
    document_type: str = Form(min_length=1),
    title: str = Form(min_length=1),
    file: UploadFile = File(...),
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> ClinicalDocumentResponse:
    started_at = time.monotonic()
    is_pdf_extension = (file.filename or "").lower().endswith(".pdf")
    is_pdf_content_type = file.content_type == "application/pdf"

    if not (is_pdf_extension or is_pdf_content_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only .pdf or application/pdf files are supported",
        )

    contents = file.file.read()

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded file is empty",
        )

    extraction_started_at = time.monotonic()
    try:
        raw_text = extract_text_from_pdf(contents)
    except PdfExtractionError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File must be a valid PDF",
        ) from None
    _log_text_extracted(patient.id, PDF_FILE_TYPE, extraction_started_at)

    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No extractable text found in PDF",
        )

    return _create_from_file(
        db,
        storage,
        patient,
        document_type=document_type,
        title=title,
        raw_text=raw_text,
        file_name=file.filename,
        file_type=PDF_FILE_TYPE,
        content=contents,
        content_type=PDF_CONTENT_TYPE,
        started_at=started_at,
    )


@router.post(
    "/upload-csv",
    response_model=ClinicalDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload CSV document",
)
def upload_csv_document(
    document_type: str = Form(min_length=1),
    title: str = Form(min_length=1),
    file: UploadFile = File(...),
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> ClinicalDocumentResponse:
    # Issue #164: a CSV uploaded here becomes an ordinary clinical document,
    # evidence for AI extraction and reconciliation, not a medication
    # import. Deliberately does not call parse_medication_csv /
    # create_medications_from_rows (app/services/medication_import_service.py,
    # the /patients/{id}/medications/import route in medications.py); the raw
    # CSV text is stored and flows through the exact same pipeline as an
    # uploaded .txt file, with nothing patient-medication-specific about it.
    started_at = time.monotonic()
    is_csv_extension = (file.filename or "").lower().endswith(".csv")
    is_csv_content_type = file.content_type == "text/csv"

    if not (is_csv_extension or is_csv_content_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only .csv or text/csv files are supported",
        )

    contents = file.file.read()

    extraction_started_at = time.monotonic()
    try:
        raw_text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File must be valid UTF-8 encoded text",
        ) from None
    _log_text_extracted(patient.id, CSV_FILE_TYPE, extraction_started_at)

    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded file is empty",
        )

    return _create_from_file(
        db,
        storage,
        patient,
        document_type=document_type,
        title=title,
        raw_text=raw_text,
        file_name=file.filename,
        file_type=CSV_FILE_TYPE,
        content=contents,
        content_type=CSV_CONTENT_TYPE,
        started_at=started_at,
    )


def _log_text_extracted(patient_id: int, file_type: str, extraction_started_at: float) -> None:
    # Issue #60: separate from document_uploaded's own duration_ms
    # (create_clinical_document_from_file, app/services/clinical_document_service.py),
    # which covers storage upload + persistence; this is only the
    # text-extraction step (pypdf for PDF, a plain decode for txt/csv),
    # logged uniformly across all three formats so file_type is a
    # meaningful comparison dimension (e.g. PDF extraction is expected to
    # be slower than a plain decode).
    duration_ms = (time.monotonic() - extraction_started_at) * 1000
    logger.info(
        "Document text extracted",
        extra={
            "event": "document_text_extracted",
            "patient_id": patient_id,
            "file_type": file_type,
            "duration_ms": round(duration_ms, 1),
        },
    )


def _create_from_file(db, storage, patient, **kwargs) -> ClinicalDocumentResponse:
    """Shared by all three upload routes above: every failure mode
    specific to *this file type* (wrong extension, bad encoding, no
    extractable text, ...) has already been checked by the caller before
    this runs, so the only new failure possible here is the storage
    backend itself being unreachable, reported as a 503, the same status
    `POST /patients/{patient_id}/analyses` already uses for "a configured
    external dependency failed" (see app/api/routes/analyses.py).
    """
    try:
        return create_clinical_document_from_file(db, storage, patient, **kwargs)
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=STORAGE_UNAVAILABLE_DETAIL,
        ) from error


@router.get("", response_model=list[ClinicalDocumentResponse])
def list_documents(
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> list[ClinicalDocumentResponse]:
    return get_clinical_documents_for_patient(db, patient.id)


@router.get("/{document_id}", response_model=ClinicalDocumentResponse)
def read_document(
    document_id: int,
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> ClinicalDocumentResponse:
    document = get_clinical_document(db, patient.id, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )

    return document


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> StreamingResponse:
    """Streams the original uploaded file back from storage (Issue #58);
    never a redirect to a bucket URL, per that feature's "do not expose
    bucket URLs directly" requirement: the object's bytes pass through
    this process, and the client never learns anything about where or how
    it's actually stored.
    """
    try:
        result = get_clinical_document_content(db, storage, patient.id, document_id)
    except DocumentHasNoStoredFileError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NO_STORED_FILE_DETAIL,
        ) from None
    except ObjectNotFoundError:
        # The database has a storage_key, but storage itself has nothing
        # at it, a genuine inconsistency (e.g. an object deleted directly
        # from the bucket, outside this application). Reported to the
        # caller the same way as "no stored file," since that's true from
        # their point of view either way, but logged, unlike the
        # ordinary, expected case above, since it means something is
        # wrong that a provider can't fix by doing anything differently.
        logger.warning(
            "Document has a storage_key with no matching object in storage",
            extra={
                "event": "storage_object_missing",
                "patient_id": patient.id,
                "document_id": document_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NO_STORED_FILE_DETAIL,
        ) from None
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=STORAGE_UNAVAILABLE_DETAIL,
        ) from error

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )

    document, stored_object = result

    return StreamingResponse(
        iter([stored_object.content]),
        media_type=stored_object.content_type,
        headers={"Content-Disposition": f'attachment; filename="{document.file_name}"'},
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    document_id: int,
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> None:
    deleted = delete_clinical_document(db, storage, patient.id, document_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )
