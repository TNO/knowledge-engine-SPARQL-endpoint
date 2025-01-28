FROM python:3.11.4-alpine

# Create and enable venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip

WORKDIR /app/

COPY requirements.txt .
RUN pip install -r requirements.txt

# Put all endpoint code in /app/ directory
COPY --from=src ./*.py .

# Put the test_unit.py in the /app/tests/ directory
RUN mkdir /app/tests
COPY ./test_unit.py /app/tests/.

WORKDIR /app/tests/

ENTRYPOINT [ "python", "test_unit.py" ]
