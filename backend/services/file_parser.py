"""
文件解析器 - 支持 Excel, CSV, PKL, Parquet, JSON
统一使用 pandas 解析，输出标准化结果
"""

import os

import numpy as np
import pandas as pd

from backend.core.exceptions import FileParseError
from backend.core.logging_config import get_logger

logger = get_logger(__name__)

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".parquet", ".json"}

# 文件魔数校验（防止伪造扩展名）
_MAGIC_BYTES = {
    ".xlsx": [b'PK\x03\x04'],          # ZIP (Office Open XML)
    ".xls":  [b'\xd0\xcf\x11\xe0'],    # OLE2 Compound
    ".parquet": [b'PAR1'],
    ".json": None,                       # JSON 无固定魔数，跳过
    ".csv":  None,                       # CSV 纯文本，跳过
}


def _validate_magic_bytes(file_path: str, ext: str) -> bool:
    """校验文件头魔数是否与扩展名匹配"""
    expected = _MAGIC_BYTES.get(ext)
    if expected is None:
        return True  # 纯文本格式跳过校验
    with open(file_path, "rb") as f:
        header = f.read(8)
    return any(header.startswith(magic) for magic in expected)

# 上传文件大小限制 (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


def parse_file(file_path: str, original_filename: str) -> dict:
    """
    解析上传的文件，返回标准化数据

    Args:
        file_path: 临时文件路径
        original_filename: 原始文件名（用于判断格式）

    Returns:
        {
            "columns": ["col1", "col2", ...],
            "rows": [[val1, val2, ...], ...],
            "row_count": int,
            "preview": [{"col1": val1, "col2": val2}, ...],  # 前5行预览
        }

    Raises:
        FileParseError: 文件格式不支持、大小超限、内容为空或解析失败
    """
    ext = os.path.splitext(original_filename)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise FileParseError(f"不支持的文件格式: {ext}，支持: {', '.join(SUPPORTED_EXTENSIONS)}")

    # 检查文件大小
    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE:
        raise FileParseError(f"文件大小 ({file_size // 1024 // 1024}MB) 超过限制 ({MAX_FILE_SIZE // 1024 // 1024}MB)")

    # 校验文件魔数
    if not _validate_magic_bytes(file_path, ext):
        raise FileParseError(f"文件内容与扩展名 {ext} 不匹配，可能是伪造文件")

    try:
        df = _read_file(file_path, ext)
    except Exception as e:
        raise FileParseError(f"文件解析失败: {e}") from e

    if df.empty:
        raise FileParseError("文件内容为空")

    # 清理列名：去除前后空格
    df.columns = [str(col).strip() for col in df.columns]

    # 将 NaN 转换为 None
    df = df.where(pd.notnull(df), None)

    columns = list(df.columns)
    rows = df.values.tolist()

    # 处理行数据中的特殊类型（如 numpy 类型转 Python 原生类型）
    rows = _normalize_rows(rows)

    # 前 5 行预览
    preview_rows = rows[:5]
    preview = [dict(zip(columns, row)) for row in preview_rows]

    logger.info("文件解析完成: %s, %d 列, %d 行", original_filename, len(columns), len(rows))

    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "preview": preview,
    }


def _read_file(file_path: str, ext: str) -> pd.DataFrame:
    """根据扩展名选择对应的 pandas 读取方法"""
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path, engine="openpyxl")
    elif ext == ".csv":
        # 尝试多种编码（中文 CSV 常见 GBK / GB2312）
        for encoding in ("utf-8-sig", "utf-8", "gbk", "gb2312", "gb18030", "latin-1"):
            try:
                return pd.read_csv(file_path, encoding=encoding, on_bad_lines="skip")
            except (UnicodeDecodeError, UnicodeError):
                continue
        # 最后兜底用 latin-1（永远不会 decode 失败）
        return pd.read_csv(file_path, encoding="latin-1", on_bad_lines="skip")
    elif ext == ".parquet":
        return pd.read_parquet(file_path)
    elif ext == ".json":
        return pd.read_json(file_path)
    else:
        raise FileParseError(f"不支持的文件格式: {ext}")


def _normalize_rows(rows: list) -> list:
    """将 numpy / pandas 特殊类型转换为 Python 原生类型"""
    import math

    result = []
    for row in rows:
        normalized = []
        for val in row:
            if val is None:
                normalized.append(None)
            elif isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                normalized.append(None)
            elif isinstance(val, (np.integer,)):
                normalized.append(int(val))
            elif isinstance(val, (np.floating,)):
                if np.isnan(val) or np.isinf(val):
                    normalized.append(None)
                else:
                    normalized.append(float(val))
            elif isinstance(val, (np.bool_,)):
                normalized.append(bool(val))
            elif isinstance(val, (pd.Timestamp, np.datetime64)):
                normalized.append(str(val))
            elif isinstance(val, bytes):
                normalized.append(val.decode("utf-8", errors="replace"))
            else:
                normalized.append(val)
        result.append(normalized)
    return result

