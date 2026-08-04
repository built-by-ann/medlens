from abc import ABC, abstractmethod
from dataclasses import dataclass


class StorageError(Exception):
    """Raised when a storage backend cannot complete an operation for any
    reason other than the object simply not existing (see
    ObjectNotFoundError below) - a network failure, a permissions problem,
    an unexpected response from the backend. Callers only need to handle
    this one exception type (plus ObjectNotFoundError) regardless of which
    backend is active, the same pattern AIProviderError already
    establishes for AI providers (app/ai/providers/base.py).
    """


class ObjectNotFoundError(StorageError):
    """Raised by download()/delete() when the given key has no
    corresponding object. Split out from the general StorageError so
    callers that want to treat "already gone" as a non-fatal case (see
    delete_clinical_document, app/services/clinical_document_service.py)
    can catch this specifically without swallowing every other failure.
    """


@dataclass
class StoredObject:
    """What download() returns - the object's bytes plus the content type
    it was uploaded with, so a caller can stream it back with the correct
    Content-Type without needing a second lookup.
    """

    content: bytes
    content_type: str


class StorageService(ABC):
    """Common interface every file-storage backend must satisfy.

    Business logic (the clinical document service and routes) depends
    only on this interface, never on a specific backend, so which backend
    is active is a matter of configuration (see app/storage/service.py),
    not conditionals scattered through upload/download/delete code. Mirrors
    the AIProvider interface (app/ai/providers/base.py) - same shape, same
    reasoning, applied to a different pluggable dependency.
    """

    @abstractmethod
    def upload(self, key: str, content: bytes, content_type: str) -> None:
        """Stores `content` under `key`. Callers are responsible for
        generating a key that does not already exist (see
        app/services/clinical_document_service.py's key generation) -
        implementations are not required to check for or reject an
        overwrite themselves.

        Raises:
            StorageError: if the upload fails for any reason.
        """
        raise NotImplementedError

    @abstractmethod
    def download(self, key: str) -> StoredObject:
        """Retrieves the object stored under `key`.

        Raises:
            ObjectNotFoundError: if no object exists at `key`.
            StorageError: if the download fails for any other reason.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        """Deletes the object stored under `key`.

        Raises:
            ObjectNotFoundError: if no object exists at `key`.
            StorageError: if the deletion fails for any other reason.
        """
        raise NotImplementedError
