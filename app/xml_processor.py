import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
from io import BytesIO
import logging
import os

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

from config import TEST_MODE, SIGNER_NAME, SIGNER_PASSWORD, PFX_FILE, F_DATE
from logger import get_logger
from pdf_utils import add_signature_stamp, sign_pdf, add_page_numbers

# Настройка логирования
logger = get_logger(__name__)

# Экзекутор для асинхронных задач
executor = ThreadPoolExecutor()

# Установка уровня логирования для сторонних библиотек
logging.getLogger('fontTools').setLevel(logging.WARNING)
logging.getLogger('weasyprint').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)

# Московский часовой пояс
MOSCOW_TZ = timezone(timedelta(hours=3))


def find_values_in_xml(element, target_name, multiple=False):
    """
    Находит значения в XML, используя XPath.

    Args:
        element (ET.Element): XML-элемент, в котором нужно искать.
        target_name (str): Имя тега, значения которого нужно найти.
        multiple (bool): Если True, возвращает список значений.
                         Если False, возвращает первое найденное значение.

    Returns:
        str/list: Найденное значение или список значений.
    """
    try:
        values = element.findall(f".//{target_name}")
        if multiple:
            return [value.text.strip() for value in values if value.text]
        elif values:
            return values[0].text.strip()
    except AttributeError:
        logger.warning(f"AttributeError in find_values_in_xml for target: {target_name}")
    return None if not multiple else []


def extract_coordinates_from_xml(element):
    coordinates = []
    try:
        for plot in element.findall('.//Plot'):
            plot_number = plot.get('Number', '')
            plot_name = plot.get('Name', '')
            plot_coords = []
            for polygon in plot.findall('.//Polygon'):
                polygon_coords = []  # Список координат для текущего полигона
                for point in polygon.findall('.//Point'):
                    latitude = find_values_in_xml(point, 'Latitude')
                    longitude = find_values_in_xml(point, 'Longitude')
                    if latitude and longitude:
                        polygon_coords.append(f"{latitude}, {longitude}")
                plot_coords.append(polygon_coords)  # Добавляем список координат полигона в список участка
            coordinates.append({
                "number": plot_number,
                "name": plot_name,
                "coords": plot_coords
            })
    except AttributeError:
        logger.warning("AttributeError in extract_coordinates_from_xml")
    return coordinates


