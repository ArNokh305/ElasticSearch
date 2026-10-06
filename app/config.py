from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://docsearch:docsearch@localhost:5432/docsearch"
    elasticsearch_url: str = "http://localhost:9200"
    es_index_name: str = "documents"
    search_overfetch_size: int = 200


settings = Settings()
