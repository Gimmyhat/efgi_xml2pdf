import logging
import os
import datetime

from config import LOG_FILE_PATH

# Создаем логгер
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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

# Добавляем обработчики к корневому логгеру
root_logger = logging.getLogger()  # Получаем корневой логгер
if not root_logger.handlers:
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

def get_logger(name):
    return logging.getLogger(name)