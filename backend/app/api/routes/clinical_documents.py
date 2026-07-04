from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.clinical_document import ClinicalDocumentCreate, ClinicalDocumentResponse
from app.services.clinical_document_service import (
    create_clinical_document,
    delete_clinical_document,
    get_clinical_document,
    get_clinical_documents_for_user,
)

router = APIRouter(prefix="/clinical-documents", tags=["clinical-documents"])

NOT_FOUND_DETAIL = "Clinical document not found"


@router.post(
    "",
    response_model=ClinicalDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    document_in: ClinicalDocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClinicalDocumentResponse:
    return create_clinical_document(db, current_user.id, document_in)


@router.get("", response_model=list[ClinicalDocumentResponse])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ClinicalDocumentResponse]:
    return get_clinical_documents_for_user(db, current_user.id)


@router.get("/{document_id}", response_model=ClinicalDocumentResponse)
def read_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClinicalDocumentResponse:
    document = get_clinical_document(db, current_user.id, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )

    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    deleted = delete_clinical_document(db, current_user.id, document_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )
