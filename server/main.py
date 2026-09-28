from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os

# Import all routers
from routers import staff, locations, clients, shifts, other, auth, documents

# Import custom middleware
from middleware import RequestContextMiddleware


load_dotenv()
app = FastAPI(
    title="Caregiver Communications Platform API",
    description="HIPAA-compliant API for caregiver communication and shift management",
    version="1.0.0"
)

# Add request context middleware for audit logging (must be added early)
app.add_middleware(RequestContextMiddleware)

# Restrict to localhost and local network for development
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "localhost",
        "127.0.0.1",
        str(os.getenv("LOCAL_IP")),  #  Mac's local IP for iOS Simulator access
        "*"  # Allow all hosts for development - remove in production
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://localhost:8443",
        "https://127.0.0.1:8443",
        f"https://{os.getenv('LOCAL_IP')}:8443",
        "*"  # Allow all origins for development - remove in production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security headers for HIPAA compliance
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# Create uploads directory if it doesn't exist
staff_uploads_dir = "uploads/staff"
if not os.path.exists(staff_uploads_dir):
    os.makedirs(staff_uploads_dir, exist_ok=True)

clients_uploads_dir = "uploads/clients"
if not os.path.exists(clients_uploads_dir):
    os.makedirs(clients_uploads_dir, exist_ok=True)

# Mount static files for profile images
app.mount("/uploads/staff", StaticFiles(directory=staff_uploads_dir), name="staff_media")
app.mount("/uploads/clients", StaticFiles(directory=clients_uploads_dir), name="clients_media")


# Include all routers
app.include_router(staff.router)
app.include_router(locations.router)
app.include_router(clients.router)
app.include_router(shifts.router)
app.include_router(other.router)
app.include_router(documents.router)
app.include_router(auth.router)


@app.get("/", tags=["Root"])
def read_root():
    return {
        "message": "Welcome to the Caregiver Communications Platform API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
