# test_main_app.py
import base64
import os
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from main_app import app
from xml_processor import convert_xml_to_pdf

# Настройка тестового клиента
client = TestClient(app)

# Путь к тестовым XML-файлам
TEST_XML_DIR = os.path.join(os.path.dirname(__file__), "test_xml")

# Тестовые данные для аутентификации
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

# Функция для получения базовой аутентификации
def get_auth_header():
    return {"Authorization": "Basic " + base64.b64encode(f"{USERNAME}:{PASSWORD}".encode()).decode()}


# Тесты для /upload/ endpoint
@pytest.mark.parametrize("xml_filename", [
    "valid_xml.xml",
    "valid_xml_with_deposit.xml",
    "valid_xml_with_10_deposits.xml",
])
def test_upload_valid_xml(xml_filename):
    with open(os.path.join(TEST_XML_DIR, xml_filename), "rb") as xml_file:
        response = client.post("/upload/", files={"file": xml_file}, headers=get_auth_header())

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def test_upload_invalid_xml():
    with open(os.path.join(TEST_XML_DIR, "invalid_xml.xml"), "rb") as xml_file:
        response = client.post("/upload/", files={"file": xml_file}, headers=get_auth_header())

    assert response.status_code == 400
    assert "Invalid XML format" in response.text


def test_upload_no_file_or_xml():
    response = client.post("/upload/", headers=get_auth_header())

    assert response.status_code == 400
    assert "No file or XML data provided" in response.text


# Тесты для функции convert_xml_to_pdf
@pytest.mark.asyncio
@pytest.mark.parametrize("xml_filename", [
    "valid_xml.xml",
    "valid_xml_with_deposit.xml",
    "valid_xml_with_10_deposits.xml",
])
async def test_convert_xml_to_pdf_valid_xml(xml_filename):
    project_path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(TEST_XML_DIR, xml_filename), "r") as xml_file:
        xml_content = xml_file.read()

    pdf_buffer = await convert_xml_to_pdf(xml_content, project_path)
    assert pdf_buffer is not None
    assert isinstance(pdf_buffer, BytesIO)
    assert pdf_buffer.getvalue()


@pytest.mark.asyncio
async def test_convert_xml_to_pdf_invalid_xml():
    project_path = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(TEST_XML_DIR, "invalid_xml.xml"), "r") as xml_file:
        xml_content = xml_file.read()

    with pytest.raises(ValueError) as excinfo:
        await convert_xml_to_pdf(xml_content, project_path)

    assert "Invalid XML format" in str(excinfo.value)

# Тесты для аутентификации
def test_upload_without_auth():
    response = client.post("/upload/")
    assert response.status_code == 401
    assert "Authentication required" in response.text


def test_upload_with_invalid_auth():
    response = client.post("/upload/", headers={"Authorization": "Basic invalid"})
    assert response.status_code == 401
    assert "Invalid authentication credentials" in response.text