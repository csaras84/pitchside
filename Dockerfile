# Pitchside container image (used by Azure Container Apps).
# Build:  docker build -t pitchside .      Run:  docker run -p 8000:8000 --env-file .env pitchside
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PITCHSIDE_WARM_CACHE=1

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src

# Install with the optional Agent Framework engine. If that package cannot be installed,
# fall back to the base app and say so: /health then reports agent_framework_installed=false.
RUN pip install ".[agent]" \
    || (echo "WARNING: agent-framework not installed; building without it" && pip install .)

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 pitchside
USER pitchside

# Secrets are never baked into the image: pass them as environment variables at run time.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn pitchside.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
