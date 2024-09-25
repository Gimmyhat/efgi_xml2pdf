# logger.py
import logging

from config import LOG_FILE_PATH

# Создаем логгер
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Формат сообщений
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Обработчик для файла
file_handler = logging.FileHandler(LOG_FILE_PATH)
# file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Обработчик для консоли
console_handler = logging.StreamHandler()
# console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# Добавляем обработчики к логгеру, если их еще нет
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


def get_logger(name):
    return logging.getLogger(name)
