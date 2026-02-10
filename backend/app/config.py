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

    class Config:
        env_file = Path(__file__).parent.parent / ".env"

settings = Settings()
