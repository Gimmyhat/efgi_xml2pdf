FROM python:3.11-slim

# Установка необходимых пакетов и шрифтов
RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    libfontconfig1 \
    libxrender1 \
    fonts-dejavu-core \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Обновление кэша шрифтов
RUN fc-cache -fv

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY . /app

# Копируем файл зависимостей и устанавливаем Python-зависимости
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Открываем порт для FastAPI
EXPOSE 8000

# Запуск приложения
CMD ["uvicorn", "app.main_app:app", "--host", "0.0.0.0", "--port", "8000"]
