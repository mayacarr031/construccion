# ── Dockerfile ────────────────────────────────────────────
# FastAPI + LM Studio + XAMPP (MySQL externo vía host.docker.internal)
# ──────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copiar solo los archivos necesarios primero (para aprovechar la caché de capas)
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . .

# Puerto en el que escucha uvicorn
EXPOSE 8000

# Arrancar FastAPI con uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
