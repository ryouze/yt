# - https://docs.streamlit.io/deploy/tutorials/docker
# - https://docs.docker.com/guides/python/

# TODO(ryouze): Add caching and reduce image size

FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

WORKDIR /app
COPY . .

# Install production dependencies from `uv.lock` (fail if inconsistent with `pyproject.toml`), excluding the default `test` and `development` groups
RUN uv sync --locked --no-default-groups

EXPOSE 8501

# Start Streamlit directly from the virtual environment created by uv
ENTRYPOINT ["/app/.venv/bin/streamlit", "run", "src/yt/streamlit_app.py", "--server.headless=true", "--server.address=0.0.0.0", "--server.port=8501", "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
