from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    DATABASE_URL: str

    SECRET_KEY: str

    WEBHOOK_URL: str = ""

    class Config:
        env_file = ".env"


settings = Settings()

# Dynamic settings store (mutable at runtime)
runtime_settings = {
    "WEBHOOK_URL": settings.WEBHOOK_URL
}