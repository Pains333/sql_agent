from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict

import backend.state as state

router = APIRouter(prefix="/api/dictionary", tags=["dictionary"])

class DictionaryEntryCreate(BaseModel):
    term: str
    definition: str
    sql_hint: Optional[str] = ""
    field_mappings: Optional[Dict[str, str]] = {}

class DictionaryEntryUpdate(BaseModel):
    term: Optional[str] = None
    definition: Optional[str] = None
    sql_hint: Optional[str] = None
    field_mappings: Optional[Dict[str, str]] = None

@router.get("")
async def list_dictionary():
    if not state.agent:
        raise HTTPException(status_code=400, detail="Agent 未初始化")
    return {"entries": state.agent.dictionary.list_entries()}

@router.post("")
async def add_dictionary_entry(req: DictionaryEntryCreate):
    if not state.agent:
        raise HTTPException(status_code=400, detail="Agent 未初始化")
    try:
        entry = state.agent.dictionary.add_entry(
            term=req.term,
            definition=req.definition,
            sql_hint=req.sql_hint,
            field_mappings=req.field_mappings
        )
        return {"success": True, "entry": entry}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{entry_id}")
async def update_dictionary_entry(entry_id: str, req: DictionaryEntryUpdate):
    if not state.agent:
        raise HTTPException(status_code=400, detail="Agent 未初始化")
    try:
        kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
        entry = state.agent.dictionary.update_entry(entry_id, **kwargs)
        return {"success": True, "entry": entry}
    except ValueError:
        raise HTTPException(status_code=404, detail="条目不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{entry_id}")
async def delete_dictionary_entry(entry_id: str):
    if not state.agent:
        raise HTTPException(status_code=400, detail="Agent 未初始化")
    success = state.agent.dictionary.delete_entry(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="条目不存在")
    return {"success": True}
