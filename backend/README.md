# People Remotely — Backend Foundation

This directory contains the Python/Django REST Framework backend for People Remotely, designed to replace Next.js server-side code and Supabase backend services while keeping the existing Next.js 16 App Router frontend intact.

---

## Technical Stack & Versions

- **Python**: `3.14.7` (Compatible with Django 5.2 LTS)
- **Django**: `5.2.17`
- **Django REST Framework**: `3.18.0`
- **Authentication**: `djangorestframework-simplejwt` (5.5.1)
- **Database**: PostgreSQL (`psycopg` 3.3.5) / local SQLite for unit tests
- **Task Queue**: Celery (`5.6.3`) + Redis (`8.1.0`)
- **Cloud Storage**: `django-storages` (`1.14.6`) + `boto3` (`1.43.85`)
- **CORS**: `django-cors-headers` (`4.9.0`)

---

## Local Setup & Development

### 1. Create and activate Python virtual environment

```bash
cd backend
python -m venv venv
# On Windows Command Prompt:
venv\Scripts\activate
# On Linux / macOS:
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Adjust variables as needed (e.g., local PostgreSQL connection string, Redis URL).

### 4. Run database migrations

```bash
python manage.py migrate
```

### 5. Run automated tests

```bash
python manage.py test
```

### 6. Run development server

```bash
python manage.py runserver 8000
```

The health check endpoint will be available at: [http://localhost:8000/api/v1/health/](http://localhost:8000/api/v1/health/)

### 7. Run Celery worker (optional for async tasks)

```bash
celery -A config worker --loglevel=info
```

---

## Key Endpoints Foundation

- `GET /api/v1/health/` — Health check endpoint (`{"status": "ok"}`)
- `POST /api/v1/auth/login/` — SimpleJWT Token Obtain Pair endpoint
- `POST /api/v1/auth/refresh/` — SimpleJWT Token Refresh endpoint
