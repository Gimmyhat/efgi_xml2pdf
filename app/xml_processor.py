# xml_processor.py
from datetime import datetime
import xml.etree.ElementTree as ET
from io import BytesIO

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
from app.pdf_utils import add_signature_stamp, sign_pdf
import os

from app.config import TEST_MODE, SIGNER_NAME, SIGNER_PASSWORD, PFX_PATH


def find_value_in_xml(element, target_name):
    if element.tag == target_name and element.text:
        return element.text.strip()
    for child in element:
        result = find_value_in_xml(child, target_name)
        if result is not None:
            return result
    return None


def find_multiple_values_in_xml(element, target_name):
    results = []
    if element.tag == target_name and element.text:
        results.append(element.text.strip())
    for child in element:
        results.extend(find_multiple_values_in_xml(child, target_name))
    return results


def extract_coordinates_from_xml(element):
    coordinates = []
    for point in element.findall('.//Point'):
        latitude = find_value_in_xml(point, 'Latitude')
        longitude = find_value_in_xml(point, 'Longitude')
        if latitude and longitude:
            coordinates.append(f"{latitude}, {longitude}")
    return coordinates


def extract_deposit_info_from_xml(root):
    deposits = []
    formatted_datetime = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    for deposit in root.findall('.//DepositInfo'):
        last_change_date = find_value_in_xml(deposit, 'last_change_date')
        deposit_data = {
            "name": find_value_in_xml(deposit, 'DepositName'),
            "cad_num": find_value_in_xml(deposit, 'CadastreNumber'),
            "licenses": ', '.join(find_multiple_values_in_xml(deposit, 'LicenseNumber')),
            "last_change_date": last_change_date if last_change_date else formatted_datetime,
        }
        deposits.append(deposit_data)
    return deposits


def render_template(template_name, context, project_path):
    templates_dir = os.path.join(project_path, 'templates')
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template(template_name)
    return template.render(context)


async def convert_xml_to_pdf(xml_content: str, project_path: str):
    try:
        root = ET.fromstring(xml_content)

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
            "cad": find_value_in_xml(root, 'CadastralNumber'),
            "is_deposit": find_value_in_xml(root, 'DepositPresence'),
            "in_city": find_value_in_xml(root, 'HasAreaInCity'),
            "coordinate_system": find_value_in_xml(root, 'CoordinateSystem'),
            "test": TEST_MODE,
            "deposit_info_list": extract_deposit_info_from_xml(root) if find_value_in_xml(root,
                                                                                          'DepositPresence') else None
        }

        context['is_10'] = 1 if len(context['deposit_info_list']) == 10 else 0

        html_content = render_template("template2.html", context, project_path)

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

        stamped_pdf_buffer = BytesIO()
        add_signature_stamp(pdf_buffer, stamped_pdf_buffer, SIGNER_NAME)
        stamped_pdf_buffer.seek(0)

        signed_pdf_buffer = BytesIO()
        pfx_path = os.path.join(project_path, 'certs', 'generatedDigital.pfx')
        await sign_pdf(stamped_pdf_buffer, signed_pdf_buffer, PFX_PATH, SIGNER_NAME, SIGNER_PASSWORD, test=TEST_MODE)
        signed_pdf_buffer.seek(0)

        return signed_pdf_buffer

    except Exception as e:
        print(f"Error converting XML to PDF: {e}")
        raise
