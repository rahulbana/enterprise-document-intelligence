<!--
Name: Rahul Singh Bana
Email: bana.saa@gmail.com
LinkedIn: https://www.linkedin.com/in/rahulsinghbana
Repo: https://github.com/rahulbana/enterprise-document-intelligence
-->

# Load testing

`locustfile.py` simulates the read-heavy usage pattern real users produce —
mostly listing documents/departments and running retrieval queries, with
uploads and chat turns (the expensive paths: embedding, reranking, LLM
calls) much rarer. Run it against a real running backend, not the test
suite's fakes.

## Running it

```bash
cd backend
source .venv/bin/activate
./start.sh   # in another terminal — need the real API + worker + infra up
locust -f locustfile.py --host http://localhost:8000
```

Open http://localhost:8089, set the user count and spawn rate, and start
the run. For a headless run sized toward a specific target:

```bash
locust -f locustfile.py --host http://localhost:8000 \
  --users 200 --spawn-rate 10 --run-time 5m --headless
```

## Reading the results

- **/documents [list], /departments** — should stay fast (single indexed
  query + the departments cache) even under load. If these climb, check
  the DB connection pool isn't exhausted (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW`
  once on Postgres) before anything else.
- **/retrieval/debug** — dominated by the embedding call + cross-encoder
  rerank, not the DB. Latency here scales with `CHAT_RETRIEVAL_CANDIDATE_LIMIT`
  (how many chunks get reranked) more than with request volume.
- **/documents [upload]** — the HTTP response returns as soon as the file's
  stored; actual parsing/embedding/upsert happens in Celery, so this
  endpoint's latency shouldn't rise much under load. If it does, check disk
  I/O or `MAX_UPLOAD_BYTES`-sized bodies specifically.
- **/chat/sessions/[id]/messages** — the slowest path by far (LLM
  round-trip). This is the one to watch for `RATE_LIMIT_CHAT` (default
  20/minute/IP) rejections under many simulated users sharing test IPs —
  expected and correct, not a bug, if you're pushing well past that rate.
- **429s** — expected once a scenario legitimately exceeds `RATE_LIMIT_DEFAULT`
  /`RATE_LIMIT_AUTH`/`RATE_LIMIT_CHAT` for a given client IP; distinguish
  these from 5xx errors, which are the real signal to chase.

## Sizing toward "1M traffic"

This app's traffic target (per `PLAN.md`) is about steady-state request
volume, not 1M concurrent users. Back-of-envelope: 1M requests/day ≈ 12
req/s average, several times that at peak. A few hundred concurrent Locust
users at `wait_time(1, 3)` approximates a comparable request rate — watch
p95/p99 latency and error rate as you scale the user count up, not just the
throughput number, since a slow-but-non-erroring endpoint is the earlier
warning sign.
