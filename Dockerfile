FROM python:3.12.9

WORKDIR /app

ENV PORT=8080
EXPOSE $PORT

COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]