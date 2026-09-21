FROM python:3.11.4-alpine

# Create and enable venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip

RUN pip install wheel

WORKDIR /app/

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY ./ttp.py .
COPY ./tokens_to_requesters.json .

ENTRYPOINT [ "uvicorn", "ttp:app", "--host", "0.0.0.0" ]
