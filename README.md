# Cowrite

---

## Description

A real-time collaborative text editor built with FastAPI, WebSockets, and Redis, allowing multiple users to edit the same document simultaneously while staying synchronized with live presence and typing indicators.

---

## Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-2C3E50?style=for-the-badge&logo=pydantic&logoColor=white)
![Postgres](https://img.shields.io/badge/Postgres-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-FF6600?style=for-the-badge&logo=rabbitmq&logoColor=white)
![Sentry](https://img.shields.io/badge/Sentry-362D59?style=for-the-badge&logo=sentry&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Resend](https://img.shields.io/badge/Resend-FF5A5F?style=for-the-badge&logo=resend&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

---

## Core Features

- Real-time collaborative editing
- Live user presence
- Typing indicators
- Automatic synchronization of document changes
- Redis-powered pub/sub for low-latency updates
- WebSocket-based communication

---

### Concepts Covered
- Real-time event broadcasting: Events are published to all users in a room and requires no polling.
- Pub/Sub Systems: A redis pub/sub channel is used as the medium for event publishing. This solves the multi-instance limitations by ensuring all users in a room have access to events irrespective of the instance connected to.
- Presence and Typing indicators: Broadcast presence and typing events in real-time.
- Event Ordering: Operation events are assigned a number to maintain sequential order.
- Operational Transformation: Applied to preserve all modifications from conflicting operations by merging writes from multiple users.

---

## Prerequisites

Before running Notix locally, make sure you have:
- Python 3.12 or newer
- Docker and Docker Compose
- uv (recommended for dependency management)
- access to a PostgreSQL instance, Redis, RabbitMQ, and Resend credentials

---

## Installation

### Running With Docker Compose

The repository includes a full local stack for the API, worker, PostgreSQL, Redis, and RabbitMQ.

### Start all services

```bash
docker compose up --build
```

This will launch:
- PostgreSQL for app data
- PostgreSQL for test data
- Redis
- RabbitMQ management UI at http://localhost:15672
- API server at http://localhost:8000
- Celery worker

### Stop services

```bash
docker compose down
```

---

## Running Locally Without Docker

### 1. Clone the repository and switch to directory

```bash
git clone https://github.com/<your-username>/cowrite.git

cd cowrite
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Environment Configuration

```bash
cp .env.example .env
```

### 4. Apply database migrations

```bash
uv run alembic upgrade head
```

### 5. Start the application

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## WebSocket Usage

### Testing with Postman

Postman can be used to test the WebSocket endpoint.

- Open Postman.
- Create a new WebSocket Request.
- Connect to the application's WebSocket URL.
- Once connected, clients exchange JSON messages over the WebSocket.

Example:

ws://localhost:8000/api/v1/ws/?token={bearer_token}

After connecting:

- Send a ping message every 10 seconds to remain connected.
- Send typing events while testing.
- Send document editing events to verify synchronization.
- Observe broadcasts from other connected clients.

---

## Presence (Important)

Every connected client must send a ping event every 10 seconds. The server refreshes the user's Redis presence key whenever a ping is received.

If the client stops sending pings:

- The Redis presence key expires.
- The user is considered offline.
- The server removes the user from the room.

Example:

{
  "event": "ping",
  "doc_id": "abc"
}

It is recommended to implement this as a repeating timer on the client that sends a ping every 10 seconds for the lifetime of the connection.

---

## Typing Events

Cowrite uses typing events to provide live typing indicators. Every keystroke should send a typing event.

Example:

{
  "event": "typing",
  "doc_id": "abc"
}

Clients do not need to manually send a typing stopped event. When no typing event has been received for 3 seconds, the server automatically broadcasts that the user has stopped typing.

---

## Testing

Run the test suite with:

```bash
uv run pytest
```

Run in verbose mode:

```bash
uv run pytest -v
```