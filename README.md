# yt

A self-hosted YouTube subscription manager built with Streamlit, SQLite, and Docker.

This is part of my [home server stack](https://github.com/ryouze/home-server).

## Motivation

I try to avoid Google services, but I still watch YouTube occasionally.

To manage my "subscriptions", I originally wrote [`yt-table`](https://github.com/ryouze/yt-table) in C++. It provides a small CLI and generates a plain HTML table. It works well on a single machine, but accessing the same list from a phone, tablet, or another computer is inconvenient.

Since I already run a Docker-based home server, I built this simple self-hosted CRUD application with Streamlit so that I can manage and access my YouTube subscriptions from any device.

## Installation

### Docker (end users)

> [!NOTE]
> I plan to add GHCR (GitHub Container Registry) support via CI/CD later.

1. Create a directory to store the SQLite database:
   ```sh
   mkdir -p /srv/yt/data
   ```
2. Add this service to your Docker stack:
   ```yaml
   services:
     yt:
       build:
         context: "https://github.com/ryouze/yt.git"
       container_name: "yt"
       user: "1000:1000"
       # For subpaths, consider the following:
       # environment:
       #   STREAMLIT_SERVER_BASE_URL_PATH: /yt
       #
       # And then in Caddyfile:
       # redir /yt /yt/
       # handle /yt/* {
       #     reverse_proxy yt:8501
       # }
       ports:
         - "8501:8501"
       volumes:
         - "/srv/yt/data:/app/data"
       restart: "unless-stopped"
   ```
3. Build and start the container:
   ```sh
   docker compose up -d --build
   ```
4. Open the application in your browser at `http://YOUR_SERVER_IP:8501`.

### Local (developers)

1. Install the project (this includes the `test` and `dev` dependencies):
   ```sh
   uv sync
   ```
2. Start the application:
   ```sh
   streamlit run app.py
   ```
