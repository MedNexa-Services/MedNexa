from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEDNEXA_", env_file=".env", extra="ignore")

    app_name: str = "MedNexa API"
    database_url: str = "postgresql+asyncpg://mednexa:mednexa@localhost:5434/mednexa"
    test_database_url: str = "postgresql+asyncpg://mednexa:mednexa@localhost:5434/mednexa_test"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    # Prefixed to 10-digit local numbers when normalizing phones (91 = India).
    default_country_code: str = "91"

    # Authentication & JWT (Part 5 - Task 5.3)
    jwt_secret: str = "mednexa-super-secret-jwt-signing-key-32bytes-minimum"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 120
    admin_email: str = "admin@hospital.com"
    admin_password: str = "admin123"
    auth_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
