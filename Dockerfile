# --- Stage 1: Build frontend ---
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python backend ---
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY sleeve_checker/ ./sleeve_checker/
COPY api.py ./
COPY dxf_output/ ./dxf_output/

# Copy frontend build output
COPY --from=frontend-build /app/frontend/dist ./static

EXPOSE 10000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "10000"]
