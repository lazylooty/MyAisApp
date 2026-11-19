from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg2://realtor_user:realtor_secret_password@localhost:5432/realtor_db"
    )
    storage_dir: Path = Path("/app/storage")
    agency_name: str = "ИП Голубина Ольга Геннадьевна"
    secret_key: str = "change-me-in-production-super-secret-jwt-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def templates_dir(self) -> Path:
        path = self.storage_dir / "templates"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def contracts_dir(self) -> Path:
        path = self.storage_dir / "contracts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def photos_dir(self) -> Path:
        path = self.storage_dir / "photos"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_storage_dirs(self) -> None:
        _ = self.templates_dir
        _ = self.contracts_dir
        _ = self.photos_dir


settings = Settings()
