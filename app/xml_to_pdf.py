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


def extract_annotations_from_xsd(xsd_path):
    tree = ET.parse(xsd_path)
    root = tree.getroot()
    namespaces = {'xs': 'http://www.w3.org/2001/XMLSchema'}

    annotations = {}

    # Проход по всем complexType и element
    for element in root.findall(".//xs:element", namespaces):
        name = element.attrib.get('name')
        doc = element.find('.//xs:documentation', namespaces)
        if name and doc is not None:
            annotations[name] = doc.text

    for complex_type in root.findall(".//xs:complexType", namespaces):
        name = complex_type.attrib.get('name')
        doc = complex_type.find('.//xs:documentation', namespaces)
        if name and doc is not None:
            annotations[name] = doc.text

    return annotations


def parse_element(element, xsd_annotations):
    """
    Рекурсивная функция для обработки XML-элементов и создания структуры данных для шаблона.
    """
    parsed_data = {
        "name": xsd_annotations.get(element.tag, element.tag),
        "value": element.text.strip() if element.text and element.text.strip() else None,
        "attributes": [],
        "children": []
    }

    # Обработка атрибутов элемента
    for attr, value in element.attrib.items():
        parsed_data["attributes"].append({
            "name": xsd_annotations.get(attr, attr),
            "value": value
        })

    # Обработка дочерних элементов
    for child in element:
        child_data = parse_element(child, xsd_annotations)
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
        xsd_annotations = extract_annotations_from_xsd(xsd_path)

        # Определение кодировки XML-файла (для парсинга, а не для записи HTML)
        with open(xml_path, "rb") as file:
            raw_data = file.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding']

        # Парсим XML и подготавливаем данные для шаблона
        tree = ET.parse(xml_path)
        root = tree.getroot()
        parsed_data = parse_element(root, xsd_annotations)

        # Подготовка данных для шаблона
        context = {
            "root_element": parsed_data
        }

        # Рендерим шаблон с данными
        html_content = render_template("template.html", context, project_path)

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
