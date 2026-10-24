# Usar una versión ligera de Python
FROM python:3.10-slim

# Crear una carpeta de trabajo dentro del servidor
WORKDIR /app

# Copiar la lista de librerías e instalarlas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo tu código y carpetas (HTML, img, static, app.py)
COPY . .

# Abrir el puerto 5000 (el predeterminado de Flask)
EXPOSE 5000

# Comando para encender tu aplicación
CMD ["python", "app.py"]