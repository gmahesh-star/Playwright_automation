# Playwright Automation Platform

A web-based test recording, code generation, and execution platform built with Python, FastAPI, and Playwright.

## Project Structure

- `app/` — FastAPI backend, API routes (`recorder`, `runs`, `tests`), database models, and background workers.
- `frontend/` — Web UI (`HTML`, `CSS`, `JS`) for managing and triggering test runs.
- `Dockerfile` & `docker-compose.yml` — Containerized deployment configuration.
- `requirements.txt` — Python dependencies.

## Quick Start

### Option 1: Docker Compose (Recommended)
```bash
docker-compose up --build
```

### Option 2: Local Setup
1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. **Install dependencies and Playwright browsers:**
   ```bash
   pip install -r requirements.txt
   playwright install --with-deps
   ```
3. **Start the application:**
   ```bash
   uvicorn app.main:app --reload
   ```
