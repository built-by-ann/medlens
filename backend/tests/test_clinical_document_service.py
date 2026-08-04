from datetime import date

import pytest

from app.core.security import hash_password
from app.models.patient import Patient
from app.models.user import User
from app.schemas.clinical_document import ClinicalDocumentCreate
from app.services.clinical_document_service import (
    DocumentHasNoStoredFileError,
    create_clinical_document,
    create_clinical_document_from_file,
    delete_clinical_document,
    get_clinical_document,
    get_clinical_document_content,
)
from app.storage.base import ObjectNotFoundError, StorageError, StorageService, StoredObject
from app.storage.local import LocalStorageService


def _create_user(db, email="storage.service.user@example.com"):
    user = User(email=email, hashed_password=hash_password("correcthorse123"), name="Storage User")
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def _create_patient(db, user, **overrides):
    defaults = {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": date(1980, 5, 14),
        "status": "active",
    }
    defaults.update(overrides)

    patient = Patient(user_id=user.id, **defaults)
    db.add(patient)
    db.commit()
    db.refresh(patient)

    return patient


class _AlwaysFailsOnDelete(StorageService):
    """A StorageService that uploads/downloads normally but always fails
    to delete - used to prove delete_clinical_document treats a storage
    failure as non-fatal (Issue #58's "handle partial failures safely")
    rather than letting it prevent the database row from being deleted.
    """

    def __init__(self):
        self._objects: dict[str, StoredObject] = {}

    def upload(self, key, content, content_type) -> None:
        self._objects[key] = StoredObject(content=content, content_type=content_type)

    def download(self, key) -> StoredObject:
        if key not in self._objects:
            raise ObjectNotFoundError(key)

        return self._objects[key]

    def delete(self, key) -> None:
        raise StorageError("simulated S3 outage")


def test_create_from_file_uploads_to_storage_and_persists_metadata(db, tmp_path):
    user = _create_user(db)
    patient = _create_patient(db, user)
    storage = LocalStorageService(base_dir=str(tmp_path))

    document = create_clinical_document_from_file(
        db,
        storage,
        patient,
        document_type="visit_note",
        title="Visit",
        raw_text="Patient reports improvement.",
        file_name="note.txt",
        file_type="txt",
        content=b"Patient reports improvement.",
        content_type="text/plain",
    )

    assert document.storage_key is not None
    assert document.content_type == "text/plain"
    assert document.file_size_bytes == len(b"Patient reports improvement.")
    assert storage.download(document.storage_key).content == b"Patient reports improvement."


def test_create_from_file_generates_a_different_key_for_each_upload(db, tmp_path):
    # "never overwrite an existing object" - proven here by uploading the
    # exact same filename twice and confirming both objects survive
    # independently, rather than the second silently replacing the first.
    user = _create_user(db)
    patient = _create_patient(db, user)
    storage = LocalStorageService(base_dir=str(tmp_path))

    first = create_clinical_document_from_file(
        db,
        storage,
        patient,
        document_type="visit_note",
        title="First",
        raw_text="first version",
        file_name="note.txt",
        file_type="txt",
        content=b"first version",
        content_type="text/plain",
    )
    second = create_clinical_document_from_file(
        db,
        storage,
        patient,
        document_type="visit_note",
        title="Second",
        raw_text="second version",
        file_name="note.txt",
        file_type="txt",
        content=b"second version",
        content_type="text/plain",
    )

    assert first.storage_key != second.storage_key
    assert storage.download(first.storage_key).content == b"first version"
    assert storage.download(second.storage_key).content == b"second version"


def test_create_from_file_cleans_up_the_uploaded_object_when_the_db_commit_fails(
    db, tmp_path, monkeypatch
):
    user = _create_user(db)
    patient = _create_patient(db, user)
    real_storage = LocalStorageService(base_dir=str(tmp_path))
    uploaded_keys: list[str] = []
    real_upload = real_storage.upload

    def _spying_upload(key, content, content_type):
        uploaded_keys.append(key)
        real_upload(key, content, content_type)

    monkeypatch.setattr(real_storage, "upload", _spying_upload)

    def _failing_commit():
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(db, "commit", _failing_commit)

    with pytest.raises(RuntimeError, match="simulated database failure"):
        create_clinical_document_from_file(
            db,
            real_storage,
            patient,
            document_type="visit_note",
            title="Visit",
            raw_text="text",
            file_name="note.txt",
            file_type="txt",
            content=b"content that should not be left behind",
            content_type="text/plain",
        )

    # Proves the upload genuinely happened (commit failed after it, not
    # before) - a version of this test that never actually uploaded
    # anything would trivially pass the ObjectNotFoundError check below
    # too, without proving cleanup did anything at all.
    assert len(uploaded_keys) == 1

    monkeypatch.undo()
    with pytest.raises(ObjectNotFoundError):
        real_storage.download(uploaded_keys[0])


