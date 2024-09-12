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