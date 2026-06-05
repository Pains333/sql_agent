from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import backend.state as state
from backend.core.logging_config import get_logger, setup_logging

from backend.routes.setup import router as setup_router
from backend.routes.conversations import router as conversations_router
from backend.routes.databases import router as databases_router
from backend.routes.uploads import router as uploads_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    setup_logging()

    saved = state.load_setup_config()
    if saved:
        logger.info("发现已保存的配置，正在自动初始化...")
        if state.init_agent_from_config(saved):
            logger.info("Agent 初始化成功，跳过配置向导")
        else:
            state.setup_done = True
            logger.info("Agent 初始化失败，但配置已保存，将在访问时延迟重试")
    yield
    if state.agent:
        state.agent.close()


app = FastAPI(title="SQL Agent API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(setup_router)
app.include_router(conversations_router)
app.include_router(databases_router)
app.include_router(uploads_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
