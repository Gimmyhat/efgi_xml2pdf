# main_app.py
import base64
import logging
import os
import shutil
import tempfile
import traceback
from functools import wraps
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic
from xml_processor import convert_xml_to_pdf
import secrets
from logger import get_logger

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

# Настройка базовой HTTP-аутентификации
security = HTTPBasic()


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

        if file:
            xml_content = await file.read()
        elif request.headers.get("Content-Type") == "application/xml":
            xml_content = await request.body()
        else:
            raise HTTPException(status_code=400, detail="No file or XML data provided")

        try:
            pdf_buffer = await convert_xml_to_pdf(xml_content.decode("utf-8"), project_path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return StreamingResponse(pdf_buffer, media_type="application/pdf",
                                 headers={"Content-Disposition": "inline; filename=document.pdf"})

    except Exception as e:
        logger.error(f"Error processing input: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing input: {str(e)}")

    finally:
        cleanup_temp_files()


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
    return HTMLResponse(content=f"HTTP Error: {exc.detail}", status_code=exc.status_code)


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
