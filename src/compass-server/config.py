from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # The token Overland will use to write data
    write_token: str
    # The token Overland will use to read data
    read_token: str
    # Where to store location data
    storage_dir: Path = Path("data")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

def get_settings() -> Settings:
    return Settings()
