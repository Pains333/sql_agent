"""
SQL Agent 日志配置
提供统一的日志初始化，替代散布在各模块中的 print() 语句
"""

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """
    初始化全局日志配置

    Args:
        level: 日志级别，支持 DEBUG / INFO / WARNING / ERROR
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 根 logger 配置
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 避免重复添加 handler
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # 降低第三方库的日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的 logger

    Args:
        name: logger 名称，通常使用模块名（如 __name__）

    Returns:
        配置好的 Logger 实例
    """
    return logging.getLogger(name)
