FROM python:3.13-slim

WORKDIR /app
COPY app.py /app/app.py
COPY static /app/static

ENV APP_DATA_DIR=/data
ENV HOST=0.0.0.0
ENV PORT=8000

VOLUME ["/data"]
EXPOSE 8000

CMD ["python", "app.py"]
