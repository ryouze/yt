# We stick to good old pip instead of uv, following the Streamlit docs
# - https://docs.streamlit.io/deploy/tutorials/docker
# - https://docs.docker.com/guides/python/

# TODO(ryouze): Add caching and reduce image size

FROM python:3.14-slim

ENV PIP_UPLOADED_PRIOR_TO=P3D

WORKDIR /app
COPY . .

RUN pip3 install .

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "app.py", "--server.headless=true", "--server.address=0.0.0.0", "--server.port=8501", "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
