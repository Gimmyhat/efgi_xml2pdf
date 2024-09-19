import base64
import datetime
import os
import shutil
import tempfile
import traceback
import uuid
from functools import wraps

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import HTTPBasic
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from io import BytesIO

from logger import get_logger
from xml_processor import convert_xml_to_pdf
import secrets

# Настройка логирования
logger = get_logger(__name__)

# Инициализация FastAPI
app = FastAPI()

# Получаем абсолютный путь к директории, где находится main_app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Указываем путь к директории с шаблонами
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Указываем каталог для статических файлов
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

# Путь к директории для сохранения файлов (предполагается, что она примонтирована)
STORAGE_DIR = os.getenv("STORAGE_DIR", "/mnt")
STORAGE_PATH = os.path.join(STORAGE_DIR, "input_data")  # Папка для входных данных

# Настройка базовой HTTP-аутентификации
security = HTTPBasic()

# Создаем папку для сохранения файлов, если она не существует
if not os.path.exists(STORAGE_PATH):
    try:
        os.makedirs(STORAGE_PATH)
        logger.info(f"Created storage directory: {STORAGE_PATH}")
    except OSError as e:
        logger.error(f"Error creating storage directory: {e}")
        raise HTTPException(status_code=500, detail="Error creating storage directory")


# Декоратор для аутентификации
def require_auth(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        auth = request.headers.get("Authorization")
        if not auth:
            return Response(
                status_code=401,
                headers={
                    "WWW-Authenticate": 'Basic realm="Restricted Area"',
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache"
                },
                content="Authentication required"
            )
        try:
            scheme, credentials = auth.split()
            if scheme.lower() != 'basic':
                raise HTTPException(status_code=401, detail="Invalid authentication scheme")
            decoded = base64.b64decode(credentials).decode("ascii")
            username, _, password = decoded.partition(":")
            if not secrets.compare_digest(username, USERNAME) or not secrets.compare_digest(password, PASSWORD):
                raise HTTPException(status_code=401, detail="Invalid username or password")
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return Response(
                status_code=401,
                headers={
                    "WWW-Authenticate": 'Basic realm="Restricted Area"',
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache"
                },
                content="Invalid authentication credentials"
            )
        response = await func(request, *args, **kwargs)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    return wrapper


def cleanup_temp_files():
    temp_dir = tempfile.gettempdir()
    for filename in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            logger.error(f'Failed to delete {file_path}. Reason: {e}')


@app.get("/", response_class=HTMLResponse)
@require_auth
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.post("/upload/")
@require_auth
async def upload_file_or_xml(
        request: Request,
        file: UploadFile = File(None),
):
    try:
        project_path = os.path.dirname(os.path.abspath(__file__))

        # Генерируем уникальное имя файла с timestamp
        unique_filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4()}"

        if file:
            file_extension = os.path.splitext(file.filename)[1]
            file_path = os.path.join(STORAGE_PATH, f"{unique_filename}{file_extension}")
            with open(file_path, "wb") as f:
                file_content = await file.read()  # Читаем данные один раз
                f.write(file_content)
            xml_content = file_content  # Используем сохраненные данные
        elif request.headers.get("Content-Type") == "application/xml":
            file_path = os.path.join(STORAGE_PATH, f"{unique_filename}.xml")
            with open(file_path, "wb") as f:
                xml_content = await request.body()
                f.write(xml_content)
        else:
            raise HTTPException(status_code=400, detail="No file or XML data provided")

        logger.info(f"Saved input data to: {file_path}")

        try:
            pdf_buffer = await convert_xml_to_pdf(xml_content.decode("utf-8"), project_path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Ожидание завершения подписания
        pdf_buffer.seek(0)  # Перемещаем указатель в начало буфера
        signed_pdf_content = pdf_buffer.read()  # Читаем данные из буфера

        # Сохранение подписанного PDF
        signed_pdf_path = os.path.join(STORAGE_PATH, f"{unique_filename}_signed.pdf")
        with open(signed_pdf_path, "wb") as f:
            f.write(signed_pdf_content)

        logger.info(f"Saved signed PDF to: {signed_pdf_path}")

        return StreamingResponse(
            BytesIO(signed_pdf_content),  # Используем буфер с подписанными данными
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=document.pdf"}
        )

    except Exception as e:
        logger.error(f"Error processing input: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing input: {str(e)}")

    finally:
        cleanup_temp_files()  # Вызываем cleanup_temp_files только после завершения всех операций


# Middleware для логирования запросов и ответов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request URL: {request.url}, Method: {request.method}")
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        raise
    logger.info(f"Response status code: {response.status_code}")
    return response


# Обработка HTTP исключений
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP Exception: {exc.detail}")
    return HTMLResponse(
        content=f"HTTP Error: {exc.detail}",
        status_code=exc.status_code,
        headers={
            "WWW-Authenticate": 'Basic realm="Restricted Area"',
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache"
        }
    )


# Обработка общих исключений
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {traceback.format_exc()}")
    return HTMLResponse(
        content="An unexpected error occurred",
        status_code=500,
        headers={
            "WWW-Authenticate": 'Basic realm="Restricted Area"',
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache"
        }
    )
