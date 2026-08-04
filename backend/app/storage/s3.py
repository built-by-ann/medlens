import boto3
from botocore.exceptions import ClientError

from app.storage.base import ObjectNotFoundError, StorageError, StorageService, StoredObject


class S3StorageService(StorageService):
    """Stores objects in a private S3 bucket. Selected via
    Settings.storage_backend == "s3" (see app/storage/service.py).

    Credentials: `access_key_id`/`secret_access_key` are passed through to
    boto3 only when both are provided (e.g. a developer's own AWS
    credentials, for testing against a real bucket locally). When either
    is omitted - the expected production configuration, per this feature's
    "use IAM credentials" requirement - boto3 falls back to its normal
    credential provider chain, which includes an IAM role attached to the
    EC2 instance. Neither this class nor its caller ever logs a credential
    value; boto3's own request signing never surfaces one to application
    code either.
    """

    def __init__(
        self,
        bucket_name: str,
        region: str,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ):
        self._bucket_name = bucket_name
        client_kwargs: dict[str, str] = {"region_name": region}

        if access_key_id and secret_access_key:
            client_kwargs["aws_access_key_id"] = access_key_id
            client_kwargs["aws_secret_access_key"] = secret_access_key

        self._client = boto3.client("s3", **client_kwargs)

    def upload(self, key: str, content: bytes, content_type: str) -> None:
        try:
            self._client.put_object(
                Bucket=self._bucket_name,
                Key=key,
                Body=content,
                ContentType=content_type,
                # Never public - this application has no use case for a
                # publicly reachable object, and the bucket itself is
                # expected to block public access at the account/bucket
                # level regardless (see docs/deployment.md). ACL is set
                # explicitly anyway as defense in depth, not as the only
                # thing standing between an object and the public internet.
                ACL="private",
            )
        except ClientError as error:
            raise StorageError(f"Failed to upload object to S3: {key}") from error

    def download(self, key: str) -> StoredObject:
        try:
            response = self._client.get_object(Bucket=self._bucket_name, Key=key)
        except ClientError as error:
            if _is_not_found(error):
                raise ObjectNotFoundError(f"No S3 object at key: {key}") from error

            raise StorageError(f"Failed to download object from S3: {key}") from error

        try:
            content = response["Body"].read()
        except Exception as error:
            raise StorageError(f"Failed to read S3 object body: {key}") from error

        content_type = response.get("ContentType") or "application/octet-stream"

        return StoredObject(content=content, content_type=content_type)

    def delete(self, key: str) -> None:
        # S3's own DeleteObject is idempotent - it returns success whether
        # or not the key existed, unlike a typical filesystem `unlink`. A
        # HeadObject check first is what actually lets this class report
        # ObjectNotFoundError the same way LocalStorageService does, so
        # callers (delete_clinical_document) can treat both backends
        # identically rather than special-casing S3's different default.
        try:
            self._client.head_object(Bucket=self._bucket_name, Key=key)
        except ClientError as error:
            if _is_not_found(error):
                raise ObjectNotFoundError(f"No S3 object at key: {key}") from error

            raise StorageError(f"Failed to check for S3 object before delete: {key}") from error

        try:
            self._client.delete_object(Bucket=self._bucket_name, Key=key)
        except ClientError as error:
            raise StorageError(f"Failed to delete object from S3: {key}") from error


def _is_not_found(error: ClientError) -> bool:
    code = error.response.get("Error", {}).get("Code", "")

    return code in ("404", "NoSuchKey", "NotFound")
