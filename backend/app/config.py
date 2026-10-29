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

    # Authentication (Part 5 - Task 5.3). There are no defaults for secrets or
    # credentials on purpose: the server refuses to start until they are set
    # (see require_auth_config), so nobody ever runs with a published key.
    auth_enabled: bool = True  # False only for local development without login
    jwt_secret: str = ""  # 32+ random characters: `openssl rand -hex 32`
    jwt_access_token_expire_minutes: int = 120
    admin_email: str = ""
    admin_name: str = "Hospital Staff"
    # Plain, or a PBKDF2 hash made with `python -m app.core.security`.
    admin_password: str = ""
    # Lets the telephony service (Part 3) write call logs without a staff login. It is
    # accepted on the /calls routes only. Empty = disabled.
    service_api_key: str = ""

    def require_auth_config(self) -> None:
        """Raise RuntimeError, listing every problem, if auth is enabled but unusable."""
        if not self.auth_enabled:
            return
        problems = []
        if len(self.jwt_secret) < 32:
            problems.append(
                "MEDNEXA_JWT_SECRET must be at least 32 characters (openssl rand -hex 32)"
            )
        if not self.admin_email:
            problems.append("MEDNEXA_ADMIN_EMAIL is not set")
        if not self.admin_password:
            problems.append("MEDNEXA_ADMIN_PASSWORD is not set")
        if self.service_api_key and len(self.service_api_key) < 32:
            problems.append("MEDNEXA_SERVICE_API_KEY must be empty or at least 32 characters")
        if problems:
            raise RuntimeError(
                "Refusing to start with an unusable auth configuration:\n  - "
                + "\n  - ".join(problems)
                + "\n(Set MEDNEXA_AUTH_ENABLED=false only for local development.)"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
