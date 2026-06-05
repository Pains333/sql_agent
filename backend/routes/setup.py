import os

import requests
from fastapi import APIRouter, HTTPException

from backend.models import SetupRequest
from backend.state import (
    agent, setup_done, load_setup_config, init_agent_from_config,
    save_setup_config, SETUP_CONFIG_PATH,
)
from backend.services.skill_manager import DEFAULT_SKILL_CONTENT
from backend.core import config

router = APIRouter()


@router.get("/api/setup/status")
def get_setup_status():
    """检查是否已完成配置"""
    import backend.state as st
    if not st.setup_done:
        saved = load_setup_config()
        if saved:
            st.setup_done = True
            init_agent_from_config(saved)
    return {"setup_done": st.setup_done}


@router.post("/api/setup/reset")
def reset_setup():
    """重置配置，关闭 Agent，删除配置文件，清除 skill.md"""
    import backend.state as st
    if st.agent:
        try:
            st.agent.close()
        except Exception:
            pass
        st.agent = None
    st.setup_done = False
    if os.path.exists(SETUP_CONFIG_PATH):
        os.remove(SETUP_CONFIG_PATH)
    with open(config.SKILL_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(DEFAULT_SKILL_CONTENT)
    return {"success": True}


@router.get("/api/ollama/models")
def get_ollama_models():
    """查询 Ollama 本地模型列表"""
    try:
        resp = requests.get(
            f"{config.OLLAMA_BASE_URL}/api/tags",
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        models = [
            {
                "name": m.get("name", ""),
                "size": m.get("size", 0),
                "modified_at": m.get("modified_at", ""),
            }
            for m in data.get("models", [])
        ]
        return {"models": models}
    except requests.exceptions.ConnectionError:
        return {"models": [], "error": "Ollama 未运行"}
    except Exception as e:
        return {"models": [], "error": str(e)}


@router.post("/api/setup")
def submit_setup(req: SetupRequest):
    """提交配置，初始化 Agent，扫描数据库结构"""
    import backend.state as st

    if not req.db_user.strip():
        raise HTTPException(status_code=400, detail="数据库用户名不能为空")
    if not req.db_password.strip():
        raise HTTPException(status_code=400, detail="数据库密码不能为空")
    if req.model_type == "api":
        if not req.api_base_url.strip():
            raise HTTPException(status_code=400, detail="API 地址不能为空")
        if not req.api_key.strip():
            raise HTTPException(status_code=400, detail="API Key 不能为空")
        if not req.api_model.strip():
            raise HTTPException(status_code=400, detail="API 模型名称不能为空")

    cfg = req.model_dump()

    try:
        if not init_agent_from_config(cfg):
            raise RuntimeError("数据库连接失败")

        scan_result = st.agent.scan_all_databases()
        save_setup_config(cfg)

        return {
            "success": True,
            "message": scan_result,
            "current_db": st.agent.get_current_db(),
            "skill_summary": st.agent.skill.get_summary(),
        }

    except Exception as e:
        if st.agent:
            try:
                st.agent.close()
            except Exception:
                pass
            st.agent = None
        st.setup_done = False
        raise HTTPException(status_code=400, detail="配置初始化失败，请检查数据库连接信息和模型配置")
