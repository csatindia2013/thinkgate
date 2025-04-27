FROM python:3.11-slim

RUN apt-get update &&     apt-get install -y tesseract-ocr libglib2.0-0 libsm6 libxext6 libxrender-dev gcc ffmpeg &&     pip install --upgrade pip

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 10000
CMD ["python", "app.py"]