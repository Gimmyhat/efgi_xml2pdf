import os
from dotenv import load_dotenv

load_dotenv()

TEST_MODE = os.getenv('TEST_MODE', 'True').lower() == 'true'
SIGNER_NAME = os.getenv('SIGNER_NAME', "ТЕСТ")
SIGNER_PASSWORD = os.getenv('SIGNER_PASSWORD', "12345")
PFX_PATH = "app/certs/generatedDigital.pfx" # Путь к файлу сертификата