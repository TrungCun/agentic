"""Logging setup đơn giản, dùng lại được cho project khác.

Cách dùng
---------
    from app.config.log import setup_logging, get_logger

    setup_logging()                    # gọi 1 lần ở entrypoint (main.py)
    logger = get_logger(__name__)
    logger.info("hello")

Cấu hình qua tham số hàm (hoặc biến môi trường khi không truyền tham số):
    setup_logging(
        service_name="myapp",          # dùng trong JSON log (default: "app")
        level="DEBUG",                 # INFO|DEBUG|WARNING|ERROR|CRITICAL (default: INFO, fallback: LOG_LEVEL env)
        json_format=True,              # True: JSON log | False: text log (default: False, fallback: LOG_FORMAT env)
        file_enabled=True,             # True: ghi file | False: stdout only (default: False, fallback: LOG_FILE_ENABLED env)
        log_dir="logs",                # thư mục chứa file (default: storage/log)
    )

Biến môi trường (tùy chọn, dùng khi không truyền tham số):
    LOG_LEVEL          INFO|DEBUG|WARNING|ERROR|CRITICAL
    LOG_FORMAT         text|json
    LOG_FILE_ENABLED   true|false
"""

import json
import logging
import logging.handlers
import os
import sys
from typing import Any, Dict, Optional

__all__ = ["setup_logging", "get_logger"]

_CONFIGURED_ATTR = "_app_log_configured"
_OWNED_HANDLER_ATTR = "_app_log_owned"


def _env_bool(raw: Optional[str], default: bool) -> bool:
    if raw is None or raw == "":
        return default
    normalized = raw.strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False
    return default


class ColoredFormatter(logging.Formatter):
    """Formatter có màu ANSI — chỉ dùng cho console."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        msg = super().format(record)

        level_part = f"{color}{self.BOLD}[{record.levelname}]{self.RESET}"
        rest = msg.split("]", 2)[2] if "]" in msg else msg

        return f"{level_part}{rest}"


class JSONFormatter(logging.Formatter):
    """Formatter JSON structured — 1 object / dòng."""

    def __init__(self, service_name: str = "app"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "service": self.service_name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(
    *,
    service_name: str = "app",
    level: Optional[str] = None,
    json_format: Optional[bool] = None,
    file_enabled: Optional[bool] = None,
    log_dir: str = "storage/log",
) -> logging.Logger:
    """Cấu hình root logger. Idempotent — gọi lại nhiều lần không tạo handler trùng."""

    root = logging.getLogger()

    if getattr(root, _CONFIGURED_ATTR, False):
        return root

    # Đọc từ tham số hoặc fallback env
    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO").upper()
    else:
        level = level.upper()

    if json_format is None:
        json_format = _env_bool(os.environ.get("LOG_FORMAT"), False)

    if file_enabled is None:
        file_enabled = _env_bool(os.environ.get("LOG_FILE_ENABLED"), True)

    root.setLevel(level)

    # Fix console encoding trên Windows (cmd.exe/PowerShell codepage cũ)
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

    # Console handler
    console_handler: logging.Handler = logging.StreamHandler(sys.stdout)
    fmt_str = "[%(levelname)s] [%(asctime)s] [%(name)s] -> %(message)s"

    if json_format:
        console_handler.setFormatter(JSONFormatter(service_name))
    else:
        console_formatter = ColoredFormatter(fmt_str, datefmt="%Y-%m-%d %H:%M:%S")
        console_handler.setFormatter(console_formatter)

    setattr(console_handler, _OWNED_HANDLER_ATTR, True)
    root.addHandler(console_handler)

    # File handler (nếu bật)
    if file_enabled:
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"{service_name}.log")

        file_handler: logging.Handler = logging.handlers.TimedRotatingFileHandler(
            log_path, when="midnight", interval=1, backupCount=30, encoding="utf-8"
        )

        if json_format:
            file_handler.setFormatter(JSONFormatter(service_name))
        else:
            file_handler.setFormatter(
                logging.Formatter(fmt_str, datefmt="%Y-%m-%d %H:%M:%S")
            )

        setattr(file_handler, _OWNED_HANDLER_ATTR, True)
        root.addHandler(file_handler)

    # Giảm noise từ thư viện bên thứ 3
    for logger_name in ("httpx", "httpcore", "urllib3", "uvicorn.access", "werkzeug"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    setattr(root, _CONFIGURED_ATTR, True)
    return root


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Wrapper đơn giản cho logging.getLogger()."""
    return logging.getLogger(name)
