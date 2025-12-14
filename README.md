# Skilltree (Graph + DAG)

A small full-stack project: Postgres + FastAPI backend + Next.js frontend, containerized with Docker Compose.

## Requirements

- Docker + Docker Compose plugin (`docker compose`)
- GNU Make (for the `make …` commands)

## Repo layout

```
.
├─ backend/              # FastAPI app
├─ frontend/             # Next.js app
├─ docker-compose.yml    # base (prod-ish) compose
├─ docker-compose.dev.yml# dev overrides (bind mounts, reload, etc.)
└─ Makefile
```

## Quick start (development)

Start the full dev stack (frontend + backend + db):

```bash
make dev
```

Open:
- Frontend: http://localhost:3000
- Backend:  http://localhost:8000
- Postgres: localhost:5432

Stop everything:

```bash
make down
```

Follow logs:

```bash
make logs
```

Reset everything (including deleting the DB volume):

```bash
make clean
```

List available make commands

```bash
make help
```

## Compose layering

The dev command uses two compose files:

- `docker-compose.yml` contains the baseline services (how the app runs “normally”).
- `docker-compose.dev.yml` overrides dev-only bits (bind mounts, hot reload, etc).

Docker Compose merges them in order; later files override earlier ones.

## Environment notes

### Backend
- The backend expects a `DATABASE_URL` (set via compose in dev).
- CORS must allow the frontend origin (`http://localhost:3000`) for browser requests.

### Frontend
- Browser API calls must use a host-reachable URL (typically `http://localhost:8000`), not the Docker service name.

## Troubleshooting

### Frontend loads but API calls fail with NetworkError / CORS
Check backend CORS config. The backend must return:

`Access-Control-Allow-Origin: http://localhost:3000`

### `localhost:3000` resets / refuses connections
If containers look healthy, check VPN/firewall rules. VPN clients often break Docker published ports. Disable VPN or allow LAN/Docker subnets.

## Useful commands

Build images:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml build
```

Start without rebuilding:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Stop and remove containers:

```bash
docker compose down
```
