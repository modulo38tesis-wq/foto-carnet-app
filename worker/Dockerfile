FROM python:3.11-slim

# Dependencias del sistema
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-descargar el modelo de rembg DURANTE el build (para que no se demore en runtime)
RUN mkdir -p /root/.u2net && \
    wget -q -O /root/.u2net/u2net_human_seg.onnx \
    https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx

# Copiar el código y modelos de OpenCV
COPY . .

ENV PORT=10000
EXPOSE 10000

# Timeout más generoso para gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "120", "--workers", "1", "app:app"]
