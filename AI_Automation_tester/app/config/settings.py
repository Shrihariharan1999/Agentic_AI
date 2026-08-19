from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Web Tester"
    app_env: str = "development"
    log_level: str = "INFO"

    llm_provider: str = "nvidia"

    google_api_key: str = ""
    google_model: str = "gemini-3.6-flash"

    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_api_key: str = ""
    nvidia_model: str = ""

    discovery_provider: str = "nvidia"
    discovery_model: str = ""

    discovery_structurer_provider: str = "nvidia"
    discovery_structurer_model: str = ""

    planner_provider: str = "nvidia"
    planner_model: str = ""

    test_writer_provider: str = "nvidia"
    test_writer_model: str = ""

    executor_provider: str = "nvidia"
    executor_model: str = ""

    failure_analyzer_provider: str = "nvidia"
    failure_analyzer_model: str = ""

    summary_provider: str = "nvidia"
    summary_model: str = ""

    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "ai-web-tester"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "ai_web_tester"
    mysql_user: str = "root"
    mysql_password: str = ""

    rag_index_path: str = "data/vector_store"

    max_test_cases: int = 50
    max_execution_retries: int = 2
    max_healing_attempts: int = 2

    allowed_target_domains: str = ""

    mcp_browser_enabled: bool = True
    mcp_browser_transport: str = "streamable_http"
    mcp_browser_url: str = ""
    mcp_browser_command: str = ""
    mcp_browser_args: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def mysql_url(self) -> str:
        return f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"

    def get_provider(self, agent_name: str) -> str:
        providers = {
            "discovery": self.discovery_provider,
            "discovery_structurer": self.discovery_structurer_provider,
            "planner": self.planner_provider,
            "test_writer": self.test_writer_provider,
            "executor": self.executor_provider,
            "failure_analyzer": self.failure_analyzer_provider,
            "summary": self.summary_provider,
        }

        return providers.get(agent_name, self.llm_provider)

    def get_model_name(self, agent_name: str) -> str:
        models = {
            "discovery": self.discovery_model,
            "discovery_structurer": self.discovery_structurer_model,
            "planner": self.planner_model,
            "test_writer": self.test_writer_model,
            "executor": self.executor_model,
            "failure_analyzer": self.failure_analyzer_model,
            "summary": self.summary_model,
        }

        return models.get(agent_name) or self.nvidia_model


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()