# main_app.py
import os
import traceback
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.xml_processor import convert_xml_to_pdf

app = FastAPI()

# Указываем каталог для статических файлов
app.mount("/static", StaticFiles(directory="static"), name="static")

USERNAME = "admin"
PASSWORD = "admin"
security = HTTPBasic()

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
async def upload_file_or_xml(
        request: Request,
        file: UploadFile = File(None),
        username: str = Depends(authenticate)
):
    try:
        project_path = os.path.dirname(os.path.abspath(__file__))
        xsd_path = os.path.join(project_path, "schemas/schema.xsd")

        if file:
            xml_content = await file.read()
        elif request.headers.get("Content-Type") == "application/xml":
            xml_content = await request.body()
        else:
            raise HTTPException(status_code=400, detail="No file or XML data provided")

        pdf_buffer = await convert_xml_to_pdf(xml_content.decode("utf-8"), project_path)

        return StreamingResponse(pdf_buffer, media_type="application/pdf",
                                 headers={"Content-Disposition": "inline; filename=document.pdf"})

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing input: {e}")