import os
import traceback
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Body
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.xml_to_pdf import convert_xml_to_pdf, create_temp_dir, delete_temp_dir
from xml.etree import ElementTree as ET

app = FastAPI()

# Указываем каталог для статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")

# Фейковые логин и пароль для демонстрации (замените на свои значения)
USERNAME = "admin"
PASSWORD = "admin"

security = HTTPBasic()


# Функция для проверки авторизации
def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != USERNAME or credentials.password != PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/", response_class=HTMLResponse)
async def upload_page(username: str = Depends(authenticate)):
    try:
        with open("app/templates/upload.html") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"Ошибка при загрузке страницы: {e}", status_code=500)


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...), username: str = Depends(authenticate)):
    temp_dir = None
    try:
        project_path = os.path.dirname(os.path.abspath(__file__))
        temp_dir = create_temp_dir(project_path)
        xsd_path = os.path.join(project_path, "schemas/schema.xsd")  # Указываем путь к XSD файлу

        # Сохраняем загруженный файл во временную директорию
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as f:
            f.write(file.file.read())

        # Преобразуем XML в PDF
        pdf_path = convert_xml_to_pdf(file_path, project_path, xsd_path)  # Передаем XSD путь

        # Проверяем, создан ли PDF файл
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Файл PDF не был создан: {pdf_path}")

        # Отправляем PDF файл на клиент
        return StreamingResponse(open(pdf_path, "rb"), media_type="application/pdf",
                                 headers={"Content-Disposition": f"inline; filename={file.filename}.pdf"})
    except Exception as e:
        # Печать полного трейсбэка ошибки для отладки
        print(traceback.format_exc())
        return HTTPException(status_code=500, detail=f"Ошибка при обработке файла: {e}")
    finally:
        # Удаляем временную директорию
        if temp_dir and os.path.exists(temp_dir):
            delete_temp_dir(temp_dir)


# Маршрут для приема XML через POST запрос
@app.post("/api/upload-xml/")
async def upload_xml(xml_body: str = Body(..., media_type="application/xml"), username: str = Depends(authenticate)):
    temp_dir = None
    try:
        # Проверяем, валиден ли XML
        try:
            root = ET.fromstring(xml_body)
        except ET.ParseError:
            raise HTTPException(status_code=400, detail="Invalid XML format")

        project_path = os.path.dirname(os.path.abspath(__file__))
        temp_dir = create_temp_dir(project_path)
        xsd_path = os.path.join(project_path, "schemas/schema.xsd")

        # Сохраняем XML во временную директорию с указанием кодировки UTF-8
        xml_file_path = os.path.join(temp_dir, "temp.xml")
        with open(xml_file_path, "w", encoding="utf-8") as xml_file:
            xml_file.write(xml_body)

        # Преобразуем XML в PDF
        pdf_path = convert_xml_to_pdf(xml_file_path, project_path, xsd_path)

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Файл PDF не был создан: {pdf_path}")

        return StreamingResponse(open(pdf_path, "rb"), media_type="application/pdf",
                                 headers={"Content-Disposition": "inline; filename=document.pdf"})
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке файла: {e}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            delete_temp_dir(temp_dir)


# Новый API маршрут для работы по принципу API
@app.post("/api/upload/")
async def api_upload(file: UploadFile = File(...), username: str = Depends(authenticate)):
    temp_dir = None
    try:
        project_path = os.path.dirname(os.path.abspath(__file__))
        temp_dir = create_temp_dir(project_path)
        xsd_path = os.path.join(project_path, "schemas/schema.xsd")  # Указываем путь к XSD файлу

        # Сохраняем загруженный файл во временную директорию
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as f:
            f.write(file.file.read())

        # Преобразуем XML в PDF
        pdf_path = convert_xml_to_pdf(file_path, project_path, xsd_path)  # Передаем XSD путь

        # Проверяем, создан ли PDF файл
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Файл PDF не был создан: {pdf_path}")

        # Отправляем PDF файл обратно как ответ на API запрос
        return StreamingResponse(open(pdf_path, "rb"), media_type="application/pdf",
                                 headers={"Content-Disposition": f"attachment; filename={file.filename}.pdf"})
    except Exception as e:
        # Печать полного трейсбэка ошибки для отладки
        print(traceback.format_exc())
        return HTTPException(status_code=500, detail=f"Ошибка при обработке файла: {e}")
    finally:
        # Удаляем временную директорию
        if temp_dir and os.path.exists(temp_dir):
            delete_temp_dir(temp_dir)
