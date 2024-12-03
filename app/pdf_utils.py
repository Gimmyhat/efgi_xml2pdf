# pdf_utils.py
import asyncio
import io
import os
from io import BytesIO
from datetime import datetime, timezone, timedelta
from logging import Logger
from typing import Union

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBox
from pyhanko.sign import signers, PdfSignatureMetadata
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign.signers.pdf_signer import PdfSigner
from pdfrw import PdfReader, PdfWriter, PageMerge
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import tempfile

from config import F_DATE, OUTPUT_PATH
from logger import get_logger

# Настройка логирования
logger: Logger = get_logger(__name__)

# Московский часовой пояс
MOSCOW_TZ = timezone(timedelta(hours=3))

# Константы для штампа
STAMP_HEIGHT = 100
STAMP_PADDING = 10
STAMP_FONT_REGULAR = 'Roboto-Regular'
STAMP_FONT_BOLD = 'Roboto-Bold'
STAMP_FONT_SIZE_REGULAR = 9
STAMP_FONT_SIZE_BOLD = 10

# Предварительная регистрация шрифтов
try:
    roboto_regular = os.path.join('static', 'fonts', 'Roboto-Regular.ttf')
    roboto_bold = os.path.join('static', 'fonts', 'Roboto-Bold.ttf')
    pdfmetrics.registerFont(TTFont(STAMP_FONT_REGULAR, roboto_regular))
    pdfmetrics.registerFont(TTFont(STAMP_FONT_BOLD, roboto_bold))
except Exception as e:
    logger.error(f"Error registering fonts: {e}")


async def sign_pdf(input_pdf: BytesIO, output_pdf: BytesIO, pfx_path: str,
                   cert_name: str, password: str, test: bool = False):
    """
    Подписывает PDF-файл.
    """
    if not test:
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_input_path = os.path.join(temp_dir, "input.pdf")
                temp_output_path = os.path.join(temp_dir, "output.pdf")

                logger.info(f"Writing PDF to temporary file: {temp_input_path}")
                with open(temp_input_path, "wb") as f:
                    f.write(input_pdf.read())
                    f.flush()  # Принудительная запись данных на диск
                logger.info(f"PDF written to temporary file.")

                # Формируем команду для csptest
                command = [
                    "csptest", "-sfsign", "-sign",
                    "-in", temp_input_path,
                    "-out", temp_output_path,
                    "-my", cert_name,
                    "-add"
                ]

                logger.info(f"Starting csptest with command: {command}")
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
                    logger.info(f"csptest completed successfully.")
                    # Читаем подписанный файл и записываем в output_pdf
                    with open(temp_output_path, "rb") as f:
                        output_pdf.write(f.read())
                    output_pdf.seek(0)
                else:
                    error_message = stderr.decode('utf-8')
                    logger.error(f"Error during PDF signing. Return code: {process.returncode}")
                    logger.error(f"Error: {error_message}")
                    raise Exception(f"Failed to sign PDF. Error: {error_message}")

        except Exception as e:
            logger.error(f"Error during PDF signing: {str(e)}")
            raise  # Передаем исключение дальше для обработки в вызывающей функции
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


def create_stamp_pdf(signer_name: str, page_width: float, page_height: float) -> PdfReader:
    """
    Создает PDF-файл со штампом.
    """
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=(page_width, page_height))

    current_time = datetime.now(MOSCOW_TZ).strftime(F_DATE)

    text1 = "Документ подписан электронной подписью"
    text2 = f"Подписант: {signer_name}"
    text3 = f"Дата и время: {current_time}"

    # Вычисляем ширину текста для каждого элемента
    text_width1 = pdfmetrics.stringWidth(text1, STAMP_FONT_BOLD, STAMP_FONT_SIZE_BOLD)
    text_width2 = pdfmetrics.stringWidth(text2, STAMP_FONT_REGULAR, STAMP_FONT_SIZE_REGULAR)
    text_width3 = pdfmetrics.stringWidth(text3, STAMP_FONT_REGULAR, STAMP_FONT_SIZE_REGULAR)
    max_text_width = max(text_width1, text_width2, text_width3)

    # Вычисляем размеры и позицию штампа
    width = max_text_width + 2 * STAMP_PADDING
    height = 60
    x = (page_width - width) / 2
    y = 30

    # Рисуем рамку штампа
    can.setStrokeColorRGB(0, 0, 0)
    can.setLineWidth(1)
    can.rect(x, y, width, height, stroke=1, fill=0)

    # Добавляем текст в штамп
    can.setFont(STAMP_FONT_BOLD, STAMP_FONT_SIZE_BOLD)
    can.drawString(x + STAMP_PADDING, y + height - 15, text1)

    can.setFont(STAMP_FONT_REGULAR, STAMP_FONT_SIZE_REGULAR)
    can.drawString(x + STAMP_PADDING, y + height - 30, text2)
    can.drawString(x + STAMP_PADDING, y + height - 45, text3)

    can.save()
    packet.seek(0)
    return PdfReader(packet)