def test_pasted_text_document_has_no_storage_key(db):
    user = _create_user(db)
    patient = _create_patient(db, user)

    document = create_clinical_document(
        db,
        patient,
        ClinicalDocumentCreate(document_type="visit_note", title="Pasted", raw_text="text"),
    )

    assert document.storage_key is None


def test_get_content_returns_the_stored_bytes_for_an_uploaded_document(db, tmp_path):
    user = _create_user(db)
    patient = _create_patient(db, user)
    storage = LocalStorageService(base_dir=str(tmp_path))
    document = create_clinical_document_from_file(
        db,
        storage,
        patient,
        document_type="visit_note",
        title="Visit",
        raw_text="text",
        file_name="note.txt",
        file_type="txt",
        content=b"original bytes",
        content_type="text/plain",
    )

    result = get_clinical_document_content(db, storage, patient.id, document.id)

    assert result is not None
    fetched_document, stored_object = result
    assert fetched_document.id == document.id
    assert stored_object.content == b"original bytes"
    assert stored_object.content_type == "text/plain"


def test_get_content_returns_none_for_a_nonexistent_document(db, tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path))

    assert get_clinical_document_content(db, storage, patient_id=1, document_id=999999) is None


def test_get_content_raises_for_a_document_with_no_stored_file(db, tmp_path):
    user = _create_user(db)
    patient = _create_patient(db, user)
    storage = LocalStorageService(base_dir=str(tmp_path))
    document = create_clinical_document(
        db,
        patient,
        ClinicalDocumentCreate(document_type="visit_note", title="Pasted", raw_text="text"),
    )

    with pytest.raises(DocumentHasNoStoredFileError):
        get_clinical_document_content(db, storage, patient.id, document.id)


def test_delete_removes_the_document_and_its_storage_object(db, tmp_path):
    user = _create_user(db)
    patient = _create_patient(db, user)
    storage = LocalStorageService(base_dir=str(tmp_path))
    document = create_clinical_document_from_file(
        db,
        storage,
        patient,
        document_type="visit_note",
        title="Visit",
        raw_text="text",
        file_name="note.txt",
        file_type="txt",
        content=b"content",
        content_type="text/plain",
    )
    storage_key = document.storage_key

    deleted = delete_clinical_document(db, storage, patient.id, document.id)

    assert deleted is True
    assert get_clinical_document(db, patient.id, document.id) is None
    with pytest.raises(ObjectNotFoundError):
        storage.download(storage_key)


def test_delete_succeeds_even_when_no_storage_object_exists(db, tmp_path):
    user = _create_user(db)
    patient = _create_patient(db, user)
    storage = LocalStorageService(base_dir=str(tmp_path))
    document = create_clinical_document(
        db,
        patient,
        ClinicalDocumentCreate(document_type="visit_note", title="Pasted", raw_text="text"),
    )

    deleted = delete_clinical_document(db, storage, patient.id, document.id)

    assert deleted is True


def test_delete_removes_the_database_row_even_when_storage_deletion_fails(db):
    # The core "handle partial failures safely" guarantee: a storage-side
    # failure during delete must never leave the document still visible
    # through the API while its file is stuck undeletable in storage - the
    # database row (what the user actually sees as "gone") is removed
    # regardless.
    user = _create_user(db)
    patient = _create_patient(db, user)
    failing_storage = _AlwaysFailsOnDelete()
    document = create_clinical_document_from_file(
        db,
        failing_storage,
        patient,
        document_type="visit_note",
        title="Visit",
        raw_text="text",
        file_name="note.txt",
        file_type="txt",
        content=b"content",
        content_type="text/plain",
    )

    deleted = delete_clinical_document(db, failing_storage, patient.id, document.id)

    assert deleted is True
    assert get_clinical_document(db, patient.id, document.id) is None
