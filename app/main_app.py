import base64
import datetime
import json
import os
import re
import shutil
import tempfile
import traceback
from functools import wraps
from io import BytesIO

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Response, Query
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.security import HTTPBasic
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import STORAGE_PATH, OUTPUT_PATH, FILE_ERRORS_PATH, LOG_FILE_PATH
from logger import get_logger
from xml_processor import convert_xml_to_pdf, find_values_in_xml
import secrets
import xml.etree.ElementTree as ET

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

# Загрузка ошибок из файла при запуске приложения
try:
    with open(FILE_ERRORS_PATH, "r") as f:
        file_errors = json.load(f)
except FileNotFoundError:
    file_errors = {}

# Настройка базовой HTTP-аутентификации
security = HTTPBasic()

# Создаем папки для сохранения файлов, если они не существуют
for path in [STORAGE_PATH, OUTPUT_PATH]:
    if not os.path.exists(path):
        try:
            os.makedirs(path)
            logger.info(f"Created storage directory: {path}")
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

        unique_filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Определяем расширение файла
        file_extension = '.xml'  # Расширение по умолчанию
        if file:
            file_extension = os.path.splitext(file.filename)[1]

        if file:
            file_path = os.path.join(STORAGE_PATH, f"{unique_filename}{file_extension}")
            with open(file_path, "wb") as f:
                file_content = await file.read()
                f.write(file_content)
            xml_content = file_content
        elif request.headers.get("Content-Type") == "application/xml":
            file_path = os.path.join(STORAGE_PATH,
                                     f"{unique_filename}{file_extension}")
            with open(file_path, "wb") as f:
                xml_content = await request.body()
                f.write(xml_content)
        else:
            raise HTTPException(status_code=400, detail="No file or XML data provided")

        # Извлекаем UniqueID из XML
        unique_id = find_values_in_xml(ET.fromstring(xml_content), 'UniqueID')
        if not unique_id:
            handle_error(os.path.basename(file_path), "UniqueID not found in XML")
            raise HTTPException(status_code=400, detail="UniqueID not found in XML")

        # Переименовываем файл, добавляя UniqueID
        new_file_path = os.path.join(STORAGE_PATH, f"{unique_filename}_{unique_id}{file_extension}")
        os.rename(file_path, new_file_path)
        logger.info(f"Saved input data to: {new_file_path}")

        try:
            pdf_buffer = await convert_xml_to_pdf(xml_content.decode("utf-8"), project_path)
        except ValueError as e:
            handle_error(new_file_path, str(e))
            raise HTTPException(status_code=400, detail=str(e))

        # Сохраняем подписанный PDF
        pdf_filename = f"{unique_filename}_{unique_id}_signed.pdf"
        pdf_filepath = os.path.join(OUTPUT_PATH, pdf_filename)
        with open(pdf_filepath, "wb") as f:
            f.write(pdf_buffer.read())

        # Возвращаем подписанный PDF для отображения в браузере
        pdf_buffer.seek(0)
        return StreamingResponse(
            BytesIO(pdf_buffer.getvalue()),
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={pdf_filename}"}
        )

    except Exception as e:
        logger.error(f"Error processing input: {traceback.format_exc()}")
        if 'new_file_path' in locals():
            handle_error(new_file_path, str(e))
        else:
            handle_error(file.filename, str(e))
        raise HTTPException(status_code=500, detail=f"Error processing input: {str(e)}")

    finally:
        cleanup_temp_files()