def get_bottom_margin(input_pdf: Union[str, io.BytesIO, bytes]) -> float:
    """
    Определяет расстояние от нижнего края последней страницы до последнего текстового элемента.

    :param input_pdf: Путь к файлу PDF, объект BytesIO или байтовая строка, содержащая PDF
    :return: Расстояние от нижнего края до последнего текстового элемента в пунктах
    """
    try:
        # Подготавливаем входные данные
        if isinstance(input_pdf, str):
            pdf_file = input_pdf
        elif isinstance(input_pdf, io.BytesIO):
            pdf_file = input_pdf
        elif isinstance(input_pdf, bytes):
            pdf_file = io.BytesIO(input_pdf)
        else:
            raise ValueError("Неподдерживаемый тип входных данных")

        # Извлекаем страницы из PDF
        pages = list(extract_pages(pdf_file))

        if not pages:
            logger.error("PDF документ не содержит страниц")
            return 0

        # Получаем последнюю страницу
        last_page = pages[-1]

        # Находим текстовые элементы на странице
        text_elements = [element for element in last_page if isinstance(element, LTTextBox)]

        if not text_elements:
            logger.warning("На последней странице не найдено текстовых элементов")
            return last_page.height

        # Находим самый нижний текстовый элемент
        bottom_most_element = min(text_elements, key=lambda e: e.y0)

        # Вычисляем расстояние от нижнего края страницы до нижнего края текстового элемента
        bottom_margin = bottom_most_element.y0

        return bottom_margin

    except Exception as e:
        logger.error(f"Ошибка при получении нижнего отступа: {str(e)}")
        return 0


def add_signature_stamp(input_pdf, output_pdf, signer_name):
    try:
        existing_pdf = PdfReader(input_pdf)
        if len(existing_pdf.pages) == 0:
            raise ValueError("PDF документ не содержит страниц")

        # Получаем размеры первой страницы для создания штампа
        first_page = existing_pdf.pages[0]
        if '/MediaBox' not in first_page:
            raise ValueError("Невозможно получить размеры страницы")

        page_width = float(first_page['/MediaBox'][2])
        page_height = float(first_page['/MediaBox'][3])

        # Создаем штамп один раз, который будем использовать для всех страниц
        stamp_pdf = create_stamp_pdf(signer_name, page_width, page_height)

        output = PdfWriter()

        # Обрабатываем каждую страницу
        for page in existing_pdf.pages:
            # Получаем отступ для текущей страницы
            page_buffer = BytesIO()
            temp_writer = PdfWriter()
            temp_writer.addpage(page)
            temp_writer.write(page_buffer)
            page_buffer.seek(0)
            bottom_margin = get_bottom_margin(page_buffer)

            # Добавляем штамп на страницу
            merger = PageMerge(page)

            # Вычисляем позицию штампа
            if bottom_margin < STAMP_HEIGHT:
                # Если места недостаточно, размещаем штамп выше текста
                stamp_y = page_height - STAMP_HEIGHT - 10
            else:
                # Если места достаточно, размещаем штамп с учетом отступа
                stamp_y = page_height - STAMP_HEIGHT - 10 - bottom_margin

            stamp_page = stamp_pdf.pages[0]
            stamp_page.y = stamp_y

            # Добавляем штамп и сохраняем страницу
            merger.add(stamp_page).render()
            output.addpage(merger.render())

        output.write(output_pdf)
        output_pdf.seek(0)
    except Exception as e:
        logger.error(f"Ошибка при добавлении штампов подписи: {str(e)}")
        raise

FONT_PATH = os.path.join('static', 'fonts', 'Roboto-Regular.ttf')

def add_page_numbers(pdf_buffer):
    pdf_reader = PdfReader(pdf_buffer)
    pdf_writer = PdfWriter()

    for page_num, page in enumerate(pdf_reader.pages):
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        can.setFont("Roboto-Regular", 10)
        can.drawString(500, 20, f"Страница {page_num + 1} из {len(pdf_reader.pages)}")
        can.save()
        packet.seek(0)

        new_pdf = PdfReader(packet)
        merger = PageMerge(page)
        merger.add(new_pdf.pages[0]).render()
        pdf_writer.addpage(page)

    output_buffer = io.BytesIO()
    pdf_writer.write(output_buffer)
    output_buffer.seek(0)
    return output_buffer

# Генерация пустого PDF
def create_empty_pdf(buffer):
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 750, "Error: PDF file not generated due to an error.")
    c.showPage()
    c.save()

# Функция для создания пустого PDF и обработки ошибок
async def create_error_pdf(filename, message):
    pdf_buffer = BytesIO()
    create_empty_pdf(pdf_buffer)
    pdf_filepath = os.path.join(OUTPUT_PATH, filename)
    with open(pdf_filepath, "wb") as f:
        f.write(pdf_buffer.getvalue())
    return pdf_buffer