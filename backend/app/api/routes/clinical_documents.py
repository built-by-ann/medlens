from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.clinical_document import ClinicalDocumentCreate, ClinicalDocumentResponse
from app.services.clinical_document_service import (
    TXT_FILE_TYPE,
    create_clinical_document,
    create_clinical_document_from_file,
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


@router.post(
    "/upload-txt",
    response_model=ClinicalDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_txt_document(
    document_type: str = Form(min_length=1),
    title: str = Form(min_length=1),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClinicalDocumentResponse:
    is_txt_extension = (file.filename or "").lower().endswith(".txt")
    is_plain_text_content_type = file.content_type == "text/plain"

    if not (is_txt_extension or is_plain_text_content_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only .txt or text/plain files are supported",
        )

    contents = file.file.read()

    try:
        raw_text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File must be valid UTF-8 encoded text",
        )

    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded file is empty",
        )

    return create_clinical_document_from_file(
        db,
        current_user.id,
        document_type=document_type,
        title=title,
        raw_text=raw_text,
        file_name=file.filename,
        file_type=TXT_FILE_TYPE,
    )


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
