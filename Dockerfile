FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    libfontconfig1 \
    libxrender1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY . /app

# Копируем файл зависимостей и устанавливаем Python-зависимости
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Открываем порт, на котором будет работать FastAPI
EXPOSE 8000

# Запуск приложения
CMD ["uvicorn", "app.main_app:app", "--host", "0.0.0.0", "--port", "8000"]
