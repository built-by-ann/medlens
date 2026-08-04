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
