from pydantic import BaseModel
from typing import Optional


class SetupRequest(BaseModel):
    language: str = "zh"
    model_type: str = "local"
    model_name: str = ""
    api_base_url: str = ""
    api_key: str = ""
    api_model: str = ""
    db_type: str = "postgresql"
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = ""
    db_password: str = ""


class MessageRequest(BaseModel):
    content: str
    upload_id: Optional[str] = None
    language: str = "zh"


class ConversationCreate(BaseModel):
    title: Optional[str] = "新对话"


class TitleUpdate(BaseModel):
    title: str


class SwitchDatabaseRequest(BaseModel):
    database: str


class ExecuteRequest(BaseModel):
    sql: str
    action: str
    message_id: str
    target_db: Optional[str] = None
    upload_id: Optional[str] = None
    target_table: Optional[str] = None


class PaginateRequest(BaseModel):
    sql: str
    page: int = 1
    page_size: int = 50


class ExplainRequest(BaseModel):
    sql: str
    database: Optional[str] = None
