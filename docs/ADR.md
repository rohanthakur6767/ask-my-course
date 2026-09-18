# Architecture Decision Records

An ADR records one important decision and the reasoning behind it, so anyone
reading the project later understands *why* it is built the way it is. Each entry
has a Context (the situation), a Decision (what we chose), and Consequences (what
we gain and give up).

---

## ADR 1 - Django + Django REST Framework instead of FastAPI

**Status:** Accepted

**Context.** An early option was FastAPI, but Django + DRF was chosen so the
service matches a typical LMS backend stack and keeps the ORM, migrations, and
admin all in one framework.

**Decision.** Build the API on Django + DRF.

**Consequences.**
- Gain: a mature ORM, built-in migrations, admin, and serializers, which made the
  data model and endpoints fast to build; everything stays in one framework.
- Give up: Django's request path is synchronous by default (no native async like
  FastAPI), and the framework is heavier. Neither matters at this service's scale.

---

## ADR 2 - PostgreSQL + pgvector instead of a dedicated vector database

**Status:** Accepted

**Context.** RAG needs vector similarity search. Options included a dedicated
vector DB (e.g. Pinecone) or the pgvector extension inside Postgres.

**Decision.** Use pgvector inside the same PostgreSQL database that holds the
relational data.

**Consequences.**
- Gain: one database to run and back up; course filtering (multi-tenancy) and
  vector search happen in a single SQL query; no extra service or network hop.
- Give up: a specialised vector DB may scale further at very large volumes. At
  one school's course materials, pgvector is comfortably enough. Revisit only if
  data grows by orders of magnitude.

---

## ADR 3 - HNSW index instead of ivfflat

**Status:** Accepted

**Context.** An ivfflat index (`lists = 100`) was the initial choice. pgvector also
offers HNSW.

**Decision.** Use an HNSW index (`m = 16`, `ef_construction = 64`,
`vector_cosine_ops`).

**Consequences.**
- Gain: HNSW needs no training data, so it builds correctly on an empty table
  (ivfflat must be rebuilt after data is loaded to get good recall). It gives
  better recall at our dataset size, and query accuracy is tunable at run time
  via `hnsw.ef_search` without a rebuild.
- Give up: HNSW uses more memory and builds more slowly than ivfflat at very
  large scale. Negligible here.
- This is a deliberate design choice; the reasoning is recorded here.

---

## ADR 4 - Local native Postgres for development; Docker for packaging

**Status:** Accepted

**Context.** Docker Compose gives a one-command setup, but installing Postgres
locally first made iteration faster during development.

**Decision.** Develop against a locally installed Postgres + pgvector, and add a
Dockerfile + docker-compose for reproducible setup and deployment.

**Consequences.**
- Gain: fast local iteration while learning, plus a `docker compose up` path for
  anyone who does not want to install Postgres by hand, and an image to deploy.
- Give up: two supported ways to run. `DB_HOST` is read from the environment so
  switching between them (`localhost` vs the `db` service) is a config change,
  not a code change.

---

## ADR 5 - AI provider: Google Gemini free tier via the OpenAI-compatible API

**Status:** Accepted

**Context.** The initial plan assumed OpenAI (`text-embedding-3-small` + `gpt-4o-mini`),
but no OpenAI key was available. We needed embeddings and answer
generation at no cost, with minimal code change. (During early development, before
any key, a temporary deterministic "fake" provider let the pipeline be built and
tested offline; it has since been removed.)

**Decision.** Use Google Gemini's free tier through its **OpenAI-compatible API**,
so we keep the `openai` client and change only the base URL, key, and model names.
Embeddings: `gemini-embedding-001` requested at **1536 dimensions**, so it matches
the existing `vector(1536)` column with no migration. Answers: `gemini-3.1-flash-lite`
(a lite model with a generous free daily limit, which matters for the 50-question
evaluation; the larger `gemini-3.6-flash` has a very small free quota).

**Consequences.**
- Gain: zero cost, no dependency on a paid API key, and almost no code
  change (Gemini speaks OpenAI's API). 1536-dim output means no schema change.
- Give up: a switch from the originally planned OpenAI models (documented here); free-tier
  rate limits need care during bulk runs; model availability can shift (we saw
  `gemini-2.5-flash` deprecated for new keys), so model IDs are pinned in one place
  and easy to update.

---

## ADR 6 - Denormalized citation fields on each embedding

**Status:** Accepted

**Context.** Every answer must cite Unit -> Lesson -> Page. That data lives up
the chain (embedding -> material -> lesson -> unit -> course).

**Decision.** Copy `course`, `unit_name`, `lesson_name`, and `page_number` onto
each embedding row when it is created.

**Consequences.**
- Gain: retrieval returns everything needed for filtering and citations in one
  query, with no extra joins on the hot path.
- Give up: some duplication, and the copies could go stale if a unit is renamed.
  Chunks are effectively write-once (re-ingest on change), so the risk is small.

---

## ADR 7 - PDF auto-structuring with teacher confirmation

**Status:** Accepted (build pending the OpenAI key)

**Context.** A single PDF often spans many units and lessons. Making the teacher
split the file or hand-label every part is tedious; dumping the whole file under
one label makes citations coarse.

**Decision.** On upload, the LLM proposes an outline (units -> lessons with page
ranges) from the document's text. The teacher reviews and edits it, then
confirms. On confirm, each lesson segment is ingested separately: its page range
is chunked, embedded, and stored under the right unit and lesson, so citations
stay precise. A single-unit fallback remains for PDFs with no clear headings or
when the teacher skips auto-structure.

**Consequences.**
- Gain: one upload builds a full Course -> Unit -> Lesson tree; precise
  citations; near-zero teacher effort; no silent guessing (the confirm step).
- Give up: one extra LLM call and a two-step upload flow; quality depends on the
  PDF having detectable headings; one PDF becomes several Material rows (one per
  lesson segment).
