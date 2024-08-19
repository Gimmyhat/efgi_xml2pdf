# xml_to_pdf.py
import xml.etree.ElementTree as ET
import xmlschema
import os
import platform
import shutil
import pdfkit
import chardet


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


def parse_xsd_annotations(xsd_path: str) -> dict:
    schema = xmlschema.XMLSchema(xsd_path)
    annotations = {}

    for elem in schema.elements.values():
        annotations[elem.name] = elem.annotation or elem.name
        for attr_name, attr in elem.attributes.items():
            annotations[attr_name] = attr.annotation or attr_name

    return annotations


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

    return annotations


def parse_xml_to_html(xml_path: str, xsd_annotations: dict) -> str:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    def parse_element(element):
        html_content = f"<h2>{xsd_annotations.get(element.tag, element.tag)}</h2>"
        if element.text and element.text.strip():
            html_content += f"<p><strong>Value:</strong> {element.text.strip()}</p>"
        if element.attrib:
            for attr, value in element.attrib.items():
                html_content += f"<p><strong>{xsd_annotations.get(attr, attr)}:</strong> {value}</p>"
        for child in element:
            html_content += parse_element(child)
        return html_content

    # Добавляем <meta charset="UTF-8"> в <head>
    html_content = """
    <html>
    <head>
        <meta charset="UTF-8">
    </head>
    <body>
    """
    html_content += parse_element(root)
    html_content += "</body></html>"

    return html_content


def convert_xml_to_pdf(xml_path: str, project_path: str, xsd_path: str):
    try:
        temp_dir = create_temp_dir(project_path)
        html_path = os.path.join(temp_dir, "temp.html")
        pdf_path = os.path.join(temp_dir, "output.pdf")

        # Получаем аннотации из XSD схемы
        xsd_annotations = extract_annotations_from_xsd(xsd_path)

        # Определение кодировки XML-файла
        with open(xml_path, "rb") as file:
            raw_data = file.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding']

        # Преобразование XML в HTML с учетом аннотаций из XSD
        html_content = parse_xml_to_html(xml_path, xsd_annotations)

        with open(html_path, "w", encoding=encoding) as file:
            file.write(html_content)

        # Конвертация HTML в PDF
        config = pdfkit.configuration(wkhtmltopdf=get_wkhtmltopdf_path())
        pdfkit.from_file(html_path, pdf_path, configuration=config)

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Файл PDF не был создан: {pdf_path}")

        return pdf_path
    except Exception as e:
        print(f"Ошибка при конвертации XML в PDF: {e}")
        raise
