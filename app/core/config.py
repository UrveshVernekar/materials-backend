from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    PROJECT_NAME: str = "Materials Management"
    SECRET_KEY: str = "7b0b2e3f5a7e4b5c6d8e9f0a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p"

    class Config:
        env_file = ".env"

settings = Settings()