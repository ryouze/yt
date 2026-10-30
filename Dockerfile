# - https://docs.streamlit.io/deploy/tutorials/docker
# - https://docs.docker.com/guides/python/

# TODO(ryouze): Add caching and reduce image size

FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

WORKDIR /app
COPY . .

# Install production dependencies
# `--locked` = use `uv.lock` and fail if it's inconsistent with `pyproject.toml`
# `--no-default-groups` = exclude the default `test` and `dev` groups initially (we don't want `ruff`)
# `--no-cache` = do not keep cache inside the container after installation
RUN uv sync --locked --no-default-groups --no-cache

EXPOSE 8501

# Run as non-root by default if outside Docker Compose
# Docker Compose's `user` setting overrides the Dockerfile's `USER` instruction
USER 1000:1000

# Start Streamlit directly from the virtual environment created by uv
ENTRYPOINT ["/app/.venv/bin/streamlit", "run", "src/yt/streamlit_app.py", "--server.headless=true", "--server.address=0.0.0.0", "--server.port=8501", "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
