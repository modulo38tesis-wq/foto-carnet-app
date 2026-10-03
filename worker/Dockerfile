FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para OpenCV y rembg
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código y modelos
COPY . .

# Puerto que usará Render
ENV PORT=10000
EXPOSE 10000

# Comando de inicio (lo cambiaremos cuando tengamos el API)
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
