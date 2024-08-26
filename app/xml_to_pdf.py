# xml_to_pdf.py
import asyncio
import xml.etree.ElementTree as ET
import os
import platform
import shutil
import pdfkit
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from app.pdf_signer import sign_pdf


def create_temp_dir(project_path):
    temp_dir = os.path.join(project_path, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def delete_temp_dir(temp_dir):
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Ошибка при удалении {temp_dir}: {e}")


def get_wkhtmltopdf_path():
    if platform.system() == 'Windows':
        return r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    elif platform.system() == 'Linux':
        return '/usr/bin/wkhtmltopdf'
    else:
        raise RuntimeError('Unsupported OS')


def find_value_in_xml(element, target_name):
    """
    Рекурсивно ищет значение элемента по имени тега в XML.
    """
    if element.tag == target_name and element.text:
        return element.text.strip()

    for child in element:
        result = find_value_in_xml(child, target_name)
        if result is not None:
            return result

    return None


def find_multiple_values_in_xml(element, target_name):
    """
    Ищет все значения элементов с указанным именем тега в XML.
    Возвращает список всех найденных значений.
    """
    results = []

    if element.tag == target_name and element.text:
        results.append(element.text.strip())

    for child in element:
        results.extend(find_multiple_values_in_xml(child, target_name))

    return results


def extract_coordinates_from_xml(element):
    """
    Извлекает координаты из XML элемента.
    """
    coordinates = []

    for point in element.findall('.//Point'):
        latitude = find_value_in_xml(point, 'Latitude')
        longitude = find_value_in_xml(point, 'Longitude')
        if latitude and longitude:
            coordinates.append(f"{latitude}, {longitude}")

    return coordinates


def extract_deposit_info_from_xml(root):
    """
    Извлекает данные о всех месторождениях из XML.
    """
    deposits = []

    for deposit in root.findall('.//DepositInfo'):
        deposit_data = {
            "name": find_value_in_xml(deposit, 'DepositName'),
            "cad_num": find_value_in_xml(deposit, 'CadastreNumber'),
            "licenses": ', '.join(find_multiple_values_in_xml(deposit, 'LicenseNumber'))
        }
        deposits.append(deposit_data)

    return deposits


def render_template(template_name, context, project_path):
    """
    Функция для рендеринга шаблона с использованием Jinja2.
    """
    templates_dir = os.path.join(project_path, 'templates')
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template(template_name)
    return template.render(context)


async def convert_xml_to_pdf(xml_path: str, project_path: str, xsd_path: str):
    try:
        temp_dir = create_temp_dir(project_path)
        html_path = os.path.join(temp_dir, "temp.html")
        pdf_path = os.path.join(temp_dir, "output.pdf")
        signed_pdf_path = os.path.join(temp_dir, "signed_output.pdf")

        # Парсим XML файл
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Извлекаем данные напрямую из XML
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
            "signature": "Примерная подпись",
            "signature_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            # Собираем список всех месторождений
            "deposit_info_list": extract_deposit_info_from_xml(root) if find_value_in_xml(root,
                                                                                          'DepositPresence') else None
        }

        # Рендерим шаблон
        html_content = render_template("template2.html", context, project_path)

        # Сохраняем HTML и создаем PDF
        with open(html_path, "w", encoding="utf-8") as file:
            file.write(html_content)

        config = pdfkit.configuration(wkhtmltopdf=get_wkhtmltopdf_path())
        options = {
            'enable-local-file-access': '',
            'dpi': 400,
            'page-size': 'A4',
            'margin-top': '20mm',
            'margin-bottom': '20mm',
            # 'disable-smart-shrinking': ''
        }
        try:
            pdfkit.from_file(html_path, pdf_path, configuration=config, options=options)
        except Exception as e:
            print(f"Ошибка при создании PDF: {e}")
            raise

        # Подписываем PDF
        cert_path = os.path.join(project_path, 'certs', 'cert.pem')
        private_key_path = os.path.join(project_path, 'certs', 'private_key.pem')
        private_key_password = "042520849"

        await sign_pdf(pdf_path, signed_pdf_path, cert_path, private_key_path, password=private_key_password)

        return signed_pdf_path
    except Exception as e:
        print(f"Ошибка при конвертации XML в PDF: {e}")
        raise
