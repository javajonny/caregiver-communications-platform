# Caregiver Communications Platform

This repository is published with a clean Git history. It contains the current project files only, starting from the initial commit. Earlier commits, messages, and file versions are intentionally not included, so the public history matches the released code and the license terms in `LICENSE` and `LICENSE.pdf`.

This repository contains a FastAPI server, a Postgres database, a management/upload portal for management and the app for the Caregiver Communications Platform. The stack is containerized with Docker and can be run locally with HTTPS enabled using your existing self-signed certificate and key.



## License

The full terms are in `LICENSE` and `LICENSE.pdf`.

## Prerequisites

- Docker Desktop 4.x+
- macOS zsh shell (commands below are copy-paste ready)

## Quick start (Docker)

1) Configure database credentials

The compose stack uses a `.env` file at the repo root:

```
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
BACKUP_ENCRYPTION_KEY=
```

2) Generate self-signed certificate (one-time setup)

For iOS Simulator testing (localhost only):
```bash
openssl req -x509 -newkey rsa:4096 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost"
```

For physical iPhone testing (localhost + your Mac's IP):
```bash
# First, get your Mac's current local IP
ipconfig getifaddr en0

# Then generate certificate with both localhost and your IP
openssl req -x509 -newkey rsa:4096 -nodes -keyout key.pem -out cert.pem -days 365 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:127.0.0.1,IP:YOUR_IP_HERE"

# Example with IP 192.168.1.100:
# openssl req -x509 -newkey rsa:4096 -nodes -keyout key.pem -out cert.pem -days 365 \
#   -subj "/CN=localhost" \
#   -addext "subjectAltName=DNS:localhost,DNS:127.0.0.1,IP:192.168.1.100"
```

**Note:** If your Mac's IP changes (common with DHCP), you'll need to:
1. Regenerate the certificate (see above).
2. Update the IP address in `app/CaregiverApp/CaregiverApp/Services/AuthService.swift`:
   ```swift
   static func localIP() -> String {
       return "YOUR_NEW_IP" 
   }
   ```
   You can find your new IP by running `ipconfig getifaddr en0`.

3) Build and start containers

This brings up Postgres and the FastAPI server. The server runs with HTTPS on port 8443 using `server/cert.pem` and `server/key.pem`.


```sh
docker compose up -d --build
```

4) Initialize the database schema (idempotent)

On the first boot, Postgres automatically applies `database/schema.sql`. You can also run the init script manually (safe to re-run—it will skip if applied):

```sh
chmod +x scripts/init_db.sh
./scripts/init_db.sh
```

5) Verify the server over HTTPS

- Browser: https://localhost:8443/
- curl (self-signed cert):

```sh
curl -k https://localhost:8443/
```

You should see:

```
{"message":"Welcome to the Caregiver Communications Platform Server"}
```

## Authentication & Mock Data

### Development Login Credentials

Sample staff accounts are not included in this repository. Local credentials, if you create them yourself, can be kept in `database/mock_data.txt`, which is gitignored.

### Security Features

- **Password hashing**: Bcrypt with 12 rounds (no plaintext passwords stored)
- **Session management**: Server-side tokens with SHA-256 hashing
- **HIPAA-compliant timeouts**:
  - Idle timeout: 15 minutes (configurable via `SESSION_IDLE_TIMEOUT_MINUTES`)
  - Absolute session TTL: 12 hours (configurable via `SESSION_ABSOLUTE_TTL_MINUTES`)
- **TLS/HTTPS**: Required for all authentication endpoints

### Authentication Endpoints

- `POST /auth/login` — Returns bearer token and timeout metadata
- `POST /auth/logout` — Invalidates current session
- `GET /auth/me` — Returns authenticated user info

**All other API endpoints require authentication.** Include the bearer token in the `Authorization` header:
```
Authorization: Bearer <token>
```

Example with curl:
```sh
# Login
TOKEN=$(curl -sk https://localhost:8443/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"daniel.davidson@aco.com","password":"XXXXXXX!"}' \
  | jq -r '.access_token')

# Use token for protected endpoints
curl -k https://localhost:8443/staff \
  -H "Authorization: Bearer $TOKEN"
```

### Role-Based Authorization (RBAC)

Role-based access control is fully implemented. Endpoints are protected based on user roles:

- **Admin**: Full access to all resources (staff management, system configuration)
- **Director**: Access to all locations and clients (excludes admin-only operations)
- **Site Director**: Scoped access to their assigned location only
- **DSP (Caregiver)**: Access limited to active shift data and assigned clients

