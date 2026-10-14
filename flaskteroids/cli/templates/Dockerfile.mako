FROM python:3.12-slim AS deps
COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim
ENV FLASK_ENV=production PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY --from=deps /app/.venv /app/.venv
COPY . .
RUN bin/flask assets:precompile
RUN addgroup --system app && adduser --system --ingroup app --home /app --no-create-home app \
    && mkdir -p /app/storage && chown -R app:app /app
USER app
EXPOSE 8000
ENTRYPOINT ["/app/bin/docker-entrypoint"]
CMD ["gunicorn", "wsgi:app", "-b", "0.0.0.0:8000", "--workers", "4"]
