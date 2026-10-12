# Static exhibition build: Python is needed only when producing the snapshot.
FROM python:3.12-slim AS snapshot
WORKDIR /app
COPY requirements-demo.txt ./
RUN pip install --no-cache-dir -r requirements-demo.txt
COPY sleeve_checker/ ./sleeve_checker/
COPY scripts/export_demo.py ./scripts/export_demo.py
COPY dxf_output/ ./dxf_output/
RUN python scripts/export_demo.py

FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY --from=snapshot /app/frontend/public/demo ./public/demo
RUN npx tsc -b && npx vite build && node scripts/build-offline.mjs

FROM nginx:alpine
COPY deploy/demo.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend /app/frontend/dist /usr/share/nginx/html
EXPOSE 10000
