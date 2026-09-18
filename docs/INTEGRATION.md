# Integration guide - calling Ask My Course from your LMS

Ask My Course runs as its own service. The host LMS talks to it over HTTP. This guide
shows how to call it.

## Base URL

- Local: `http://127.0.0.1:8000/api/v1`
- Deployed: whatever host the container runs on (e.g. `http://ask-my-course-service:8000/api/v1`).

## Typical flow

1. A teacher creates a course and uploads materials (the Teacher Dashboard, or
   `POST /courses` then `POST /courses/{id}/ingest`).
2. A student asks a question: the LMS calls `POST /courses/{id}/ask`.
3. The LMS shows the answer, the sources, and the confidence.

## Ask a question

`POST /api/v1/courses/{course_id}/ask`

Request:

```json
{ "question": "What are the main functions of the cell membrane?", "top_k": 5 }
```

Response:

```json
{
  "answer": "...",
  "sources": [
    { "unit": "Cell Biology", "lesson": "Organelles", "page": 12, "relevance_score": 0.82 }
  ],
  "confidence": 0.82,
  "guardrail_triggered": false
}
```

When the answer is not in the materials, `guardrail_triggered` is `true`,
`sources` is empty, and `answer` is a polite refusal. The LMS should show the
refusal rather than treat it as an error.

## Example call (Python, as the LMS would)

```python
import requests

def ask_course_question(course_id, question, tenant_id):
    resp = requests.post(
        f"http://ask-my-course-service:8000/api/v1/courses/{course_id}/ask",
        json={"question": question},
        headers={"X-Tenant-ID": str(tenant_id)},   # reserved for multi-tenant auth
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
```

## Other endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/health` | Liveness + database check (for load balancers). |
| GET  | `/stats` | Totals for the current tenant (dashboard KPIs). |
| GET  | `/courses` | List courses. |
| POST | `/courses` | Create a course. |
| POST | `/courses/{id}/ingest` | Upload + ingest a material (multipart `file`, or JSON `file_path`). |
| GET  | `/courses/{id}/structure` | Unit -> lesson -> material tree. |
| GET  | `/courses/{id}/materials` | Flat materials list with chunk counts. |
| GET  | `/courses/{id}/history?limit=20` | Recent questions. |

## Multi-tenancy and auth (planned)

Each course belongs to a tenant (a school). Today a single demo tenant is used.
For production, the LMS will pass the tenant (e.g. an `X-Tenant-ID` header) and
a Bearer token; the service will scope every query to that tenant and reject
unauthenticated calls. The data model already carries `tenant_id`, so enabling
this is additive.

## Deployment shape

The service is a container that runs alongside the LMS (for example in ECS),
pointed at a PostgreSQL database that has the pgvector extension. See
`docker-compose.yml` for the local equivalent.
