import os
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_BASE_URL = BACKEND_URL  # alias used by services/api.py