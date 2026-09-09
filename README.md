# Ask My Course

An AI-powered course Q&A assistant (a RAG microservice) for the Eagle LMS.
Students ask questions in plain language and get answers drawn **only** from that
course's uploaded materials, with citations (Unit → Lesson → Page) and a
confidence score. If the answer is not in the materials, it refuses instead of
guessing (the guardrail).

## Architecture

- **Backend**: Django + Django REST Framework, PostgreSQL 18 + pgvector, and
  Google Gemini (free tier) via its OpenAI-compatible API (`gemini-embedding-001`
  at 1536 dims for embeddings, `gemini-3.1-flash-lite` for answers).
- **Frontend**: React + Vite (a Teacher Dashboard and a Student ask page).
- **Pipeline**: PDF → extract text (PyMuPDF) → chunk (~400 words) → embed →
  store vectors → retrieve nearest chunks (HNSW cosine) → generate a grounded
  answer with citations.

```
ask-my-course/
  backend/    Django project (core) + app (courses) + services/ (the RAG pipeline)
  frontend/   React + Vite app
```

## Prerequisites

- Python 3.13
- Node.js 18+ and npm
- PostgreSQL 18 with the **pgvector** extension installed
- A Google Gemini API key (free at https://aistudio.google.com/apikey)

## Backend setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows (use: source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
```

Create `backend/.env` (never commit this file):

```
DB_NAME=ask_my_course
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Required: Google Gemini key (free at https://aistudio.google.com/apikey).
GEMINI_API_KEY=your_gemini_key_here
```

Enable pgvector once in your database (`psql -d ask_my_course`):

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Migrate and run:

```bash
python manage.py migrate
python manage.py runserver
```

The API is now at `http://127.0.0.1:8000/api/v1/`.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The dev server's origin is already allowed by the
backend's CORS settings. To point at a different API, set `VITE_API_URL`.

## Gemini key

The service uses Google Gemini's free tier for embeddings and answers, through
its OpenAI-compatible API. Get a free key at https://aistudio.google.com/apikey
and put it in `backend/.env` as `GEMINI_API_KEY`. If you change the key or the
embedding model, re-ingest your materials so all stored vectors stay consistent.

## API endpoints (all under `/api/v1/`)

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/courses` | List courses |
| POST | `/courses` | Create a course |
| POST | `/courses/{id}/ingest` | Upload + ingest a material (multipart `file`, or JSON `file_path`) |
| POST | `/courses/{id}/ask` | Ask a question → answer, sources, confidence, guardrail_triggered |
| GET  | `/courses/{id}/structure` | The unit → lesson → material tree |
| GET  | `/courses/{id}/materials` | Flat materials list with chunk counts |
| GET  | `/courses/{id}/history?limit=20` | Recent questions |

## Notes

- **Multi-tenancy**: every course belongs to a tenant (a school). Until real
  auth exists, courses created via the API use a single demo tenant.
- **Guardrail**: if the best matching chunk scores below 0.5 similarity, the
  system refuses and marks `guardrail_triggered`.
- **Chunking** defaults to ~400 words with ~60 words of overlap; both are
  configurable and meant to be tuned against an evaluation set.
