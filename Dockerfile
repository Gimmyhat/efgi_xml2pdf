# Используем базовый образ Python 3.11
FROM python:3.11-slim

# Устанавливаем переменную окружения для избежания интерактивных запросов
ENV DEBIAN_FRONTEND=noninteractive

# Установка необходимых пакетов, шрифтов и зависимостей для КриптоПро CSP
RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    libfontconfig1 \
    libxrender1 \
    lsb-release \
    wget \
    ca-certificates \
    expect \
    fontconfig \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем стандартные шрифты
RUN apt-get update && apt-get install -y \
    fonts-roboto \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Обновление кэша шрифтов
RUN fc-cache -fv

# Копируем архив КриптоПро CSP в контейнер
COPY linux-amd64_deb.tgz /tmp/linux-amd64_deb.tgz

# Устанавливаем КриптоПро CSP
RUN tar -xzvf /tmp/linux-amd64_deb.tgz -C /tmp \
    && cd /tmp/linux-amd64_deb \
    && ./install.sh \
    && cd / \
    && rm -rf /tmp/linux-amd64_deb /tmp/linux-amd64_deb.tgz

# Копируем архив сертификата и скрипт в контейнер
COPY app/certs/nedra.pfx /app/nedra.pfx
COPY import_cert.exp /app/import_cert.exp

# Устанавливаем права и запускаем скрипт
RUN chmod +x /app/import_cert.exp && /app/import_cert.exp

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY . /app

# Устанавливаем Python-зависимости
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Устанавливаем путь к csptest
ENV PATH="/opt/cprocsp/bin/amd64:${PATH}"

# Открываем порт для FastAPI
EXPOSE 8000

# Запуск приложения
CMD ["uvicorn", "app.main_app:app", "--host", "0.0.0.0", "--port", "8000"]
