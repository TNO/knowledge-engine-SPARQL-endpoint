FROM python:3.11.4-alpine

# Create and enable venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip

RUN pip install wheel

WORKDIR /app/

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY ./app.py .

ENTRYPOINT [ "uvicorn", "app:app", "--host", "0.0.0.0" ]
