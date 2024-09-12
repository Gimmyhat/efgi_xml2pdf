import logging

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.WARNING)

    # Формат сообщений
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Обработчик для файла
    file_handler = logging.FileHandler('app.log')
    # file_handler.setLevel(logging.ERROR)  # Записывать только ошибки в файл
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Обработчик для консоли
    console_handler = logging.StreamHandler()
    # console_handler.setLevel(logging.ERROR)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger