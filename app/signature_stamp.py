import platform
from pdfrw import PdfReader, PdfWriter, PageMerge
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
from datetime import datetime
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import os


def get_font_path():
    if platform.system() == 'Windows':
        # Укажите путь к шрифту Arial для Windows
        return 'C:\\Windows\\Fonts\\arial.ttf'
    else:
        # Укажите путь к шрифту DejaVuSans для Linux
        return '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def add_signature_stamp(input_pdf_path, output_pdf_path, signer_name):
    # Регистрация шрифта
    font_path = get_font_path()
    pdfmetrics.registerFont(TTFont('CustomFont', font_path))

    # Создание PDF с печатью
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)

    # Определение размеров и позиции рамки
    x = 150
    y = 40  # Положение штампа внизу страницы
    width = 290
    height = 60
    border_width = 2

    # Рисование рамки
    can.setStrokeColorRGB(0, 0, 0)  # Цвет рамки (черный)
    can.setLineWidth(border_width)
    can.rect(x - border_width, y - border_width, width + 2 * border_width, height + 2 * border_width)

    # Внутри рамки
    can.setFont('CustomFont', 8)  # Используйте зарегистрированный шрифт
    can.drawString(x + 5, y + height - 10, "Документ подписан электронной подписью")
    can.drawString(x + 5, y + height - 30, f"Подписант: {signer_name}")
    can.drawString(x + 5, y + height - 50, f"Дата и время подписания (UTC): "
                                           f"{datetime.utcnow().strftime('%d.%m.%Y %H:%M:%S')}")

    can.save()

    # Перемещение указателя в начало BytesIO
    packet.seek(0)
    stamp_pdf = PdfReader(packet)

    # Чтение существующего PDF
    try:
        existing_pdf = PdfReader(input_pdf_path)
    except Exception as e:
        print(f"Ошибка при открытии PDF файла: {str(e)}")
        raise

    # Создание нового PDF с объединенными страницами
    output = PdfWriter()

    # Обрабатываем каждую страницу
    for i, page in enumerate(existing_pdf.pages):
        if i == len(existing_pdf.pages) - 1:
            # Только для последней страницы
            merger = PageMerge(page)
            merger.add(stamp_pdf.pages[0]).render()
        output.addpage(page)

    # Запись результата в файл
    output.write(output_pdf_path)
