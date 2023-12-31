FROM python:3.8

WORKDIR /app

COPY src ./app
COPY requirements.txt /app


RUN pip install -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