# Маршрут для просмотра файлов в /mnt/input_data
@app.get("/files/", response_class=HTMLResponse)
@require_auth
async def list_files(request: Request,
                     page: int = Query(1, ge=1),
                     per_page: int = Query(20, ge=1),
                     search: str = Query(None)):
    files = []
    for filename in os.listdir(STORAGE_PATH):
        filepath = os.path.join(STORAGE_PATH, filename)
        if os.path.isfile(filepath):
            creation_time = datetime.datetime.fromtimestamp(os.path.getctime(filepath))
            error_message = file_errors.get(filename)  # Получаем сообщение об ошибке, если есть

            # Извлекаем UniqueID из имени файла с помощью регулярного выражения
            match = re.search(r'_(.+?)\.xml$', filename)
            unique_id = match.group(1) if match else None

            # Проверяем, совпадает ли search с UniqueID, если он найден
            if search and unique_id and search.lower() != unique_id.lower():
                continue  # Пропускаем файл, если search не совпадает

            # Формируем имя PDF файла и URL для просмотра в браузере
            unique_filename = filename.split('.')[0]  # Получаем имя без расширения
            pdf_filename = f"{unique_filename}_signed.pdf"
            pdf_url = f"/output/{pdf_filename}?view=inline"  # URL для просмотра PDF

            files.append({
                "name": filename,
                "creation_time": creation_time.strftime("%Y-%m-%d %H:%M:%S"),
                "url": f"/files/{filename}",
                "error": error_message,
                "pdf_url": pdf_url,
                "pdf_filename": pdf_filename
            })

    # Сортируем файлы по дате создания в обратном порядке (сначала новые)
    files.sort(key=lambda x: x["creation_time"], reverse=True)

    total_files = len(files)
    total_pages = (total_files + per_page - 1) // per_page

    start_index = (page - 1) * per_page
    end_index = min(start_index + per_page, total_files)
    current_files = files[start_index:end_index]

    return templates.TemplateResponse("files.html", {
        "request": request,
        "files": current_files,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "total_files": total_files
    })


# Функция для обработки ошибок
def handle_error(filename, error_message):
    file_errors[filename] = error_message
    logger.error(f"Error processing file {filename}: {error_message}")

    # Сохранение ошибок в файл
    with open(FILE_ERRORS_PATH, "w") as f:
        json.dump(file_errors, f)


@app.get("/error/{filename}", response_class=HTMLResponse)
@require_auth
async def view_error(request: Request, filename: str):
    error_message = file_errors.get(filename)
    if error_message:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "filename": filename,
            "error_message": error_message
        })
    else:
        raise HTTPException(status_code=404, detail="Error not found")


# Маршрут для скачивания/просмотра PDF файла
@app.get("/output/{pdf_filename}")
@require_auth
async def download_pdf(request: Request, pdf_filename: str, view: str = "download"):  # Добавляем параметр view
    pdf_filepath = os.path.join(OUTPUT_PATH, pdf_filename)
    if os.path.isfile(pdf_filepath):
        if view == "inline":
            return FileResponse(pdf_filepath, media_type="application/pdf", filename=pdf_filename,
                                headers={"Content-Disposition": f"inline; filename={pdf_filename}"})
        else:
            return FileResponse(pdf_filepath, media_type="application/pdf", filename=pdf_filename)
    else:
        raise HTTPException(status_code=404, detail="PDF file not found")


# Маршрут для просмотра конкретного файла
@app.get("/files/{filename}")
@require_auth
async def view_file(request: Request, filename: str):
    filepath = os.path.join(STORAGE_PATH, filename)
    if os.path.isfile(filepath):
        return FileResponse(filepath)
    else:
        raise HTTPException(status_code=404, detail="File not found")


@app.get("/logs/", response_class=HTMLResponse)
@require_auth
async def view_logs(request: Request):
    """Отображает содержимое лог-файла."""
    try:
        # Если лог-файл не существует, создаем его
        if not os.path.exists(LOG_FILE_PATH):
            with open(LOG_FILE_PATH, "w") as f:
                pass  # Просто создаем пустой файл

        with open(LOG_FILE_PATH, "r") as f:
            log_content = f.read()
        return templates.TemplateResponse("logs.html", {"request": request, "log_content": log_content})
    except Exception as e:
        logger.error(f"Error reading log file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error reading log file")


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
