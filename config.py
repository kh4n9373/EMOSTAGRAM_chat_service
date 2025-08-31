from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    letta_base_url: str = "http://localhost:8283"
    backend_url: str = "http://localhost:5001/api/v1"

    openai_api_key: str 
    openai_base_url: str 
    
    datastax_token: str
    astra_client_id: str
    astra_client_secret: str
    cassandra_enabled: bool = True
    
    mongodb_url: str
    kafka_bootstrap: str
    @property
    def debug(self) -> bool:
        return self.environment == "dev"

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

settings = Settings()
