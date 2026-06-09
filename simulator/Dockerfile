FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir prometheus_client==0.22.1

COPY app.py /app/app.py

EXPOSE 9000

CMD ["python", "/app/app.py"]
