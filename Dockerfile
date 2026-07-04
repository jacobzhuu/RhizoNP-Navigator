FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /app

RUN python -m pip install --upgrade pip

COPY requirements.txt pyproject.toml README.md ./
RUN python -m pip install -r requirements.txt \
    && python -m pip install pytest ruff mypy

COPY . .

CMD ["python", "-m", "pytest"]
