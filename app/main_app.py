# main_app.py
import os
import traceback
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.xml_to_pdf import convert_xml_to_pdf, create_temp_dir, delete_temp_dir

app = FastAPI()

# Указываем каталог для статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")

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


async def handle_xml(xml_content: str, project_path: str, xsd_path: str):
    temp_dir = create_temp_dir(project_path)

    xml_file_path = os.path.join(temp_dir, "temp.xml")
    with open(xml_file_path, "w", encoding="utf-8") as xml_file:
        xml_file.write(xml_content)

    pdf_path = await convert_xml_to_pdf(xml_file_path, project_path, xsd_path)

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Файл PDF не был создан: {pdf_path}")

    return pdf_path


@app.get("/", response_class=HTMLResponse)
async def upload_page(username: str = Depends(authenticate)):
    try:
        with open("app/templates/upload.html") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"Ошибка при загрузке страницы: {e}", status_code=500)


@app.post("/upload/")
async def upload_file_or_xml(
        request: Request,
        file: UploadFile = File(None),
        username: str = Depends(authenticate)
):
    try:
        project_path = os.path.dirname(os.path.abspath(__file__))
        xsd_path = os.path.join(project_path, "schemas/schema.xsd")
        temp_dir = create_temp_dir(project_path)  # Создаем временный каталог

        # Проверка на загруженный файл
        if file:
            # Создание временного пути для файла
            file_path = os.path.join(create_temp_dir(project_path), file.filename)
            with open(file_path, "wb") as f:
                f.write(await file.read())  # Читаем файл асинхронно

            # Используем await для вызова асинхронной функции
            pdf_path = await convert_xml_to_pdf(file_path, project_path, xsd_path)

        # Проверка на XML в теле запроса
        elif request.headers.get("Content-Type") == "application/xml":
            xml_body = await request.body()
            pdf_path = await handle_xml(xml_body.decode("utf-8"), project_path, xsd_path)  # Используем await

        else:
            raise HTTPException(status_code=400, detail="No file or XML data provided")

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file was not created: {pdf_path}")

        # Возвращаем PDF файл в ответе
        return StreamingResponse(open(pdf_path, "rb"), media_type="application/pdf",
                                 headers={"Content-Disposition": "inline; filename=document.pdf"})

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing input: {e}")
