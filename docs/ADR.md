# Architecture Decision Records

An ADR records one important decision and the reasoning behind it, so anyone
reading the project later understands *why* it is built the way it is. Each entry
has a Context (the situation), a Decision (what we chose), and Consequences (what
we gain and give up).

---

## ADR 1 - Django + Django REST Framework instead of FastAPI

**Status:** Accepted

**Context.** The original brief suggested FastAPI. The team lead (Shivam) asked
for Django + DRF so this service matches the rest of the Eagle LMS stack.

**Decision.** Build the API on Django + DRF.

**Consequences.**
- Gain: a mature ORM, built-in migrations, admin, and serializers, which made the
  data model and endpoints fast to build; consistency with the team's other work.
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

## ADR 3 - HNSW index instead of the brief's ivfflat

**Status:** Accepted

**Context.** The brief specified an ivfflat index (`lists = 100`). pgvector also
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
- This is a deliberate deviation from the brief; the reasoning is recorded here.

---

## ADR 4 - Local native Postgres for development; Docker for packaging

**Status:** Accepted

**Context.** The brief mentioned Docker Compose for one-command setup. Shivam
asked to install Postgres locally first.

**Decision.** Develop against a locally installed Postgres + pgvector, and add a
Dockerfile + docker-compose for reproducible setup and deployment.

**Consequences.**
- Gain: fast local iteration while learning, plus a `docker compose up` path for
  anyone who does not want to install Postgres by hand, and an image to deploy.
- Give up: two supported ways to run. `DB_HOST` is read from the environment so
  switching between them (`localhost` vs the `db` service) is a config change,
  not a code change.

---

## ADR 5 - Offline "fake" AI provider behind settings flags

**Status:** Accepted

**Context.** The OpenAI key was not available during the build, but the whole
pipeline (ingest, retrieve, generate) needed to be developed and tested.

**Decision.** Put a deterministic fake embedding provider and a stub answer
behind `USE_FAKE_EMBEDDINGS` and `USE_FAKE_LLM`. The rest of the code always
calls the same functions.

**Consequences.**
- Gain: the full app runs and is testable offline; switching to real OpenAI is
  flipping two flags in `.env`.
- Give up: fake vectors carry no real meaning, so quality cannot be judged in
  fake mode, and stored fake embeddings must be re-ingested once real embeddings
  are enabled (the two are not comparable).

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
