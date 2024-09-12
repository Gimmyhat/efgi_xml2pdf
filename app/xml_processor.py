# xml_processor.py
from datetime import datetime
import xml.etree.ElementTree as ET
from io import BytesIO
import logging

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

from logger import get_logger
from pdf_utils import add_signature_stamp, sign_pdf
import os

from config import TEST_MODE, SIGNER_NAME, SIGNER_PASSWORD, PFX_FILE

# Настройка логирования
logger = get_logger(__name__)

# Установка уровня логирования WARNING для сторонних библиотек
logging.getLogger('fontTools').setLevel(logging.WARNING)
logging.getLogger('weasyprint').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)


def find_value_in_xml(element, target_name):
    try:
        if element.tag == target_name and element.text:
            return element.text.strip()
        for child in element:
            result = find_value_in_xml(child, target_name)
            if result is not None:
                return result
    except AttributeError:
        logger.warning(f"AttributeError in find_value_in_xml for target: {target_name}")
    return None


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


# xml_processor.py

def extract_coordinates_from_xml(element):
    coordinates = []
    try:
        for plot in element.findall('.//Plot'):
            plot_number = plot.get('Number', '')
            plot_coords = []
            for polygon in plot.findall('.//Polygon'):
                polygon_coords = [] # Список координат для текущего полигона
                for point in polygon.findall('.//Point'):
                    latitude = find_value_in_xml(point, 'Latitude')
                    longitude = find_value_in_xml(point, 'Longitude')
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
    formatted_datetime = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    try:
        for deposit in root.findall('.//DepositInfo'):
            last_change_date = find_value_in_xml(deposit, 'last_change_date')
            deposit_data = {
                "name": find_value_in_xml(deposit, 'DepositName'),
                "licenses": ', '.join(find_multiple_values_in_xml(deposit, 'LicenseNumber')),
                "last_change_date": last_change_date if last_change_date else formatted_datetime,
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

        deposit_presence = find_value_in_xml(root, 'DepositPresence')

        context = {
            "name": find_value_in_xml(root, 'FullName'),
            "last_name": find_value_in_xml(root, 'LastName'),
            "first_name": find_value_in_xml(root, 'FirstName'),
            "middle_name": find_value_in_xml(root, 'MiddleName'),
            "inn": find_value_in_xml(root, 'INN'),
            "snils": find_value_in_xml(root, 'RepresentativeSNILS'),
            "tel": find_value_in_xml(root, 'Phone'),
            "email": find_value_in_xml(root, 'Email'),
            "date": find_value_in_xml(root, 'RequestDate'),
            "inv": find_value_in_xml(root, 'UniqueID'),
            "coords": extract_coordinates_from_xml(root),
            "is_deposit": find_value_in_xml(root, 'DepositPresence'),
            "in_city": find_value_in_xml(root, 'HasAreaInCity'),
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
                margin-top: 5mm;
                margin-right: 20mm;
                margin-bottom: 20mm;
                margin-left: 10mm;
            }
            @page {
                @bottom-center {
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
        signed_pdf_buffer.seek(0)

        logger.info("PDF conversion and signing completed successfully")
        return signed_pdf_buffer

    except ET.ParseError as e:
        logger.error(f"Error parsing XML: {e}")
        raise ValueError("Invalid XML format")
    except Exception as e:
        logger.error(f"Error converting XML to PDF: {e}")
        raise