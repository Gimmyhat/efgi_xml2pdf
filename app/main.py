# main.py
import os
import traceback
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from app.xml_to_pdf import convert_xml_to_pdf

app = FastAPI()


def create_temp_dir(project_path):
    temp_dir = os.path.join(project_path, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


@app.get("/", response_class=HTMLResponse)
async def upload_page():
    try:
        with open("app/templates/upload.html") as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        return HTMLResponse(content=f"Ошибка при загрузке страницы: {e}", status_code=500)


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        project_path = os.path.dirname(os.path.abspath(__file__))
        temp_dir = create_temp_dir(project_path)
        xsd_path = os.path.join(project_path, r"schemas\schema.xsd")  # Указываем путь к XSD файлу

        # Сохраняем загруженный файл во временную директорию
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as f:
            f.write(file.file.read())

        # Преобразуем XML в PDF
        pdf_path = convert_xml_to_pdf(file_path, project_path, xsd_path)  # Передаем XSD путь

        # Отправляем PDF файл на клиент
        return StreamingResponse(open(pdf_path, "rb"), media_type="application/pdf",
                                 headers={"Content-Disposition": f"inline; filename={file.filename}.pdf"})
    except Exception as e:
        return HTTPException(status_code=500, detail=f"Ошибка при обработке файла: {e}")
