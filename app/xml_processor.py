from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
from io import BytesIO
import logging
import os

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

from config import TEST_MODE, SIGNER_NAME, SIGNER_PASSWORD, PFX_FILE
from logger import get_logger
from pdf_utils import add_signature_stamp, sign_pdf

# Настройка логирования
logger = get_logger(__name__)

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


def find_multiple_values_in_xml(element, target_name):
    results = []
    try:
        if element.tag == target_name and element.text:
            results.append(element.text.strip())
        for child in element:
            results.extend(find_multiple_values_in_xml(child, target_name))
    except AttributeError:
        logger.warning(f"AttributeError in find_multiple_values_in_xml for target: {target_name}")
    return results


def extract_coordinates_from_xml(element):
    coordinates = []
    try:
        for plot in element.findall('.//Plot'):
            plot_number = plot.get('Number', '')
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
                "coords": plot_coords
            })
    except AttributeError:
        logger.warning("AttributeError in extract_coordinates_from_xml")
    return coordinates


def extract_deposit_info_from_xml(root):
    deposits = []
    formatted_datetime = datetime.now(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M:%S")
    try:
        for deposit in root.findall('.//DepositInfo'):
            last_change_date_str = find_values_in_xml(deposit, 'last_change_date')

            if last_change_date_str:
                try:
                    last_change_date = datetime.strptime(last_change_date_str, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc).astimezone(MOSCOW_TZ)
                except ValueError:
                    last_change_date = datetime.strptime(last_change_date_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(MOSCOW_TZ)
                last_change_date_str = last_change_date.strftime("%d.%m.%Y %H:%M:%S")

            deposit_data = {
                "name": find_values_in_xml(deposit, 'DepositName'),
                "licenses": ', '.join(find_values_in_xml(deposit, 'LicenseNumber', multiple=True)),
                "last_change_date": last_change_date_str if last_change_date_str else formatted_datetime,
            }
            deposits.append(deposit_data)
    except AttributeError:
        logger.warning("AttributeError in extract_deposit_info_from_xml")

    if not deposits:
        logger.info("No deposit information found in XML")

    return deposits


def render_template(template_name, context, project_path):
    try:
        templates_dir = os.path.join(project_path, 'templates')
        env = Environment(loader=FileSystemLoader(templates_dir))
        template = env.get_template(template_name)
        return template.render(context)
    except Exception as e:
        logger.error(f"Error rendering template: {e}")
        raise


async def convert_xml_to_pdf(xml_content: str, project_path: str):
    try:
        logger.info("Starting XML to PDF conversion")
        root = ET.fromstring(xml_content)

        deposit_presence = find_values_in_xml(root, 'DepositPresence')
        request_datetime = find_values_in_xml(root, 'RequestDateTime')

        date_object = datetime.strptime(request_datetime.split(".")[0], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc).astimezone(MOSCOW_TZ)

        formatted_date = date_object.strftime("%Y-%m-%d %H:%M:%S") # Удалена дублирующая строка

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
            "deposit_info_list": extract_deposit_info_from_xml(root) if deposit_presence and deposit_presence.lower()
                                                                        in ['1', 'true'] else [],
        }

        context['is_10'] = 1 if len(context.get('deposit_info_list', [])) == 10 else 0

        html_content = render_template("template2.html", context, project_path)

        logger.info("Generating PDF from HTML")
        pdf_buffer = BytesIO()
        html = HTML(string=html_content, base_url=project_path)
        css = CSS(string='''
            @page {
                size: A4;
                margin-top: 10mm;
                margin-right: 20mm;
                margin-bottom: 20mm;
                margin-left: 10mm;
                @top-right {
                    content: "Страница " counter(page) " из " counter(pages);
                    font-size: 10pt;
                    color: gray;
                }
            }
        ''')

        html.write_pdf(pdf_buffer, stylesheets=[css])
        pdf_buffer.seek(0)

        logger.info("Adding signature stamp")
        stamped_pdf_buffer = BytesIO()
        add_signature_stamp(pdf_buffer, stamped_pdf_buffer, SIGNER_NAME)
        stamped_pdf_buffer.seek(0)

        logger.info("Signing PDF")
        signed_pdf_buffer = BytesIO()
        pfx_path = os.path.join(project_path, 'certs', PFX_FILE)
        await sign_pdf(stamped_pdf_buffer, signed_pdf_buffer, pfx_path, SIGNER_NAME, SIGNER_PASSWORD, test=TEST_MODE)

        # Ожидание завершения подписания
        signed_pdf_buffer.seek(0)  # Перемещаем указатель в начало буфера
        signed_pdf_content = signed_pdf_buffer.read()  # Читаем данные из буфера

        logger.info("PDF conversion and signing completed successfully")
        return BytesIO(signed_pdf_content)  # Возвращаем буфер с подписанными данными


    except ET.ParseError as e:
        logger.error(f"Error parsing XML: {e}")
        raise ValueError("Invalid XML format")
    except Exception as e:
        logger.error(f"Error converting XML to PDF: {e}")
        raise
