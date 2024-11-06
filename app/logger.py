# logger.py
import logging
import os
import datetime

from config import LOG_FILE_PATH


# Формат сообщений с московским временем
class MoscowFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.datetime.fromtimestamp(record.created)
        dt = dt + datetime.timedelta(hours=3)  # Добавляем 3 часа для московского времени
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            try:
                s = dt.isoformat(timespec='milliseconds')
            except TypeError:
                s = dt.isoformat()
        return s


formatter = MoscowFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Если лог-файл не существует, создаем его
log_dir = os.path.dirname(LOG_FILE_PATH)
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

if not os.path.exists(LOG_FILE_PATH):
    with open(LOG_FILE_PATH, "w") as f:
        pass  # Просто создаем пустой файл

# Обработчик для файла
file_handler = logging.FileHandler(LOG_FILE_PATH)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Обработчик для консоли
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)


def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Устанавливаем уровень логирования для логгера

    # Добавляем обработчики к логгеру, если их еще нет
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
