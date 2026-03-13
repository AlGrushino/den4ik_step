# logging.py - ГЛАВНЫЙ ФАЙЛ ЛОГИРОВАНИЯ
import logging
import sys
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

# ✅ Создаем папку logs
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# ✅ Формат логов (время + файл:строка + сообщение)
log_format = logging.Formatter(
    '%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s'
)

# ✅ Консольный handler (DEBUG в development)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(log_format)

# ✅ Файловый handler (INFO + ротация 10MB)
file_handler = RotatingFileHandler(
    log_dir / "app.log", maxBytes=10*1024*1024, backupCount=5
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(log_format)

# ✅ SQLAlchemy handler (DEBUG для SQL запросов)
sql_handler = RotatingFileHandler(
    log_dir / "sql.log", maxBytes=10*1024*1024, backupCount=5
)
sql_handler.setLevel(logging.DEBUG)
sql_handler.setFormatter(log_format)

# ✅ Настраиваем логгеры
# logging.py
_setup_done = False

def setup_logging():
    global _setup_done
    if _setup_done:
        return logging.getLogger("stepapp")
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    
    # ✅ Консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # ✅ Файл
    file_handler = RotatingFileHandler(log_dir / "app.log", maxBytes=10*1024*1024, backupCount=5)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)
    
    # ✅ SQLAlchemy, Uvicorn - без изменений
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_logger.setLevel(logging.ERROR)
    sqlalchemy_logger.propagate = False
    
    logging.getLogger("sqlalchemy.pool").setLevel(logging.ERROR)
    logging.getLogger("sqlalchemy.orm").setLevel(logging.ERROR)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.ERROR)
    
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    _setup_done = True
    print("✅ Logging FIXED!")
    return logging.getLogger("stepapp")  # ✅ Возвращаем app_logger



logger = setup_logging()
