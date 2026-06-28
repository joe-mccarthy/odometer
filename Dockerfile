FROM python:3.12-slim

ENV POETRY_VERSION=2.4.1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    ODOMETER_DB_PATH=/data/odometer.db

WORKDIR /app

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock README.md LICENSE ./
COPY odometer ./odometer

RUN poetry install --only main

VOLUME ["/data"]

ENTRYPOINT ["odometer"]
CMD ["--help"]
