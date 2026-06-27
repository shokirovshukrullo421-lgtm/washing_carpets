from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str
    DB_USER: str
    DB_PASS: str
    SUPER_ADMIN_TG_ID: int = 6563817580

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()