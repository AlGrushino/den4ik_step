FROM python:3.10-alpine

WORKDIR /app

COPY req.txt .

RUN pip install --no-cache-dir -r req.txt