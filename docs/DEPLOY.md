# Deploying Ask My Course

The project splits into three hosted pieces, each on a free tier:

| Piece | Hosted on | What it is |
|-------|-----------|------------|
| Database (Postgres + pgvector) | **Supabase** | stores courses, chunks, embeddings |
| Backend (Django API) | **Render** | the RAG API, built from `backend/Dockerfile` |
| Frontend (React) | **Cloudflare Pages** | the site students and teachers use |

> Nothing here is needed to run locally or to demo. This is only for putting a live URL online.

**Before you start:** push the repo to GitHub (Render and Cloudflare build from it).

---

## Step 1 - Database on Supabase

1. Create an account at supabase.com and create a new project. Choose a strong database password and **save it**.
2. In the project, go to **Database -> Extensions** and enable the **`vector`** extension (this is pgvector).
3. Go to **Project Settings -> Database -> Connection info**, and open the **Connection pooling** section. Use the **Session** mode values (they work with Django and are IPv4-friendly):
   - Host: `aws-0-<region>.pooler.supabase.com`
   - Port: `5432`
   - User: `postgres.<your-project-ref>`
   - Database: `postgres`
   - Password: the one you set in step 1

Keep these five values handy for Step 2.

---

## Step 2 - Backend on Render

1. Create an account at render.com. Click **New -> Web Service** and connect your GitHub repo.
2. Settings:
   - **Root Directory:** `backend`
   - **Runtime:** `Docker` (Render will use `backend/Dockerfile`, which runs migrations and starts gunicorn for you)
3. Add these **Environment Variables** (from Supabase in Step 1, plus your own):

   ```
   DB_NAME=postgres
   DB_USER=postgres.<your-project-ref>
   DB_PASSWORD=<your supabase password>
   DB_HOST=aws-0-<region>.pooler.supabase.com
   DB_PORT=5432
   DB_SSLMODE=require
   DB_CONN_MAX_AGE=600

   GEMINI_API_KEY=<your gemini key>

   DEBUG=False
   SECRET_KEY=<a long random string>
   ```
   (You do not need to set `ALLOWED_HOSTS` - Render provides its hostname automatically.)
4. Click **Create Web Service**. On the first deploy the Dockerfile runs the migrations against Supabase and starts the server.
5. Copy your backend URL, e.g. `https://ask-my-course.onrender.com`.

> Free tier note: the service sleeps after ~15 minutes idle, so the first request after a pause takes ~30-60s to wake. Uploaded PDF files are temporary on Render, but that is fine - the embeddings live in Supabase and answering never needs the original file.

---

## Step 3 - Frontend on Cloudflare Pages

1. Create an account at pages.cloudflare.com. Create a project and connect the same GitHub repo.
2. Build settings:
   - **Root directory:** `frontend`
   - **Build command:** `npm run build`
   - **Build output directory:** `dist`
3. Add an **Environment Variable** (this points the site at your backend):
   ```
   VITE_API_URL=https://ask-my-course.onrender.com/api/v1
   ```
   (use your real Render URL, and keep the `/api/v1` on the end)
4. Deploy. Copy your frontend URL, e.g. `https://ask-my-course.pages.dev`.

The `frontend/public/_redirects` file is already in the repo, so page refreshes on routes like `/student/courses/123` work.

---

## Step 4 - Let the two talk to each other

Back on **Render**, add one more environment variable so the backend allows the frontend to call it:

```
CORS_ORIGINS=https://ask-my-course.pages.dev
```
(use your real Pages URL) then let Render redeploy.

---

## Step 5 - Test

1. Open the Cloudflare Pages URL.
2. Create a course, upload a PDF, analyze and confirm.
3. Switch to the student side and ask a question.

If the first request is slow, that is the Render free tier waking up - try again and it will be fast.

---

## Quick checklist

- [ ] Repo pushed to GitHub
- [ ] Supabase project created, `vector` extension enabled, connection values copied
- [ ] Render web service (root `backend`, Docker) with all env vars + `DEBUG=False`
- [ ] Cloudflare Pages (root `frontend`, build `npm run build`, output `dist`) with `VITE_API_URL`
- [ ] `CORS_ORIGINS` on Render set to the Pages URL
- [ ] Tested end to end
