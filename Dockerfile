FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV FLET_FORCE_WEB_SERVER=true
ENV FLET_SERVER_IP=0.0.0.0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "FLET_SERVER_PORT=${PORT:-8000} python main-DESKTOP-3SJ00FD.py"]
