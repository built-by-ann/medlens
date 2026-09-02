import logging
import time
import uuid

from sqlalchemy.orm import Session, selectinload

from app.models.clinical_document import ClinicalDocument
from app.models.patient import Patient
from app.schemas.clinical_document import ClinicalDocumentCreate
from app.storage.base import ObjectNotFoundError, StorageError, StorageService, StoredObject

logger = logging.getLogger(__name__)

DEFAULT_FILE_TYPE = "manual_entry"
TXT_FILE_TYPE = "txt"
PDF_FILE_TYPE = "pdf"
CSV_FILE_TYPE = "csv"


class DocumentHasNoStoredFileError(Exception):
    """Raised by get_clinical_document_content when a document exists but
    has no storage_key: a pasted-text document (never had a file to
    begin with) or one created before Issue #58. Distinct from the
    document itself not existing, which callers already handle as a 404
    via get_clinical_document returning None.
    """


def _build_storage_key(patient_id: int, file_name: str) -> str:
    # A uuid4 segment, not the filename alone, is what actually satisfies
    # "never overwrite an existing object": two uploads of the same
    # filename (even for the same patient) get different keys. The
    # filename is kept in the key purely so a key is still human-legible
    # when browsing a bucket directly; it plays no role in uniqueness.
    return f"clinical-documents/{patient_id}/{uuid.uuid4()}/{file_name}"


def create_clinical_document(
    db: Session, patient: Patient, document_in: ClinicalDocumentCreate
) -> ClinicalDocument:
    document = ClinicalDocument(
        patient_id=patient.id,
        document_type=document_in.document_type,
        title=document_in.title,
        raw_text=document_in.raw_text,
        file_name=None,
        file_type=DEFAULT_FILE_TYPE,
        # No storage_key: pasted text has no original file to store -
        # see app/models/clinical_document.py.
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def create_clinical_document_from_file(
    db: Session,
    storage: StorageService,
    patient: Patient,
    document_type: str,
    title: str,
    raw_text: str,
    file_name: str,
    file_type: str,
    content: bytes,
    content_type: str,
    started_at: float | None = None,
) -> ClinicalDocument:
    """Uploads the original file to storage, then persists the document
    with the resulting metadata. Text extraction (producing `raw_text`)
    already happened in the caller (app/api/routes/clinical_documents.py)
    before this is called; a PDF/CSV/TXT that fails extraction never
    reaches here, so this function never uploads a file for a document
    that wouldn't have been created anyway.

    started_at (Issue #60): a time.monotonic() reading from the top of the
    calling route handler, used only to compute the document_uploaded log's
    duration_ms below: the "document upload processing" span covers the
    whole route (validation, extraction, this function), not just the part
    inside this function, so the timer has to start before this function is
    even called. Optional (defaults to now, i.e. ~0ms) so this function
    still works standalone, e.g. from a test that doesn't care about timing.
    """
    if started_at is None:
        started_at = time.monotonic()
    storage_key = _build_storage_key(patient.id, file_name)
    storage.upload(storage_key, content, content_type)

    document = ClinicalDocument(
        patient_id=patient.id,
        document_type=document_type,
        title=title,
        raw_text=raw_text,
        file_name=file_name,
        file_type=file_type,
        storage_key=storage_key,
        content_type=content_type,
        file_size_bytes=len(content),
    )

    try:
        db.add(document)
        db.commit()
    except Exception:
        # The upload above already succeeded; without this, a DB failure
        # here would leave an object in storage with no ClinicalDocument
        # row ever pointing to it. Best-effort: a secondary failure while
        # cleaning up is logged, not raised, so the caller still sees the
        # original database error rather than a confusing new one about
        # storage.
        try:
            storage.delete(storage_key)
        except StorageError:
            logger.warning(
                "Failed to clean up orphaned storage object after a failed document creation",
                extra={"event": "storage_cleanup_failed"},
            )
        raise

    db.refresh(document)

    duration_ms = (time.monotonic() - started_at) * 1000
    logger.info(
        "Clinical document uploaded",
        extra={
            "event": "document_uploaded",
            "patient_id": patient.id,
            "document_id": document.id,
            "file_type": file_type,
            "duration_ms": round(duration_ms, 1),
        },
    )

    return document


def get_clinical_documents_for_patient(db: Session, patient_id: int) -> list[ClinicalDocument]:
    # selectinload avoids an N+1 query for analysis_count (Issue #146),
    # which reads the analyses relationship on every returned document.
    return (
        db.query(ClinicalDocument)
        .options(selectinload(ClinicalDocument.analyses))
        .filter(ClinicalDocument.patient_id == patient_id)
        .order_by(ClinicalDocument.created_at.desc())
        .all()
    )


def get_clinical_document(
    db: Session, patient_id: int, document_id: int
) -> ClinicalDocument | None:
    return (
        db.query(ClinicalDocument)
        .options(selectinload(ClinicalDocument.analyses))
        .filter(
            ClinicalDocument.id == document_id,
            ClinicalDocument.patient_id == patient_id,
        )
        .first()
    )


def get_clinical_document_content(
    db: Session, storage: StorageService, patient_id: int, document_id: int
) -> tuple[ClinicalDocument, StoredObject] | None:
    """Used by the download route. Returns None only when the document
    itself doesn't exist or doesn't belong to this patient, the same
    "not found" case get_clinical_document already handles, so the route
    can keep using its existing 404 for that. A document that exists but
    has no stored file (storage_key is null) raises
    DocumentHasNoStoredFileError instead, a distinct, more specific
    condition the route reports separately.
    """
    document = get_clinical_document(db, patient_id, document_id)

    if document is None:
        return None

    if document.storage_key is None:
        raise DocumentHasNoStoredFileError(document_id)

    return document, storage.download(document.storage_key)


def delete_clinical_document(
    db: Session, storage: StorageService, patient_id: int, document_id: int
) -> bool:
    document = get_clinical_document(db, patient_id, document_id)

    if document is None:
        return False

    storage_key = document.storage_key

    db.delete(document)
    db.commit()

    logger.info(
        "Clinical document deleted",
        extra={"event": "document_deleted", "patient_id": patient_id, "document_id": document_id},
    )

    # The database record, what the user actually sees as "this document
    # is gone", is already correctly deleted at this point, regardless of
    # what happens below. Deleting the storage object second, and treating
    # its failure as non-fatal, means the worst case is a harmless orphaned
    # object in storage (a cleanup/cost concern), never a document that
    # still exists but points at something that no longer does.
    if storage_key is not None:
        try:
            storage.delete(storage_key)
        except ObjectNotFoundError:
            pass
        except StorageError:
            logger.warning(
                "Failed to delete storage object for a deleted document",
                extra={
                    "event": "storage_delete_failed",
                    "patient_id": patient_id,
                    "document_id": document_id,
                },
            )

    return True
