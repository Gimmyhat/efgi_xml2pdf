import xml.etree.ElementTree as ET
import os
import shutil
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from app.pdf_signer import sign_pdf
from app.signature_stamp import add_signature_stamp
from weasyprint import HTML
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

debug_env = os.getenv('DEBUG', 'False')

# Преобразуем строковое значение в булево
DEBUG = debug_env.lower() in ['true', '1', 't', 'y', 'yes']

if DEBUG:
    name_cert = "TEST"
    pswd_cert = "12345"
else:
    name_cert = "ФЕДЕРАЛЬНОЕ АГЕНТСТВО ПО НЕДРОПОЛЬЗОВАНИЮ"
    pswd_cert = "00000000"

print(name_cert)

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
    for deposit in root.findall('.//DepositInfo'):
        deposit_data = {
            "name": find_value_in_xml(deposit, 'DepositName'),
            "cad_num": find_value_in_xml(deposit, 'CadastreNumber'),
            "licenses": ', '.join(find_multiple_values_in_xml(deposit, 'LicenseNumber'))
        }
        deposits.append(deposit_data)
    return deposits

def render_template(template_name, context, project_path):
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
            "coordinate_system": find_value_in_xml(root, 'CoordinateSystem'),
            "signature": "Примерная подпись",
            "signature_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "debug": DEBUG,
            "deposit_info_list": extract_deposit_info_from_xml(root) if find_value_in_xml(root, 'DepositPresence') else None
        }

        context['is_10'] = 1 if len(context['deposit_info_list']) == 10 else 0

        # Рендерим основной шаблон
        html_content = render_template("template2.html", context, project_path)

        # Сохраняем HTML для основного шаблона
        with open(html_path, "w", encoding="utf-8") as file:
            file.write(html_content)

        # Генерация PDF с помощью weasyprint
        try:
            html = HTML(string=html_content, base_url=project_path)
            html.write_pdf(pdf_path)
        except Exception as e:
            print(f"Ошибка при создании PDF с помощью weasyprint: {e}")
            raise

        # Добавляем штамп на последнюю страницу
        try:
            stamp_pdf_path = os.path.join(temp_dir, "final_output.pdf")
            add_signature_stamp(pdf_path, stamp_pdf_path, name_cert)
        except Exception as e:
            print(f"Ошибка при добавлении штампа: {str(e)}")
            raise

        # Подписываем PDF с использованием PFX
        pfx_path = os.path.join(project_path, 'certs', 'generatedDigital.pfx')

        try:
            await sign_pdf(stamp_pdf_path, signed_pdf_path, pfx_path, name_cert, pswd_cert, test=DEBUG)
        except Exception as e:
            print(f"Ошибка при подписании PDF: {str(e)}")
            raise

        return signed_pdf_path

    except Exception as e:
        print(f"Ошибка при конвертации XML в PDF: {e}")
        raise

