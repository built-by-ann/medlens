from app.core.config import Settings, settings
from app.storage.base import StorageService
from app.storage.local import LocalStorageService
from app.storage.s3 import S3StorageService


def build_storage_service(app_settings: Settings) -> StorageService:
    """The single place storage_backend is ever branched on; everywhere
    else in the application (routes, services) depends only on the
    StorageService interface, never on this choice. Settings.storage_backend
    is validated at startup (Settings' own model_validator) to guarantee
    the "s3" branch here always has the configuration it needs, so this
    function itself never has to re-validate or raise a config error.
    """
    if app_settings.storage_backend == "s3":
        return S3StorageService(
            bucket_name=app_settings.s3_bucket_name,  # type: ignore[arg-type]
            region=app_settings.aws_region,  # type: ignore[arg-type]
            access_key_id=app_settings.aws_access_key_id,
            secret_access_key=app_settings.aws_secret_access_key,
        )

    return LocalStorageService(base_dir=app_settings.local_storage_dir)


def get_storage_service() -> StorageService:
    """FastAPI dependency, mirrors get_ai_summary_service's shape
    (app/ai/service.py) for the same reason: routes declare a dependency
    on this function, never on a concrete backend class, so swapping the
    active backend is a configuration change, not a code change.
    """
    return build_storage_service(settings)
