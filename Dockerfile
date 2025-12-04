# ---- Builder (runtime dependencies) ----
FROM python:3.14-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry \
    && poetry self add poetry-plugin-export

COPY pyproject.toml poetry.lock ./

RUN poetry export \
    --format=requirements.txt \
    --without-hashes \
    -o requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

# ---- Dev final (development image with dev tools) ----
FROM builder AS dev-final
WORKDIR /app

RUN apt-get update && apt-get install -y \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Export and install dev dependencies
RUN poetry export \
    --format=requirements.txt \
    --without-hashes \
    --with dev \
    -o requirements-dev.txt \
    && pip install --no-cache-dir -r requirements-dev.txt

COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

COPY . .

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "80"]

