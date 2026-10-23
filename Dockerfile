FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock .
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    pip install --no-cache-dir --require-hashes -r requirements.lock
COPY app ./app
COPY data ./data
RUN useradd --create-home calculator && mkdir -p /app/instance \
    && chown calculator /app/instance && chmod -R a+rX /app/app /app/data
USER calculator
ENV DATABASE_URL=sqlite:////app/instance/eppgg.db
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
