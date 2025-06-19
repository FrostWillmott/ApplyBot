# ---- Base Builder ----
FROM python:3.11-slim AS base-builder
WORKDIR /app

# Install Poetry + export plugin
RUN pip install poetry \
 && poetry self add poetry-plugin-export

COPY pyproject.toml poetry.lock ./

# ---- Production Builder ----
FROM base-builder AS prod-builder

# Export runtime deps only
RUN poetry export \
      --format=requirements.txt \
      --without-hashes \
      -o requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

# ---- Development Builder ----
FROM base-builder AS dev-builder

# Export including dev group
RUN poetry export \
      --format=requirements.txt \
      --without-hashes \
      --with dev \
      -o requirements-dev.txt

RUN pip install --no-cache-dir -r requirements-dev.txt

# ---- Production Final ----
FROM python:3.11-slim AS final
WORKDIR /app

# Copy only production dependencies
COPY --from=prod-builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=prod-builder /usr/local/bin/ /usr/local/bin/

# Copy app code
COPY . .
COPY app/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]

# ---- Development Final ----
FROM python:3.11-slim AS dev-final
WORKDIR /app

# Copy dev dependencies (includes alembic)
COPY --from=dev-builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=dev-builder /usr/local/bin/ /usr/local/bin/

# Copy app code
COPY . .
COPY app/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "80"]
