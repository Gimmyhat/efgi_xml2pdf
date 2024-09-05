# Используем multi-stage сборку
FROM python:3.11-slim AS builder

# Устанавливаем переменную окружения для избежания интерактивных запросов
ENV DEBIAN_FRONTEND=noninteractive

# Установка необходимых пакетов и зависимостей для КриптоПро CSP и WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    expect \
    libfontconfig1 \
    libxrender1 \
    libpango1.0-0 \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Копируем архив КриптоПро CSP в контейнер и устанавливаем его
COPY linux-amd64_deb.tgz /tmp/
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

# Устанавливаем Python-зависимости
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt

# Второй этап: финальный образ
FROM python:3.11-slim

# Копируем установленные пакеты и зависимости из builder
COPY --from=builder /usr/local /usr/local
COPY --from=builder /opt/cprocsp /opt/cprocsp
COPY --from=builder /var/opt/cprocsp /var/opt/cprocsp
COPY --from=builder /etc/opt/cprocsp /etc/opt/cprocsp

# Устанавливаем необходимые библиотеки и зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfontconfig1 \
    libxrender1 \
    libpango1.0-0 \
    libcairo2 \
    expect \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY . /app

# Устанавливаем путь к csptest
ENV PATH="/opt/cprocsp/bin/amd64:${PATH}"

# Открываем порт для FastAPI
EXPOSE 8000

# Запуск приложения
CMD ["uvicorn", "app.main_app:app", "--host", "0.0.0.0", "--port", "8000"]