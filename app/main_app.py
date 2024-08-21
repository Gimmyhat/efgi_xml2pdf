import os
import traceback
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.xml_to_pdf import convert_xml_to_pdf, create_temp_dir, delete_temp_dir

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
