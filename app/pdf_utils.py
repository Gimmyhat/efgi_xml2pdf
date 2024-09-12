# pdf_utils.py
import asyncio
import logging
import os
from io import BytesIO
from datetime import datetime
from pyhanko.sign import signers, PdfSignatureMetadata
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign.signers.pdf_signer import PdfSigner
from pdfrw import PdfReader, PdfWriter, PageMerge
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import letter
import tempfile

from logger import get_logger

# Настройка логирования
logger = get_logger(__name__)


async def sign_pdf(input_pdf, output_pdf, pfx_path, cert_name, password, test=False):
    if not test:
        try:
            # Сохраняем BytesIO в файл
            with tempfile.NamedTemporaryFile(delete=False) as temp_input_file, \
                    tempfile.NamedTemporaryFile(delete=False) as temp_output_file:

                temp_input_file.write(input_pdf.read())  # Записываем BytesIO в файл
                temp_input_file.flush()

                # Формируем команду для csptest
                command = [
                    "csptest", "-sfsign", "-sign",
                    "-in", temp_input_file.name,
                    "-out", temp_output_file.name,
                    "-my", cert_name,
                    "-add"
                ]

                # Запускаем процесс с передачей пароля через stdin
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                # Отправляем пароль и завершаем ввод
                password_bytes = (password + '\n').encode('utf-8')
                stdout, stderr = await process.communicate(input=password_bytes)

                if process.returncode == 0:
                    logging.info(f"PDF успешно подписан и сохранен как {temp_output_file.name}")

                    # Читаем подписанный файл и возвращаем как BytesIO
                    with open(temp_output_file.name, 'rb') as signed_pdf:
                        output_pdf.write(signed_pdf.read())
                    output_pdf.seek(0)

                else:
                    logger.error(f"Ошибка при подписании PDF. Код возврата: {process.returncode}")
                    logger.error(f"Ошибка: {stderr.decode('utf-8')}")
                    raise Exception(f"Не удалось подписать PDF. Ошибка: {stderr.decode('utf-8')}")

        except Exception as e:
            logger.error(f"Ошибка при подписании PDF: {str(e)}")
            raise
    else:
        try:
            signer = signers.SimpleSigner.load_pkcs12(
                pfx_file=pfx_path,
                passphrase=password.encode() if password else None
            )

            w = IncrementalPdfFileWriter(input_pdf)
            signature_meta = PdfSignatureMetadata(field_name="Signature1")
            pdf_signer = PdfSigner(signature_meta=signature_meta, signer=signer)

            await pdf_signer.async_sign_pdf(w, output=output_pdf, existing_fields_only=False)

        except Exception as e:
            logger.error(f"Error signing PDF: {e}")
            raise

def register_fonts():
    try:
        roboto_regular = os.path.join('static', 'fonts', 'Roboto-Regular.ttf')
        roboto_bold = os.path.join('static', 'fonts', 'Roboto-Bold.ttf')
        pdfmetrics.registerFont(TTFont('Roboto-Regular', roboto_regular))
        pdfmetrics.registerFont(TTFont('Roboto-Bold', roboto_bold))
    except Exception as e:
        logger.error(f"Error registering fonts: {e}")
        logger.error(f"Attempted paths: \nRegular: {roboto_regular}\nBold: {roboto_bold}")
        raise

def create_stamp_pdf(signer_name, page_width, font_regular='Roboto-Regular', font_bold='Roboto-Bold'):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)

    text1 = "Документ подписан электронной подписью"
    text2 = f"Подписант: {signer_name}"
    text3 = f"Дата и время (UTC): {datetime.utcnow().strftime('%d.%m.%Y %H:%M:%S')}"

    text_width1 = pdfmetrics.stringWidth(text1, font_bold, 10)
    text_width2 = pdfmetrics.stringWidth(text2, font_regular, 9)
    text_width3 = pdfmetrics.stringWidth(text3, font_regular, 9)

    max_text_width = max(text_width1, text_width2, text_width3)

    padding = 10
    height = 60
    width = max_text_width + 2 * padding

    x = (page_width - width) / 2
    y = 40

    can.setStrokeColorRGB(0, 0, 0)
    can.setLineWidth(1)
    can.rect(x, y, width, height, stroke=1, fill=0)

    can.setFont(font_bold, 10)
    can.drawString(x + padding, y + height - 15, text1)

    can.setFont(font_regular, 9)
    can.drawString(x + padding, y + height - 30, text2)
    can.drawString(x + padding, y + height - 45, text3)

    can.save()
    packet.seek(0)
    return PdfReader(packet)

def add_signature_stamp(input_pdf, output_pdf, signer_name):
    register_fonts()

    existing_pdf = PdfReader(input_pdf)
    last_page = existing_pdf.pages[-1]
    page_width = float(last_page.MediaBox[2])

    stamp_pdf = create_stamp_pdf(signer_name, page_width)

    output = PdfWriter()

    for i, page in enumerate(existing_pdf.pages):
        if i == len(existing_pdf.pages) - 1:
            merger = PageMerge(page)
            merger.add(stamp_pdf.pages[0], prepend=False).render()
        output.addpage(page)

    output.write(output_pdf)