import os
import time
import uuid

from fastapi import APIRouter, HTTPException, UploadFile, File

from backend.state import upload_storage
from backend.services.file_parser import parse_file, SUPPORTED_EXTENSIONS
from backend.core import config

router = APIRouter()


@router.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件并解析，支持 xlsx/xls/csv/pkl/parquet/json"""
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，支持: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    try:
        tmp_dir = os.path.join(config.PROJECT_ROOT, ".uploads")
        os.makedirs(tmp_dir, exist_ok=True)

        tmp_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}{ext}")
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        parsed = parse_file(tmp_path, filename)

        os.remove(tmp_path)

        upload_id = uuid.uuid4().hex[:12]
        upload_storage[upload_id] = {
            "filename": filename,
            "columns": parsed["columns"],
            "rows": parsed["rows"],
            "row_count": parsed["row_count"],
            "preview": parsed["preview"],
            "created_at": time.time(),
        }

        return {
            "upload_id": upload_id,
            "filename": filename,
            "columns": parsed["columns"],
            "row_count": parsed["row_count"],
            "preview": parsed["preview"],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {e}")


@router.delete("/api/upload/{upload_id}")
def delete_upload(upload_id: str):
    """删除已上传的文件数据"""
    upload_storage.pop(upload_id, None)
    return {"success": True}
