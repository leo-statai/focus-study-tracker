# Focus Study Tracker

<p align="center">
  <img src="static/favicon.svg" alt="Focus Study Tracker" width="92" height="92">
</p>

<h3 align="center">Self-hosted study time tracker — Python stdlib + SQLite, browser-based, LAN-accessible.</h3>

<p align="center">
  <a href="#overview">Overview</a> ·
  <a href="#features">Features</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#backup">Backup</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-local-003B57?style=for-the-badge&logo=sqlite&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?style=for-the-badge&logo=docker&logoColor=white">
</p>

---

## Overview

**Focus Study Tracker** is a local web application for logging study time in a simple, visual, and persistent way. It is designed to run on a home server, laptop, or workstation — accessible via browser on the same machine or from other devices on the local network.

With it you can track:

- daily study time;
- progress against a daily goal;
- progress against the project's total goal;
- time distribution across subjects;
- reports by day, week, month, and total;
- sessions stored in a local SQLite database.

## Features

| Area | What it offers |
| --- | --- |
| Timer | Start, pause, and switch subjects during a session |
| Subjects | Create, edit, colour-tag, enable, disable, and delete |
| Goals | Daily goal (hours) and total project goal |
| Reports | Period summaries, charts, and per-subject share |
| Persistence | SQLite database at `data/estudos.sqlite` |
| Local deploy | Run directly with Python or via Docker Compose |

## UI map

```txt
Project
├── Daily goal
│   └── today's progress
├── Timer
│   ├── current subject
│   └── start / pause
├── Reports
│   ├── day
│   ├── week
│   ├── month
│   └── total
└── Settings
    ├── project
    ├── goals
    └── subjects
```

## Technologies

- **Python 3.13** — HTTP server and local API (stdlib only)
- **SQLite** — session storage
- **HTML, CSS, JavaScript** — frontend
- **Docker Compose** — isolated execution
- No mandatory external Python dependencies when running directly with Python

## Project structure

```txt
.
├── app.py                 # Server, API, and SQLite layer
├── static/
│   ├── index.html         # Main UI
│   ├── styles.css         # Styles
│   ├── app.js             # Frontend logic
│   └── favicon.svg        # Project icon
├── data/                  # Local database (gitignored)
├── Dockerfile
├── docker-compose.yml
├── GUIA_INSTALACAO.md     # Install guide (PT-BR)
├── GUIA_UTILIZACAO.md     # Usage guide (PT-BR)
└── README.md
```

## Installation

### Option 1 — Docker Compose

Recommended for keeping the app running in isolation.

```bash
docker compose up -d --build
```

Open in your browser:

```txt
http://localhost:8000
```

From another device on the same network, use the host machine's IP:

```txt
http://SERVER_IP:8000
```

To stop:

```bash
docker compose down
```

### Option 2 — Python directly

Good for development and quick tests.

```bash
python3 app.py
```

Open:

```txt
http://localhost:8000
```

## How to use

1. Open the app in your browser.
2. Go to settings.
3. Set the project name.
4. Configure daily and total goals.
5. Register your subjects.
6. Select a subject.
7. Click start and study with the timer running.

When you pause, the session is saved to the local database and reports update.

## Backup

Data lives in:

```txt
data/estudos.sqlite
```

Before resetting the app or moving the install to another machine, stop the app and copy that file:

```bash
mkdir -p backups
cp data/estudos.sqlite backups/estudos-$(date +%F).sqlite
```

## Updating

After changing project files, restart the app.

With Docker:

```bash
docker compose up -d --build
```

With Python directly:

```bash
python3 app.py
```

## Notes

- Designed for local or home-network use.
- The SQLite database is not committed to GitHub.
- The `data/` folder is gitignored to protect personal study records.
- Detailed usage: see [GUIA_UTILIZACAO.md](GUIA_UTILIZACAO.md) (PT-BR).
- Step-by-step install: see [GUIA_INSTALACAO.md](GUIA_INSTALACAO.md) (PT-BR).

---

<p align="center">
  Turn scattered study hours into visible progress.
</p>
