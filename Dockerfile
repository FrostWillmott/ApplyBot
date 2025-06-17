# ---- Builder (runtime only) ----
FROM python:3.11-slim AS builder
WORKDIR /app

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

# ---- Final (prod image) ----
FROM builder AS final
WORKDIR /app

# copy only your installed runtime deps
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/

# copy app code + entrypoint.sh
COPY . .
COPY app/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]
