# Caregiver Management Portal

A React-based web portal for the Caregiver Communications Platform. This portal provides management functionality for administrators, directors, and site directors.

> **Note**: DSPs (Direct Support Professionals) cannot access this portal.
## Tech Stack

- **React 19** with TypeScript
- **Vite** for development and building
- **React Router** for navigation
- **CSS** for styling (vanilla CSS, no frameworks)

## Getting Started

### Prerequisites

- Node.js 18+
- The backend server running at `https://localhost:8443`

### Installation

```bash
cd portal/caregiver-mgmt-portal
npm install
```

### Development

```bash
npm run dev
```

The portal runs at `https://localhost:5173` with HTTPS enabled using the same certificates as the backend.

### Production (Docker)

When running via Docker Compose, the portal is served at `https://localhost:3000` via Nginx.

```bash
# From project root
./restart.zsh
```

## Features

### For Administrators
- Staff management (create, update, deactivate)
- Client management (create, update, deactivate)
- Document template builder
- Shift template builder
- Behavior type configuration

### For Directors
- View all locations and clients
- Document template builder
- Shift template builder
- Document review and compliance tracking
- Staff oversight

### For Site Directors
- Location-scoped view of clients and staff
- Shift scheduling and shift template builder for their location
- Document management for enrolled clients

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Overview stats and quick actions |
| `/clients` | Clients | Client list, enrollment, residence, contacts |
| `/staff` | Staff | Staff directory and management |
| `/shifts` | Shifts | Shift scheduling and assignments |
| `/documents` | Documents | Document templates and client documents |

## Project Structure

```
src/
├── components/     # Reusable UI components (forms, modals)
├── pages/          # Page components (Dashboard, Clients, Staff, etc.)
├── contexts/       # React context providers (AuthContext)
├── hooks/          # Custom React hooks (usePermission)
├── types/          # TypeScript type definitions
└── services/       # API service layer
```

## Authentication & Authorization

- **AuthContext** manages login/logout and session state
- **usePermission** hook provides role-based access control
- Protected routes redirect unauthenticated users to `/login`
- DSP users are blocked at login with a clear error message


## HTTPS Configuration

The portal uses the same self-signed certificates as the backend server. Certificates are expected at:
- `../../server/cert.pem`
- `../../server/key.pem`

See the main `README.md` for certificate generation instructions.
