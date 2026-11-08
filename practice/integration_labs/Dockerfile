FROM python:3.12-slim
WORKDIR /app
RUN python -m pip install --no-cache-dir uv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY practice ./practice
RUN uv sync --locked --group web --no-dev
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "practice.integration_labs.docpilot:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
