from sqlalchemy.orm import Session

from app.models.clinical_document import ClinicalDocument
from app.schemas.clinical_document import ClinicalDocumentCreate

DEFAULT_FILE_TYPE = "manual_entry"
TXT_FILE_TYPE = "txt"
PDF_FILE_TYPE = "pdf"


def create_clinical_document(
    db: Session, user_id: int, document_in: ClinicalDocumentCreate
) -> ClinicalDocument:
    document = ClinicalDocument(
        user_id=user_id,
        document_type=document_in.document_type,
        title=document_in.title,
        raw_text=document_in.raw_text,
        file_name=None,
        file_type=DEFAULT_FILE_TYPE,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def create_clinical_document_from_file(
    db: Session,
    user_id: int,
    document_type: str,
    title: str,
    raw_text: str,
    file_name: str,
    file_type: str,
) -> ClinicalDocument:
    document = ClinicalDocument(
        user_id=user_id,
        document_type=document_type,
        title=title,
        raw_text=raw_text,
        file_name=file_name,
        file_type=file_type,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def get_clinical_documents_for_user(db: Session, user_id: int) -> list[ClinicalDocument]:
    return (
        db.query(ClinicalDocument)
        .filter(ClinicalDocument.user_id == user_id)
        .order_by(ClinicalDocument.created_at.desc())
        .all()
    )


def get_clinical_document(
    db: Session, user_id: int, document_id: int
) -> ClinicalDocument | None:
    return (
        db.query(ClinicalDocument)
        .filter(
            ClinicalDocument.id == document_id,
            ClinicalDocument.user_id == user_id,
        )
        .first()
    )


def delete_clinical_document(db: Session, user_id: int, document_id: int) -> bool:
    document = get_clinical_document(db, user_id, document_id)

    if document is None:
        return False

    db.delete(document)
    db.commit()

    return True
