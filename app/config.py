# config.py
import os
from dotenv import load_dotenv

load_dotenv()

TEST_MODE = os.getenv('TEST_MODE', 'True').lower() == 'true'

if TEST_MODE:
    SIGNER_NAME = "ТЕСТ"
    SIGNER_PASSWORD = "12345"
else:
    SIGNER_NAME = os.getenv('SIGNER_NAME')
    SIGNER_PASSWORD = os.getenv('SIGNER_PASSWORD')

PFX_FILE = "generatedDigital.pfx"

# Путь к директории для сохранения файлов (предполагается, что она примонтирована)
STORAGE_DIR = os.getenv("STORAGE_DIR", "/mnt")
STORAGE_PATH = os.path.join(STORAGE_DIR, "input_data")  # Папка для входных данных
OUTPUT_PATH = os.path.join(STORAGE_DIR, "output_data")  # Папка для выходных PDF файлов
FILE_ERRORS_PATH = os.path.join(STORAGE_DIR, "file_errors.json")  # Путь к файлу для хранения ошибок
LOG_FILE_PATH = os.path.join(STORAGE_DIR, "app.log")  # Путь к лог-файлу