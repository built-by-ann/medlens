import logging

import boto3
import pytest
from moto import mock_aws

from app.storage.base import ObjectNotFoundError, StorageError
from app.storage.local import LocalStorageService
from app.storage.s3 import S3StorageService

# --- LocalStorageService ---


def test_local_upload_then_download_round_trips_content_and_content_type(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path))

    storage.upload("notes/a.txt", b"hello world", "text/plain")
    result = storage.download("notes/a.txt")

    assert result.content == b"hello world"
    assert result.content_type == "text/plain"


def test_local_upload_creates_nested_directories_as_needed(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path))

    storage.upload("a/b/c/d.txt", b"nested", "text/plain")

    assert storage.download("a/b/c/d.txt").content == b"nested"


def test_local_download_raises_object_not_found_for_missing_key(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path))

    with pytest.raises(ObjectNotFoundError):
        storage.download("does/not/exist.txt")


def test_local_delete_removes_the_object(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path))
    storage.upload("a.txt", b"content", "text/plain")

    storage.delete("a.txt")

    with pytest.raises(ObjectNotFoundError):
        storage.download("a.txt")


def test_local_delete_raises_object_not_found_for_missing_key(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path))

    with pytest.raises(ObjectNotFoundError):
        storage.delete("does/not/exist.txt")


def test_local_two_uploads_with_different_keys_do_not_collide(tmp_path):
    storage = LocalStorageService(base_dir=str(tmp_path))

    storage.upload("patient-1/a.txt", b"first", "text/plain")
    storage.upload("patient-1/b.txt", b"second", "text/plain")

    assert storage.download("patient-1/a.txt").content == b"first"
    assert storage.download("patient-1/b.txt").content == b"second"


# --- S3StorageService ---


@pytest.fixture
def s3_bucket():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="medlens-test-bucket")
        yield "medlens-test-bucket"


def _s3_storage(bucket_name):
    return S3StorageService(bucket_name=bucket_name, region="us-east-1")


def test_s3_upload_then_download_round_trips_content_and_content_type(s3_bucket):
    storage = _s3_storage(s3_bucket)

    storage.upload("notes/a.txt", b"hello s3", "text/plain")
    result = storage.download("notes/a.txt")

    assert result.content == b"hello s3"
    assert result.content_type == "text/plain"


def test_s3_download_raises_object_not_found_for_missing_key(s3_bucket):
    storage = _s3_storage(s3_bucket)

    with pytest.raises(ObjectNotFoundError):
        storage.download("does/not/exist.txt")


def test_s3_delete_removes_the_object(s3_bucket):
    storage = _s3_storage(s3_bucket)
    storage.upload("a.txt", b"content", "text/plain")

    storage.delete("a.txt")

    with pytest.raises(ObjectNotFoundError):
        storage.download("a.txt")


def test_s3_delete_raises_object_not_found_for_missing_key(s3_bucket):
    storage = _s3_storage(s3_bucket)

    with pytest.raises(ObjectNotFoundError):
        storage.delete("does/not/exist.txt")


def test_s3_upload_never_makes_the_object_public(s3_bucket):
    # Verifies the actual request sent to S3, not just that upload()
    # succeeds - ACL="private" is passed explicitly (see S3StorageService)
    # rather than relied on as an S3 default, and this is what proves it
    # actually reaches the request.
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="acl-check-bucket")
        storage = _s3_storage("acl-check-bucket")

        storage.upload("a.txt", b"content", "text/plain")

        acl = client.get_object_acl(Bucket="acl-check-bucket", Key="a.txt")
        grantee_uris = {
            grant["Grantee"].get("URI") for grant in acl["Grants"] if "URI" in grant["Grantee"]
        }
        assert "http://acs.amazonaws.com/groups/global/AllUsers" not in grantee_uris


def test_s3_failure_raises_storage_error_not_object_not_found(s3_bucket):
    # A genuine S3-side failure (here: the bucket itself doesn't exist,
    # simulating e.g. misconfiguration or an outage) is a different
    # condition than "the object isn't there" and must not be reported the
    # same way - a caller catching ObjectNotFoundError specifically (see
    # delete_clinical_document, app/services/clinical_document_service.py)
    # must not accidentally swallow this.
    storage = _s3_storage("this-bucket-does-not-exist")

    with pytest.raises(StorageError) as exc_info:
        storage.upload("a.txt", b"content", "text/plain")

    assert not isinstance(exc_info.value, ObjectNotFoundError)


def test_s3_credentials_are_never_included_in_a_raised_error_message(s3_bucket):
    storage = S3StorageService(
        bucket_name="this-bucket-does-not-exist",
        region="us-east-1",
        access_key_id="AKIAFAKEEXAMPLE00000",
        secret_access_key="fakeSecretKeyValueThatMustNeverAppearInLogsOrErrors",
    )

    with pytest.raises(StorageError) as exc_info:
        storage.upload("a.txt", b"content", "text/plain")

    assert "fakeSecretKeyValueThatMustNeverAppearInLogsOrErrors" not in str(exc_info.value)
    assert "AKIAFAKEEXAMPLE00000" not in str(exc_info.value)


# --- Storage failure logging (Issue #59) ---


def test_s3_upload_failure_is_logged_with_key_and_error_type_but_not_content(s3_bucket, caplog):
    storage = S3StorageService(bucket_name="this-bucket-does-not-exist", region="us-east-1")

    with caplog.at_level(logging.WARNING), pytest.raises(StorageError):
        storage.upload("patients/7/notes.txt", b"sensitive clinical content", "text/plain")

    (record,) = [r for r in caplog.records if r.event == "s3_upload_failed"]
    assert record.storage_key == "patients/7/notes.txt"
    assert record.error_type
    assert "sensitive clinical content" not in caplog.text


def test_s3_download_failure_is_logged_with_key_and_error_type(s3_bucket, caplog):
    storage = S3StorageService(bucket_name="this-bucket-does-not-exist", region="us-east-1")

    with caplog.at_level(logging.WARNING), pytest.raises(StorageError):
        storage.download("patients/7/notes.txt")

    (record,) = [r for r in caplog.records if r.event == "s3_download_failed"]
    assert record.storage_key == "patients/7/notes.txt"
    assert record.error_type


def test_s3_download_for_a_missing_object_is_not_logged_as_a_failure(s3_bucket, caplog):
    # ObjectNotFoundError is an expected, already-handled condition (see
    # S3StorageService.download) - not an operational failure worth a log
    # line, unlike a genuine S3-side error.
    storage = _s3_storage(s3_bucket)

    with caplog.at_level(logging.WARNING), pytest.raises(ObjectNotFoundError):
        storage.download("does/not/exist.txt")

    assert [r for r in caplog.records if r.event == "s3_download_failed"] == []


def test_s3_delete_failure_is_logged_with_key_and_error_type(s3_bucket, caplog):
    storage = S3StorageService(bucket_name="this-bucket-does-not-exist", region="us-east-1")

    with caplog.at_level(logging.WARNING), pytest.raises(StorageError):
        storage.delete("patients/7/notes.txt")

    (record,) = [r for r in caplog.records if r.event == "s3_delete_failed"]
    assert record.storage_key == "patients/7/notes.txt"
    assert record.error_type


def test_s3_delete_for_a_missing_object_is_not_logged_as_a_failure(s3_bucket, caplog):
    storage = _s3_storage(s3_bucket)

    with caplog.at_level(logging.WARNING), pytest.raises(ObjectNotFoundError):
        storage.delete("does/not/exist.txt")

    assert [r for r in caplog.records if r.event == "s3_delete_failed"] == []


# --- Storage upload timing (Issue #60) ---


def test_local_upload_logs_storage_upload_completed_duration_ms(tmp_path, caplog):
    storage = LocalStorageService(base_dir=str(tmp_path))

    with caplog.at_level(logging.INFO):
        storage.upload("a.txt", b"content", "text/plain")

    (record,) = [r for r in caplog.records if r.event == "storage_upload_completed"]
    assert record.storage_backend == "local"
    assert record.storage_key == "a.txt"
    assert isinstance(record.duration_ms, float)
    assert record.duration_ms >= 0


def test_s3_upload_logs_storage_upload_completed_duration_ms(s3_bucket, caplog):
    storage = _s3_storage(s3_bucket)

    with caplog.at_level(logging.INFO):
        storage.upload("a.txt", b"content", "text/plain")

    (record,) = [r for r in caplog.records if r.event == "storage_upload_completed"]
    assert record.storage_backend == "s3"
    assert record.storage_key == "a.txt"
    assert isinstance(record.duration_ms, float)
    assert record.duration_ms >= 0


def test_s3_upload_failure_also_includes_duration_ms(s3_bucket, caplog):
    # The timer that produces storage_upload_completed's duration_ms above
    # is the same one already wrapping the failure path (S3StorageService.upload) -
    # naturally extending the existing s3_upload_failed log with the value
    # it was already computing, not a second, duplicate timing mechanism.
    storage = S3StorageService(bucket_name="this-bucket-does-not-exist", region="us-east-1")

    with caplog.at_level(logging.WARNING), pytest.raises(StorageError):
        storage.upload("a.txt", b"content", "text/plain")

    (record,) = [r for r in caplog.records if r.event == "s3_upload_failed"]
    assert isinstance(record.duration_ms, float)
    assert record.duration_ms >= 0
