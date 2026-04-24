from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    DB_ADMIN_URL: str = ""
    DB_ADMIN_USER: str = ""
    DB_ADMIN_PASSWORD: str = ""
    DB_ADMIN_HOST: str = ""
    DB_ADMIN_PORT: int | None = None
    DB_ADMIN_DB: str = ""
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    LIBRARY_FILES_ROOT: str = "/var/lib/forgelab/"
    NAS_MOUNT_ROOT: str = "/mnt/forgelab"
    LOGS_FILES_ROOT: str = "/var/log/forgelab"
    TEMP_FILES_ROOT: str = "/var/cache/forgelab"
    FILE_REMOVE_ATTEMPTS: int = 5
    FILE_REMOVE_RETRY_SECONDS: float = 0.25
    WORKER_NOTIFY_TIMEOUT_SECONDS: float = 30.0
    WORKER_RECONCILE_INTERVAL_SECONDS: float = 60.0
    WORKER_HEARTBEAT_SECONDS: float = 30.0
    WORKER_LEASE_TIMEOUT_SECONDS: float = 300.0

    class Config:
        env_file = Path(__file__).parent.parent / ".env"


settings = Settings()
