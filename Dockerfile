# builder stage
FROM python:3.13-slim AS builder
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv venv .venv && uv lock && uv sync
COPY . .

# Make sure the venv’s bin/ is first on PATH
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Expose your app’s port and set the default command
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
