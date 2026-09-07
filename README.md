# Ask My Course

An AI-powered course Q&A assistant (a RAG microservice) for the Eagle LMS.
Students ask questions in plain language and get answers drawn **only** from that
course's uploaded materials, with citations (Unit → Lesson → Page) and a
confidence score. If the answer is not in the materials, it refuses instead of
guessing (the guardrail).

## Architecture

- **Backend**: Django + Django REST Framework, PostgreSQL 18 + pgvector, OpenAI
  (`text-embedding-3-small` for embeddings, `gpt-4o-mini` for answers).
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

# Leave these as-is to run fully offline with fake embeddings.
# When you have an OpenAI key, add it and flip both to false.
OPENAI_API_KEY=
USE_FAKE_EMBEDDINGS=true
USE_FAKE_LLM=true
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

## Switching from fake to real AI

The project runs offline out of the box using deterministic **fake** embeddings
and a stub answer, so you can build and demo without an API key. When the OpenAI
key is ready:

1. Put the key in `backend/.env` as `OPENAI_API_KEY`.
2. Set `USE_FAKE_EMBEDDINGS=false` and `USE_FAKE_LLM=false`.
3. **Re-ingest** your materials (fake and real vectors are not comparable, so the
   old fake vectors must be replaced).

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
