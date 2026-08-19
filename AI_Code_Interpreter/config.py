from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """
    Central configuration for the application.
    """

    BASE_URL: str = os.getenv("BASE_URL", "")
    API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "")

    TEMPERATURE: float = 0.0
    MAX_TOKENS: int = 4096

    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "outputs"
    LOG_DIR: str = "logs"


config = Config()