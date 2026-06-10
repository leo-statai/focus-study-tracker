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

**Focus Study Tracker** is a local web application for logging study time toward personal goals — an exam, a certification, a dream. It is designed to run on a home server, laptop, or workstation, accessible via browser on the same machine or from other devices on the local network.

Each user signs in with email and password and can keep **multiple study projects** (e.g. one per exam), each with its own subjects, goals, and history.

With it you can track:

- daily study time and progress against a daily goal;
- progress against each project's total goal;
- time distribution across subjects;
- reports by day, week, month, and total;
- as many projects as you need, fully independent from each other.

## Features

| Area | What it offers |
| --- | --- |
| Accounts | Email + password sign-up and login (sessions via secure cookie) |
| Projects | Multiple projects per user; create, switch, and delete |
| Timer | Start, pause, and switch subjects during a session |
| Subjects | Create, edit, colour-tag, enable, disable, and delete (per project) |
| Goals | Daily goal (hours) and total goal per project |
| Reports | Period summaries, charts, and per-subject share |
| Persistence | SQLite database at `data/estudos.sqlite` |
| Resilience | Automatic checkpoints cap data loss to 5 minutes on a crash |
| Local deploy | Docker Compose (recommended) or plain Python |

## UI map

```txt
Landing (public)           App (after login)
├── Sign in / Sign up      ├── Project selector (+ new project)
└── Product overview       ├── Daily goal gauge
                           ├── Timer (subject / start / pause)
                           ├── Reports (day · week · month · total)
                           └── Settings (project, goals, subjects)
```

## Technologies

- **Python 3.13** — HTTP server, JSON API, and auth (stdlib only, zero dependencies)
- **SQLite** — users, projects, subjects, and session storage
- **HTML, CSS, JavaScript** — frontend, no framework, no build step
- **Docker Compose** — recommended way to run

## Project structure

```txt
.
├── app.py                 # Server, API, auth, and SQLite layer (single file)
├── static/
│   ├── landing.html       # Public landing page with login/sign-up (self-contained)
│   ├── index.html         # Main app UI (requires login)
│   ├── app.js             # App frontend logic
│   ├── styles.css         # App styles
│   └── favicon.svg        # Project icon
├── data/                  # Local database (gitignored)
├── Dockerfile
├── docker-compose.yml
├── GUIA_INSTALACAO.md     # Install guide (PT-BR)
├── GUIA_UTILIZACAO.md     # Usage guide (PT-BR)
└── README.md
```

## Installation

### Docker Compose (recommended)

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

The container restarts automatically (`restart: unless-stopped`) and ships a healthcheck, so `docker ps` shows whether the app is actually responding. Logs are available with:

```bash
docker logs -f contador-estudos
```

To stop:

```bash
docker compose down
```

### Python directly (development)

```bash
python3 app.py
```

Open `http://localhost:8000`. No dependencies to install.

## How to use

1. Open the app and create your account (email + password).
2. A first project is created for you — open settings to rename it and set your daily and total goals.
3. Register your subjects (with colours).
4. Select a subject, hit start, and study.
5. Use the project selector in the top bar to create or switch between projects ("+ Novo projeto…").

When you pause, the session is saved and all reports update. Switching projects pauses any running timer.

## Backup

Data lives in:

```txt
data/estudos.sqlite
```

This same file is used whether you run via Docker (mounted at `/data`) or plain Python. To back it up, stop the app and copy the file:

```bash
mkdir -p backups
cp data/estudos.sqlite backups/estudos-$(date +%F).sqlite
```

## Updating

After changing project files, rebuild and restart:

```bash
docker compose up -d --build
```

## Notes

- Designed for local or home-network use; it serves plain HTTP, so don't expose it directly to the internet without a reverse proxy with TLS.
- Passwords are stored as PBKDF2-SHA256 hashes; sessions use HttpOnly cookies.
- The `data/` folder is gitignored to protect personal study records.
- Detailed usage: see [GUIA_UTILIZACAO.md](GUIA_UTILIZACAO.md) (PT-BR).
- Step-by-step install: see [GUIA_INSTALACAO.md](GUIA_INSTALACAO.md) (PT-BR).

---

<p align="center">
  Turn daily consistency into achievement.
</p>
