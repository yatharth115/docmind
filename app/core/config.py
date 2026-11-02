from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    LLM_MODEL: str = "gemini-3.6-flash"

   
    ENABLE_RERANK: bool = True
    ALLOW_REGISTRATION: bool = True
    READ_ONLY_DOCS: bool = False
    ASK_LIMIT_PER_USER_PER_HOUR: int = 30
    ASK_LIMIT_GLOBAL_PER_HOUR: int = 300

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()