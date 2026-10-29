"""Test package. The environment below must be set before any `app` module is
imported (the settings object is created on first import), so it lives here."""

import os

# Fixed, test-only auth configuration (the app deliberately has no defaults for these).
os.environ.setdefault("MEDNEXA_JWT_SECRET", "test-only-jwt-secret-0123456789abcdef0123456789")
os.environ.setdefault("MEDNEXA_ADMIN_EMAIL", "admin@hospital.com")
os.environ.setdefault("MEDNEXA_ADMIN_PASSWORD", "admin123")
os.environ.setdefault("MEDNEXA_ADMIN_NAME", "Dr. Admin")
os.environ.setdefault("MEDNEXA_SERVICE_API_KEY", "test-only-service-key-0123456789abcdef0123456789")
