from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Oracle DB
    db_user: str
    db_password: str
    db_host: str
    db_port: int = 1521
    db_service_name: str
    oracle_client_lib_dir: str = "/opt/oracle/instantclient_21_13"

    # Buk API
    buk_api_url: str = "https://linkeschile.buk.cl"
    buk_api_token: str = ""

    # SMTP (email)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    @property
    def db_dsn(self) -> str:
        return f"{self.db_host}:{self.db_port}/{self.db_service_name}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