def extract_deposit_info_from_xml(root):
    """
    Извлекает информацию о месторождениях из XML, разделяя их на ОПИ и не-ОПИ.
    Args:
        root (ET.Element): Корневой элемент XML.
    Returns:
        tuple: Два списка - opi_deposits (месторождения ОПИ) и non_opi_deposits (остальные месторождения).
    """
    opi_deposits = []  # Список для месторождений ОПИ
    non_opi_deposits = []  # Список для остальных месторождений
    formatted_datetime = datetime.now(MOSCOW_TZ).strftime(F_DATE)
    try:
        for deposit in root.findall('.//DepositInfo'):
            last_change_date_str = find_values_in_xml(deposit, 'last_change_date')

            # Парсим и форматируем дату последнего изменения
            if last_change_date_str:
                try:
                    last_change_date = datetime.strptime(last_change_date_str, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc).astimezone(MOSCOW_TZ)
                except ValueError:
                    last_change_date = datetime.strptime(last_change_date_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(MOSCOW_TZ)
                last_change_date_str = last_change_date.strftime(F_DATE)


            deposit_data = { # Формируем словарь с данными о месторождении
                "name": find_values_in_xml(deposit, 'DepositName'),
                "licenses": ', '.join(find_values_in_xml(deposit, 'LicenseNumber', multiple=True)),
                "last_change_date": last_change_date_str if last_change_date_str else formatted_datetime,
                "is_opi": find_values_in_xml(deposit, 'isOPI'),
            }

            # Разделяем месторождения на ОПИ и не-ОПИ
            if deposit_data["is_opi"] == "1":
                opi_deposits.append(deposit_data)
            else:
                non_opi_deposits.append(deposit_data)

    except AttributeError:
        logger.warning("AttributeError в extract_deposit_info_from_xml")

    return opi_deposits, non_opi_deposits


def enumerate_filter(iterable):
    return list(enumerate(iterable))

def render_template(template_name, context, project_path):
    try:
        templates_dir = os.path.join(project_path, 'templates')
        env = Environment(loader=FileSystemLoader(templates_dir))
        env.filters['enumerate'] = enumerate_filter # Регистрируем фильтр
        template = env.get_template(template_name)
        return template.render(context)
    except Exception as e:
        logger.error(f"Error rendering template: {e}")
        raise


async def convert_xml_to_pdf(xml_content: str, project_path: str):
    try:
        logger.info("Starting XML to PDF conversion")
        root = ET.fromstring(xml_content)

        request_datetime = find_values_in_xml(root, 'RequestDateTime')
        opi_deposits, non_opi_deposits = extract_deposit_info_from_xml(root)


        # Парсим и форматируем дату
        date_object = datetime.strptime(request_datetime.split(".")[0], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc).astimezone(MOSCOW_TZ)
        formatted_date = date_object.strftime(F_DATE)

        # Формирование контекста для шаблона
        context = {
            "name": find_values_in_xml(root, 'FullName'),
            "last_name": find_values_in_xml(root, 'LastName'),
            "first_name": find_values_in_xml(root, 'FirstName'),
            "middle_name": find_values_in_xml(root, 'MiddleName'),
            "inn": find_values_in_xml(root, 'INN'),
            "snils": find_values_in_xml(root, 'RepresentativeSNILS'),
            "tel": find_values_in_xml(root, 'Phone'),
            "email": find_values_in_xml(root, 'Email'),
            "date": formatted_date,
            "inv": find_values_in_xml(root, 'UniqueID'),
            "coords": extract_coordinates_from_xml(root),
            "is_deposit": find_values_in_xml(root, 'DepositPresence'),
            "in_city": find_values_in_xml(root, 'HasAreaInCity'),
            "test": TEST_MODE,
            "opi_deposits": opi_deposits,
            "non_opi_deposits": non_opi_deposits,
            "has_opi_deposits": bool(opi_deposits), # Флаг наличия месторождений ОПИ
            "has_non_opi_deposits": bool(non_opi_deposits), # Флаг наличия других месторождений
        }

        context['is_10'] = 1 if len(context.get('opi_deposits', [])) + len(
            context.get('non_opi_deposits', [])) == 10 else 0

        # Генерация HTML из шаблона
        html_content = render_template("template2.html", context, project_path)

        logger.info("Generating PDF from HTML")
        pdf_buffer = BytesIO()
        html = HTML(string=html_content, base_url=project_path)
        css = CSS(string=''' 
            @page {
                size: A4;
                margin-top: 10mm;
                margin-right: 20mm;
                margin-bottom: 35mm;
                margin-left: 10mm;
            }
        ''')

        # Асинхронная генерация PDF
        await asyncio.get_event_loop().run_in_executor(
            executor, lambda: html.write_pdf(pdf_buffer, stylesheets=[css])
        )
        pdf_buffer.seek(0)

        logger.info("Adding signature stamp")
        stamped_pdf_buffer = BytesIO()

        # Асинхронное добавление штампа
        await asyncio.get_event_loop().run_in_executor(
            executor, lambda: add_signature_stamp(pdf_buffer, stamped_pdf_buffer, SIGNER_NAME)
        )
        stamped_pdf_buffer.seek(0)

        logger.info("Adding page numbers")
        # Асинхронное добавление номеров страниц
        numbered_pdf_buffer = await asyncio.get_event_loop().run_in_executor(
            executor, lambda: add_page_numbers(stamped_pdf_buffer)
        )

        logger.info("Signing PDF")
        signed_pdf_buffer = BytesIO()
        pfx_path = os.path.join(project_path, 'certs', PFX_FILE)

        # Подпись PDF
        await sign_pdf(numbered_pdf_buffer, signed_pdf_buffer, pfx_path, SIGNER_NAME, SIGNER_PASSWORD, test=TEST_MODE)

        # Ожидание завершения подписания
        signed_pdf_content = signed_pdf_buffer.read()  # Читаем данные из буфера

        logger.info("PDF conversion and signing completed successfully")
        return BytesIO(signed_pdf_content)  # Возвращаем буфер с подписанными данными



    except ET.ParseError as e:
        logger.error(f"Error parsing XML: {e}")
        raise ValueError("Invalid XML format")
    except Exception as e:
        logger.error(f"Error converting XML to PDF: {e}")
        raise
