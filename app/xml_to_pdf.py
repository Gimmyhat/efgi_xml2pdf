# xml_to_pdf.py
import xml.etree.ElementTree as ET
import xmlschema
import os
import platform
import shutil
import pdfkit
import chardet
from jinja2 import Environment, FileSystemLoader


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
        return r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'  # Убедитесь, что путь правильный
    elif platform.system() == 'Linux':
        return '/usr/bin/wkhtmltopdf'  # Путь для Linux
    else:
        raise RuntimeError('Unsupported OS')


def extract_attributes_from_xsd(xsd_path):
    tree = ET.parse(xsd_path)
    root = tree.getroot()
    namespaces = {'xs': 'http://www.w3.org/2001/XMLSchema'}

    attributes_data = {}

    # Проход по всем element и complexType в XSD
    for element in root.findall(".//xs:element", namespaces):
        element_name = element.attrib.get('name')

        # Найдем атрибуты для каждого элемента
        attributes = element.findall('.//xs:attribute', namespaces)
        element_attributes = {}
        for attribute in attributes:
            attr_name = attribute.attrib.get('name')
            attr_type = attribute.attrib.get('type')
            element_attributes[attr_name] = attr_type

        if element_name and element_attributes:
            attributes_data[element_name] = element_attributes

    return attributes_data


def parse_element(element, xsd_attributes):
    """
    Рекурсивная функция для обработки XML-элементов и создания структуры данных для шаблона.
    """
    parsed_data = {
        "name": element.tag,
        "value": element.text.strip() if element.text and element.text.strip() else None,
        "attributes": [],
        "children": []
    }

    # Обработка атрибутов элемента на основе информации из XSD
    element_attributes = xsd_attributes.get(element.tag, {})
    for attr, value in element.attrib.items():
        attr_type = element_attributes.get(attr, 'unknown')
        parsed_data["attributes"].append({
            "name": attr,
            "value": value,
            "type": attr_type  # Добавляем тип атрибута
        })

    # Обработка дочерних элементов
    for child in element:
        child_data = parse_element(child, xsd_attributes)
        if child_data['value'] or child_data['children']:
            parsed_data["children"].append(child_data)

    return parsed_data


def render_template(template_name, context, project_path):
    """
    Функция для рендеринга шаблона с использованием Jinja2.
    """
    templates_dir = os.path.join(project_path, 'templates')  # Путь к папке с шаблонами
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template(template_name)
    return template.render(context)


def convert_xml_to_pdf(xml_path: str, project_path: str, xsd_path: str):
    try:
        temp_dir = create_temp_dir(project_path)
        html_path = os.path.join(temp_dir, "temp.html")
        pdf_path = os.path.join(temp_dir, "output.pdf")

        # Получаем аннотации из XSD схемы
        xsd_annotations = extract_attributes_from_xsd(xsd_path)

        # Определение кодировки XML-файла (для парсинга, а не для записи HTML)
        with open(xml_path, "rb") as file:
            raw_data = file.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding']

        # Парсим XML и подготавливаем данные для шаблона
        tree = ET.parse(xml_path)
        root = tree.getroot()
        data = parse_element(root, xsd_annotations)

        # Преобразование данных из словаря в формат, подходящий для шаблона
        context = {
            "name": find_value(data, 'FullName'),
            "last_name": find_value(data, 'LastName'),  # Добавляем фамилию
            "first_name": find_value(data, 'FirstName'),  # Добавляем имя
            "middle_name": find_value(data, 'MiddleName'),  # Добавляем отчество
            "inn": find_value(data, 'INN'),
            "snils": find_value(data, 'RepresentativeSNILS'),
            "tel": find_value(data, 'Phone'),
            "email": find_value(data, 'Email'),
            "date": find_value(data, 'RequestDate'),
            "inv": find_value(data, 'UniqueID'),
            "coords": extract_coordinates(data),  # Функция для извлечения координат
            "cad": find_value(data, 'CadastralNumber')
        }

        # Рендерим шаблон с данными
        html_content = render_template("template2.html", context, project_path)

        # Сохраняем сгенерированный HTML во временный файл с кодировкой UTF-8
        with open(html_path, "w", encoding="utf-8") as file:  # Принудительное использование UTF-8
            file.write(html_content)

        # Конвертация HTML в PDF
        config = pdfkit.configuration(wkhtmltopdf=get_wkhtmltopdf_path())
        options = {'enable-local-file-access': ''}
        pdfkit.from_file(html_path, pdf_path, configuration=config, options=options)

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Файл PDF не был создан: {pdf_path}")

        return pdf_path
    except Exception as e:
        print(f"Ошибка при конвертации XML в PDF: {e}")
        raise


def find_value(data, target_name):
    """
    Рекурсивно ищет значение элемента по имени в словаре.

    :param data: Словарь, представляющий дерево элементов.
    :param target_name: Имя элемента, значение которого нужно найти.
    :return: Значение элемента с именем target_name, или None, если не найдено.
    """
    # Если текущий элемент содержит нужное имя, возвращаем его значение
    if data['name'] == target_name:
        return data['value']

    # Если элемент имеет детей, рекурсивно ищем среди них
    if 'children' in data:
        for child in data['children']:
            result = find_value(child, target_name)
            if result is not None:
                return result

    # Если имя не найдено в текущем элементе или среди детей, возвращаем None
    return None


def extract_coordinates(data):
    coords = []

    # Поиск координат в словаре
    def recursive_search(d):
        if d['name'] == 'Point':
            lat = find_value(d, 'Latitude')
            lon = find_value(d, 'Longitude')
            if lat and lon:
                coords.append(f"{lat}, {lon}")
        if 'children' in d:
            for child in d['children']:
                recursive_search(child)

    recursive_search(data)
    return coords
