"""
Structured Logging Configuration: JSON formatting for production, rich for development.

Usage:
    from app.utils.structured_logging import configure_logging
    configure_logging()  # Call once at startup
"""
import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict
from app.utils.config import settings


class JSONFormatter(logging.Formatter):
    """JSON log formatter for production - machine-parseable logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
            
        return json.dumps(log_entry)


class ColoredFormatter(logging.Formatter):
    """Colored log formatter for development - human-readable logs."""
    
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Truncate long messages
        msg = record.getMessage()
        if len(msg) > 500:
            msg = msg[:497] + "..."
        
        return f"{color}[{timestamp}] {record.levelname:8} {record.name:30} | {msg}{self.RESET}"


def configure_logging():
    """Configure structured logging based on environment."""
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if settings.ENVIRONMENT == "production":
        # Production: JSON formatted logs
        console_handler.setFormatter(JSONFormatter())
    else:
        # Development: Colored, human-readable logs
        console_handler.setFormatter(ColoredFormatter())
    
    root_logger.addHandler(console_handler)
    
    # Reduce noise from noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("pinecone").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    
    # Log startup message
    root_logger.info(
        f"Logging configured: env={settings.ENVIRONMENT}, level={settings.LOG_LEVEL}"
    )


class ContextLogger:
    """Logger that automatically includes context (user_id, request_id)."""
    
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}
    
    def bind(self, **context) -> "ContextLogger":
        """Bind context to logger."""
        new_logger = ContextLogger(self._logger.name)
        new_logger._context = {**self._context, **context}
        return new_logger
    
    def _log(self, level: int, msg: str, *args, **kwargs):
        """Log with context."""
        extra = kwargs.pop("extra", {})
        extra.update(self._context)
        self._logger.log(level, msg, *args, extra=extra, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        self._log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        self._log(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        self._log(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        self._log(logging.ERROR, msg, *args, **kwargs)


def get_logger(name: str) -> ContextLogger:
    """Get a context-aware logger."""
    return ContextLogger(name)
