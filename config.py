from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = ""
    admin_login: str = "admin"
    admin_password: str = "change-me"
    public_access: bool = True
    gps_scheduler_enabled: bool = False
    secret_key: str = ""
    rate_limit_enabled: bool = True
    gps_interval_minutes: int = 5
    model_config = {"env_file": ".env"}

    @property
    def db_url(self) -> str:
        u = self.database_url or "sqlite+aiosqlite:///./data/tracking.db"
        return u.replace("postgresql://", "postgresql+asyncpg://", 1) if u.startswith("postgresql://") else u

settings = Settings()
