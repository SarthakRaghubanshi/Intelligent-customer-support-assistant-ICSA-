import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Compute the absolute project root from this file's location.
# config.py lives at backend/core/config.py → root is 3 levels up.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

# Environment-to-database mapping (absolute paths, launch-directory independent).
# In production, set DATABASE_URL explicitly (e.g. a Postgres URL); it always
# takes precedence over this map.
_ENV_DB_MAP = {
    "development": f"sqlite:///{os.path.join(_PROJECT_ROOT, 'data', 'saas.db')}",
    "uat":         f"sqlite:///{os.path.join(_PROJECT_ROOT, 'data', 'uat_saas.db')}",
    "test":        f"sqlite:///{os.path.join(_PROJECT_ROOT, 'data', 'test.db')}",
    "production":  f"sqlite:///{os.path.join(_PROJECT_ROOT, 'data', 'prod_saas.db')}",
}

_JWT_DEV_FALLBACK = "fallback_local_secret_key_for_development_purposes_only_123456"
_ADMIN_PW_DEFAULT = "AdminPass123!"


class Config:
    # Active application environment: development | uat | test | production
    # ("prod" is normalized to "production" so the env selects the production
    # database and IS_PRODUCTION agree — otherwise a prod deploy would silently
    # fall back to the development DB.)
    APP_ENV: str = os.getenv("APP_ENV", "development").strip().lower()
    if APP_ENV == "prod":
        APP_ENV = "production"

    # Select the database URL based on APP_ENV.
    # An explicit DATABASE_URL env var always takes precedence over the map.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        _ENV_DB_MAP.get(APP_ENV, _ENV_DB_MAP["development"])
    )

    # Ensure the data directory exists when using a local SQLite path
    if DATABASE_URL.startswith("sqlite:///"):
        _db_path = DATABASE_URL.replace("sqlite:///", "")
        _db_dir = os.path.dirname(_db_path)
        if _db_dir and not os.path.exists(_db_dir):
            os.makedirs(_db_dir, exist_ok=True)

    IS_PRODUCTION: bool = APP_ENV == "production"

    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", _JWT_DEV_FALLBACK)
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    # Permanent administrator account seeding credentials.
    # Override via environment variables in production; never commit plain-text passwords.
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@icsa.com")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", _ADMIN_PW_DEFAULT)


# Fail-HARD security check: in production the secrets MUST be overridden.
# A misconfigured production deploy that signs JWTs with a publicly-known dev
# secret (or ships the demo admin password) is a critical vulnerability, so we
# refuse to start rather than merely logging a warning. Set
# ALLOW_INSECURE_DEFAULTS=true only for a deliberate, throwaway prod smoke test.
if Config.IS_PRODUCTION and os.getenv("ALLOW_INSECURE_DEFAULTS", "false").strip().lower() not in ("1", "true", "yes"):
    _insecure = []
    if Config.JWT_SECRET_KEY == _JWT_DEV_FALLBACK:
        _insecure.append("JWT_SECRET_KEY is the insecure dev default")
    if Config.ADMIN_PASSWORD == _ADMIN_PW_DEFAULT:
        _insecure.append("ADMIN_PASSWORD is the demo default")
    if _insecure:
        raise RuntimeError(
            "[SECURITY] Refusing to start in production with insecure defaults: "
            + "; ".join(_insecure)
            + ". Set strong JWT_SECRET_KEY / ADMIN_PASSWORD environment variables "
            "(or set ALLOW_INSECURE_DEFAULTS=true to override, not recommended)."
        )

