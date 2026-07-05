FROM python:3.10-slim AS api-base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /app

RUN python -m pip install --upgrade pip

COPY requirements.txt pyproject.toml README.md ./
RUN python -m pip install -r requirements.txt \
    && python -m pip install pytest ruff mypy uvicorn

COPY . .

FROM api-base AS api
EXPOSE 8000
CMD ["uvicorn", "rhizonp.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src"]

FROM api-base AS test
CMD ["python", "-m", "pytest"]

FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
ENV VITE_API_BASE_URL=
RUN npm run build

FROM nginx:1.27-alpine AS frontend
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
