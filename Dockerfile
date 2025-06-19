# ---- Builder (runtime only) ----
FROM python:3.11-slim AS builder
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# install Poetry + export plugin
RUN pip install poetry \
 && poetry self add poetry-plugin-export

COPY pyproject.toml poetry.lock ./

# export runtime deps only
RUN poetry export \
      --format=requirements.txt \
      --without-hashes \
      -o requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

# ---- Dev-builder (adds dev tools) ----
FROM builder AS dev-builder

# export including dev group
RUN poetry export \
      --format=requirements.txt \
      --without-hashes \
      --with dev \
      -o requirements-dev.txt

RUN pip install --no-cache-dir -r requirements-dev.txt

# ---- Dev-final (development image) ----
FROM dev-builder AS dev-final
WORKDIR /app

# Install netcat for health checks
RUN apt-get update && apt-get install -y \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# copy installed dev deps
COPY --from=dev-builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/

# Copy entrypoint script from root and set permissions
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# copy app code
COPY . .

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "80"]

# ---- Final (prod image) ----
FROM builder AS final
WORKDIR /app

# Install netcat for health checks
RUN apt-get update && apt-get install -y \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# copy only your installed runtime deps
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/

# Copy entrypoint script from root and set permissions
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# copy app code
COPY . .

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]