See `docs/RBAC_PERMISSIONS.md` for the complete permissions matrix and `server/authorization.py` for implementation details.

## Backup & Recovery

The stack includes a dedicated backup service that runs daily at 2 AM.

### Automatic Backups
- **Schedule**: Daily at 02:00 (Timezone: America/New_York)
- **Encryption**: Backups are gzipped and encrypted using AES-256-CBC with the `BACKUP_ENCRYPTION_KEY`.
- **Retention**: Backups older than 6 years are automatically deleted (HIPAA compliance).
- **Location**: Stored in the `backups/` directory (git-ignored).

### Restoring a Backup
To restore the database from an encrypted backup file, use the provided script:

```sh
./scripts/restore_backup.sh backups/backup_YYYYMMDD_HHMMSS.sql.gz.enc
```

**Note**: This will drop the current database and replace it with the backup content.

## How it works

- Postgres 16 runs with a persistent volume and a healthcheck. The schema is auto-applied from `database/schema.sql` on first initialization via Docker’s `docker-entrypoint-initdb.d` mechanism. The same schema is also mounted at `/schema/schema.sql` for manual application by the init script.
- The FastAPI server builds from `server/` and is started by compose with Uvicorn using TLS on port 8443, mounting `server/cert.pem` and `server/key.pem` read-only into the container.
- The `server/` directory is bind-mounted to enable `--reload` in the container for a good dev experience.

## Common commands

- View logs
```
docker compose logs -f
```

```sh
docker compose logs -f server
docker compose logs -f db
```

- Access the database for testing

```sh
docker compose exec db psql -U POSTGRES_USER -d POSTGRES_DB
```

Example queries:
```sql
-- View all task statuses for a shift
SELECT * FROM shift_task_status;

-- View task status history (audit trail)
SELECT * FROM shift_task_status_history;

-- View all tasks
SELECT * FROM tasks;

-- View task status types
SELECT * FROM task_status_types;

-- View shifts
SELECT * FROM shifts;
```

- Stop the stack

```sh
docker compose down
```

- Reset database (CAUTION: deletes data)

```sh
docker compose down -v
docker compose up -d --build
./scripts/init_db.sh
```

## Changing HTTPS behavior

The compose file starts Uvicorn with:

```
--port 8443 --ssl-keyfile /certs/key.pem --ssl-certfile /certs/cert.pem --reload
```

If you prefer to run HTTP-only inside containers (e.g., use a reverse proxy for TLS), remove the SSL flags and port mapping changes from `docker-compose.yml` and map `8000:8000` instead. You can also remove the `./server:/app` bind mount and `--reload` for a leaner production image.

### Frontend HTTPS (Development)

The management portal (Vite/React) is configured to run with HTTPS using the same certificates as the backend. This ensures end-to-end encryption during local development.

**URLs:**
- Backend API: `https://localhost:8443`
- Frontend (Docker): `https://localhost:3000`
- Frontend (Local Dev): `https://localhost:5173`

The frontend uses the certificates from `server/key.pem` and `server/cert.pem` (configured in `portal/caregiver-mgmt-portal/vite.config.ts`).

To start the frontend with HTTPS:
```bash
cd portal/caregiver-mgmt-portal
npm run dev
```

**Note:** Since both services use the same self-signed certificate for `localhost`, you may see browser warnings. Click "Advanced" → "Proceed" to continue, or trust the certificate in your system keychain for a smoother experience.


## Project structure (key paths)

- `docker-compose.yml` — container definitions for DB and server
- `database/schema.sql` — full database schema
- `backups/` — storage for encrypted database backups
- `scripts/init_db.sh` — waits for DB, applies schema if needed
- `scripts/restore_backup.sh` — restores DB from encrypted backup
- `server/` — FastAPI app source, certs, and Dockerfile
	- `main.py` — app entrypoint
	- `Dockerfile` — server image build
	- `requirements.txt` — Python dependencies
	- `cert.pem`, `key.pem` — self-signed cert and key used in dev
- `portal/caregiver-mgmt-portal/` — React/Vite management portal
- `app/CaregiverApp/` — iOS mobile application source

## Troubleshooting

- SSL warnings in browser
	- Self-signed certificates will show a security warning. Proceed to continue in development. For production, terminate TLS with a trusted certificate at a reverse proxy (nginx/Traefik/Caddy).

- Schema didn’t apply on first run
	- Ensure `database/schema.sql` exists and re-create the DB volume:

```sh
docker compose down -v
docker compose up -d
./scripts/init_db.sh
```

- Port already in use
	- If 8443 or 5432 are occupied, update the host-side port mappings in `docker-compose.yml` accordingly.

