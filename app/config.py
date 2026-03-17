"""Application settings module."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration."""

    app_name: str = "CozyBuddy"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "sqlite+aiosqlite:///./cozybuddy.db"

    llm_default_provider: str = "vllm"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.7

    vllm_base_url: str = "http://localhost:8080/v1"
    vllm_model: str = "llama-3.1-8b"
    vllm_api_key: str = "not-needed"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    rag_db_path: str = "./data/chromadb"
    rag_embedding_model: str = "intfloat/multilingual-e5-small"
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50

    tts_model_path: str = "./models/piper"

    stt_model_size: str = "small"
    stt_device: str = "cuda"

    log_level: str = "INFO"
    log_file: str = "logs/cozybuddy.log"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
