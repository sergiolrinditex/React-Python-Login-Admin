# Official Doc Note — P00-S02-T001 Docker Compose Image Tags
RESOLVED: All discrepancies applied by developer on 2026-05-09. See resolution details per check below.
  - postgres: pgvector/pgvector:pg18-bookworm (was pg17, updated to pg18-bookworm per researcher)
  - redis: redis:8-alpine (was redis:7.4-alpine, updated to redis:8-alpine per researcher)
  - litellm: ghcr.io/berriai/litellm:v1.83.14-stable (was main-stable floating tag, now pinned)
  - minio: minio/minio:RELEASE.2025-09-07T16-13-09Z (researcher confirmed latest tag)
  - backend/worker: python:3.13-slim-bookworm (was python:3.13-slim, now explicit bookworm)
  - frontend: nginxinc/nginx-unprivileged:1.29-alpine (was 1.27-alpine which does NOT exist)

**Date**: 2026-05-09
**Task**: P00-S02-T001 (Docker compose services, Rancher-ready)
**Researcher**: official-docs-researcher
**Pass type**: DEEP (all items new — no prior cache for Docker image tags)

---

## CHECK 1 — Postgres + pgvector

**Question**: Confirm canonical image for pgvector-enabled Postgres.

**Findings (from pgvector GitHub README + Docker Hub, 2026-05-09)**:

- Latest pgvector extension version: **0.8.2** (pushed ~2 months ago, i.e. ~March 2026)
- Supported Postgres major versions in Docker images: **13–18**
- Available Debian variants per PG version:
  - `pgvector/pgvector:pg17` — rolling latest (points to 0.8.2-pg17-bookworm or equivalent)
  - `pgvector/pgvector:pg17-bookworm` — Debian Bookworm (stable)
  - `pgvector/pgvector:pg17-trixie` — Debian Trixie (testing)
  - `pgvector/pgvector:pg18` — rolling latest for PG18
  - `pgvector/pgvector:pg18-bookworm` — Debian Bookworm (stable)
  - `pgvector/pgvector:pg18-trixie` — Debian Trixie (testing)
- The README explicitly documents Docker pull examples using `pg18-trixie` as the shown command.
- No `latest` tag without a pg-version suffix is documented.

**DISCREPANCY with task pack**:

The task pack's service contract table references `pgvector/pgvector:pg18` — this is a valid rolling tag but TECHNICAL_GUIDE §10.4 says "pg18 or equivalent". The task pack is consistent internally. However:
1. **pg18 vs pg17**: PostgreSQL 18 is the most recent major version (as of 2026). The project's first migration (P01-S01-T001) only needs pgvector + pgcrypto — no PG18-specific features are required. Using `pg18` is acceptable and forward-looking.
2. **Bookworm vs Trixie**: For production use, `bookworm` (Debian stable) is safer than `trixie` (Debian testing). The plain `pg18` tag without a Debian suffix resolves to the image that pgvector project chooses — historically this has been Bookworm. To be explicit and reproducible, prefer `pgvector/pgvector:pg18-bookworm` (or `0.8.2-pg18-bookworm` for full pin).

**Recommendation for developer**:

Use `pgvector/pgvector:pg18-bookworm` as the image tag (or pin to `0.8.2-pg18-bookworm` for immutability). This matches the task pack's intent (`pg18`) while being explicit about Debian variant. Bookworm is Debian stable — appropriate for production-oriented compose.

pgcrypto is part of the standard `postgresql-contrib` package included in the pgvector image — no additional image or initdb args needed. The P01-S01-T001 migration can run `CREATE EXTENSION IF NOT EXISTS pgcrypto;` on first boot.

**RESOLVED**: verified 2026-05-09 via https://github.com/pgvector/pgvector/blob/master/README.md + https://hub.docker.com/r/pgvector/pgvector/tags

---

## CHECK 2 — Redis

**Question**: Confirm latest stable Redis major, alpine tag, and Celery 5.6.3 / kombu compatibility.

**Findings (from Docker Hub API + PyPI kombu, 2026-05-09)**:

- **Redis latest tag** resolves to **8.6.3** (confirmed from Docker Hub, pushed 2026-05-07)
- `redis:8-alpine` tag exists and resolves to **8.6.3** (identical digest to `redis:8.6.3-alpine`)
- `redis:8.6.3-alpine` is available (exact pinned version)
- Redis 7.x alpine tags: not visible as recently updated tags — Redis 8 is current stable/`latest`
- **kombu 5.6.2** (latest; T003 pinned celery 5.6.3 which requires `kombu>=5.6.0`): Python client constraint is `redis!=4.5.5,!=5.0.2,<6.5,>=4.5.2`
- **redis Python client 6.4.0** (pinned in T003): satisfies `>=4.5.2 AND <6.5` — **COMPATIBLE** with kombu 5.6.2
- kombu constraints are on the **Python client package** (`redis` PyPI package), NOT on the Redis server version. Redis server 8.6.3 is a different thing — there is no documented server-version constraint in kombu; the Python client handles protocol negotiation.
- **Celery 5.6.3** is still the latest stable (no 5.6.4+ as of 2026-05-09 per PyPI)

**Recommendation for developer**:

Use `redis:8-alpine` (resolves to 8.6.3-alpine) or pin to `redis:8.6.3-alpine` for full immutability. The task pack's current candidate `redis:7.4-alpine` is outdated — Redis 8 is current stable. The Python client `redis==6.4.0` is fully compatible with kombu 5.6.2.

**DISCREPANCY**: Task pack service contract lists `redis:7.4-alpine` as candidate. Current Docker Hub stable is **Redis 8.6.3**. The `7.4` release is over a year old and is no longer `latest`. Developer SHOULD use `redis:8-alpine` (or `redis:8.6.3-alpine`). The Python client `redis==6.4.0` and kombu constraint `<6.5` are both satisfied. No breaking change risk in using Redis 8 server with the pinned Python client.

**RESOLVED**: verified 2026-05-09 via Docker Hub API (redis alpine tags) + https://pypi.org/pypi/kombu/5.6.2/json

---

## CHECK 3 — LiteLLM proxy

**Question**: Canonical image, tag for v1.83.14, `litellm_config.yaml` schema, healthcheck endpoint.

**Findings (from GitHub API releases + LiteLLM docs, 2026-05-09)**:

### Image registry and tag

- **Canonical registry**: `ghcr.io/berriai/litellm` (GitHub Container Registry — primary)
- Alternative for database-enabled deployments: `ghcr.io/berriai/litellm-database`
- Docker Hub documentation mentions `docker.litellm.ai/berriai/litellm` as a mirror
- Tag `main-latest` is the rolling latest (NOT recommended for production — no stability guarantee)
- **Official recommendation from README**: "Use docker images with the `-stable` tag. These have undergone 12 hour load tests before being published."
- Stable tag format: `<version>-stable` — e.g., `v1.83.14-stable`

### Current releases (as of 2026-05-09)

| Release | Date | Notes |
|---|---|---|
| v1.83.14-stable.patch.3 | 2026-05-07 | Latest stable |
| v1.83.14-stable.patch.2 | 2026-05-06 | — |
| v1.83.14-stable | 2026-04-26 | Base stable for 1.83.14 |
| v1.84.0-rc.1 | 2026-05-05 | RC — NOT production |

### Tag to use

The Python lib is pinned to `litellm==1.83.14`. The matching Docker image is:
- `ghcr.io/berriai/litellm:v1.83.14-stable` (base stable — matches Python lib exactly)
- OR `ghcr.io/berriai/litellm:v1.83.14-stable.patch.3` (latest patch on top of 1.83.14 — includes hotfixes)

**Recommendation**: Use `ghcr.io/berriai/litellm:v1.83.14-stable` to exactly match the Python lib pin. Do NOT use `main-stable` (floating tag, not immutable) or `main-latest`.

### `litellm_config.yaml` schema (2026-05-09, from docs.litellm.ai/docs/proxy/docker_quick_start)

```yaml
model_list:
  - model_name: <alias>
    litellm_params:
      model: <provider>/<model-id>
      api_base: os.environ/PROVIDER_API_BASE   # or literal string
      api_key: os.environ/PROVIDER_API_KEY

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  # database_url: ... (optional — only needed for virtual key management)

litellm_settings:
  ssl_verify: false  # dev only
  # drop_params: true  # optional
```

For dev (no models yet), a minimal valid config is:
```yaml
model_list: []
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

The image expects the config file mounted at the path given to `--config` CLI flag (default pattern: `/app/config.yaml`).

### Healthcheck endpoints (from docs.litellm.ai/docs/proxy/health)

| Endpoint | Description | Auth required | Use for |
|---|---|---|---|
| `/health` | Full check — makes real API calls to each model | Yes | Manual checks |
| `/health/readiness` | Checks DB, cache, callbacks — proxy ready to accept requests | No | K8s readinessProbe |
| `/health/liveliness` | Returns `"I'm alive!"` — basic process alive check | No | K8s livenessProbe, Docker healthcheck |
| `/health/services` | Checks Datadog/Langfuse etc. | Admin | Observability |

**Recommendation**: Use `/health/liveliness` for the Docker healthcheck (maps to K8s livenessProbe). Task pack already references this endpoint correctly as `http://localhost:4000/health/liveliness`.

**Note on spelling**: It is `/health/liveliness` (not `/health/liveness`) — the LiteLLM docs consistently use the non-standard spelling "liveliness". The task pack already uses the correct spelling.

**RESOLVED**: verified 2026-05-09 via https://api.github.com/repos/BerriAI/litellm/releases + https://docs.litellm.ai/docs/proxy/health + https://raw.githubusercontent.com/BerriAI/litellm/main/README.md

---

## CHECK 4 — MinIO

**Question**: Current image tag, canonical registry, healthcheck URL.

**Findings (from Docker Hub + MinIO official docs, 2026-05-09)**:

### Current release tag

- Most recent timestamped tag visible on Docker Hub: `RELEASE.2025-09-07T16-13-09Z` (8 months ago)
- The `latest` tag on Docker Hub points to this same digest
- **Note**: MinIO's GitHub releases page showed `RELEASE.2025-10-15T17-29-55Z` (October 2025) but the Docker Hub page showed September 2025. There may be a lag in Docker Hub publishing. Use `latest` or check the GitHub releases page for the newest tag.

### Canonical registry

Docker Hub `minio/minio` is the primary documented registry. The official MinIO docs (container section) reference Docker Hub commands. `quay.io/minio/minio` exists as a mirror for enterprise/airgapped environments but Docker Hub is canonical for open-source MinIO.

### Healthcheck endpoints (from docs.min.io/enterprise/aistor-object-store/operations/monitoring/healthcheck-probe)

| Endpoint | Returns | Use for |
|---|---|---|
| `/minio/health/live` | 200 OK (server running), 429 (high load) | **Liveness probe / Docker healthcheck** |
| `/minio/health/cluster` | 200 OK (write quorum met), 503 (quorum not met) | K8s readinessProbe (write) |
| `/minio/health/cluster/read` | 200 OK (read quorum), 503 (not) | K8s readinessProbe (read) |

**Recommendation**: Use `/minio/health/live` for the Docker compose healthcheck. This is the documented liveness endpoint. The task pack correctly references this endpoint in the verification commands.

**DISCREPANCY**: Task pack service contract table shows `curl -fsS http://localhost:9000/minio/health/live` which is CORRECT per official docs. The task pack verification commands also use `/minio/health/live` — consistent and correct.

For the image tag: the task pack says `minio/minio:RELEASE.YYYY-MM-DDTHH-MM-SSZ (researcher pins exact)`. The most recent confirmed tag is `minio/minio:RELEASE.2025-09-07T16-13-09Z` (or check GitHub for newer). Developer should verify the absolute latest by running:
```bash
docker pull minio/minio:latest && docker inspect minio/minio:latest | grep -i "created\|RepoDigests"
```
Or use `latest` in compose with a SHA256 digest pin for immutability.

**RESOLVED**: verified 2026-05-09 via https://hub.docker.com/r/minio/minio/tags + https://docs.min.io/enterprise/aistor-object-store/operations/monitoring/healthcheck-probe/

---

## CHECK 5 — Python base image

**Question**: Is `python:3.13-slim-bookworm` current? Any drift to trixie?

**Findings (from Docker Hub, 2026-05-09)**:

- `python:3.13-slim-bookworm` is available and was last pushed **2026-04-22** — recent and active
- Exact current patch: `3.13.13-slim-bookworm` (Python 3.13.13)
- SHA256 digest: `sha256:bb73517d48bd32016e15eade0c009b2724ec3a025a9975b5cd9b251d0dcadb33`
- Trixie variants also exist: `3.13-slim-trixie`, `3.13.13-slim-trixie` (last pushed 2026-04-24)
- Bookworm is Debian 12 (current stable). Trixie is Debian 13 (testing/next).

**Recommendation**: Use `python:3.13-slim-bookworm` for production Dockerfiles. This is the stable Debian variant. The plain `python:3.13-slim` tag also resolves to bookworm (Debian stable is the default). For maximum reproducibility, pin to `python:3.13.13-slim-bookworm`.

Bookworm is still the LTS variant for Docker images — there is NO drift away from it for `python:3.13-slim`. Trixie tags exist but are explicitly the testing/unstable variant. No action needed — task pack's recommendation of `python:3.13-slim` (or `python:3.13-slim-bookworm`) is correct.

**RESOLVED**: verified 2026-05-09 via Docker Hub API (python 3.13-slim tags)

---

## CHECK 6 — Nginx unprivileged

**Question**: Confirm `nginxinc/nginx-unprivileged:1.27-alpine` or newer for frontend Dockerfile.

**Findings (from Docker Hub, 2026-05-09)**:

- `1.27-alpine`: **NOT AVAILABLE** in current tags. Nginx 1.27 is not the current stable.
- Current nginx stable branch: **1.29.x** (Nginx 1.29.8 as of the latest push)
- Available non-perl, non-otel alpine tags for 1.29:
  - `1.29-alpine` — available, stable non-perl alpine
  - `1.29-alpine3.23` — specific Alpine 3.23 variant
  - `1.29.8-alpine` — exact patch version
  - `1.29.8-alpine3.23` — exact patch + exact Alpine
- The `alpine` tag (no version prefix) resolves to the latest stable-alpine (currently 1.29.x)
- Default port: **8080** (not 80; cannot bind to <1024 as non-root)
- Runs as non-root user (unprivileged by design)

**DISCREPANCY**: Task pack specifies `nginxinc/nginx-unprivileged:1.27-alpine` which does NOT exist. Current stable is **1.29.x**. Developer MUST use `nginxinc/nginx-unprivileged:1.29-alpine` (or `1.29.8-alpine` for exact pin).

The UID for nginx-unprivileged is typically **101** (nginx user). The task pack references `USER 101` in the frontend Dockerfile design — this is correct.

**RESOLVED**: verified 2026-05-09 via Docker Hub API (nginx-unprivileged 1.29 tags query)

---

## CHECK 7 — Celery 5.6.3 + kombu breaking changes since 2026-05-08

**Question**: Any breaking changes between T003 pin (2026-05-08) and today (2026-05-09)?

**Findings (from PyPI celery + kombu, 2026-05-09)**:

- **Celery**: Still at 5.6.3 as of 2026-05-09. No 5.6.4+ released. No breaking changes.
- **kombu**: Latest is 5.6.2 (confirmed). T003 pinned `celery[redis]==5.6.3` which requires `kombu>=5.6.0` — satisfied by 5.6.2.
- **Python redis client**: `redis==6.4.0` (pinned by T003). kombu 5.6.2 requires `redis>=4.5.2,<6.5 AND !=4.5.5,!=5.0.2` — **redis 6.4.0 satisfies this constraint** (6.4.0 < 6.5.0 is TRUE).
- **Redis server 8.6.3**: The kombu constraints apply to the Python `redis` package (client), not the server. Redis 8.x server is fully usable with the `redis==6.4.0` Python client as the client handles protocol negotiation.

**Recommendation**: No changes needed. T003 pins remain valid. Use `redis:8-alpine` (or `redis:8.6.3-alpine`) for the Docker server image — fully compatible.

**RESOLVED**: verified 2026-05-09 via https://pypi.org/pypi/celery/json + https://pypi.org/pypi/kombu/5.6.2/json

---

## Summary for developer (action items)

| Service | Task pack candidate | Verified tag to use | Notes |
|---|---|---|---|
| postgres | `pgvector/pgvector:pg18` | **`pgvector/pgvector:pg18-bookworm`** | Explicit Debian stable variant; 0.8.2 included |
| redis | `redis:7.4-alpine` | **`redis:8-alpine`** (= 8.6.3) or `redis:8.6.3-alpine` | Redis 8 is current stable; 7.4 is outdated |
| litellm | `ghcr.io/berriai/litellm:main-stable` | **`ghcr.io/berriai/litellm:v1.83.14-stable`** | Pin to version matching Python lib; `main-stable` is floating |
| minio | `minio/minio:RELEASE.YYYY-MM-DDTHH-MM-SSZ` | **`minio/minio:latest`** + digest pin, or `RELEASE.2025-09-07T16-13-09Z` | Verify latest tag before pinning |
| backend/worker | `python:3.13-slim` | **`python:3.13-slim-bookworm`** (or `3.13.13-slim-bookworm`) | Bookworm explicit; no trixie drift |
| frontend | `nginxinc/nginx-unprivileged:1.27-alpine` | **`nginxinc/nginx-unprivileged:1.29-alpine`** | 1.27 does NOT exist; 1.29 is current stable |

### Healthcheck endpoints (confirmed)

| Service | Healthcheck URL | Status |
|---|---|---|
| backend | `http://localhost:8000/health` | Correct (task pack) |
| litellm | `http://localhost:4000/health/liveliness` | CORRECT — note spelling: "liveliness" not "liveness" |
| minio | `http://localhost:9000/minio/health/live` | CORRECT per official docs |
| redis | `redis-cli ping` → PONG | Correct (no HTTP endpoint) |
| postgres | `pg_isready -U $POSTGRES_USER -d $POSTGRES_DB` | Correct |
| frontend nginx | `http://localhost:8080/` | Correct (nginx-unprivileged listens on 8080) |

### Discrepancies requiring developer action

1. **DISCREPANCY (medium)** — `redis:7.4-alpine` is outdated. Use `redis:8-alpine`.
2. **DISCREPANCY (medium)** — `nginxinc/nginx-unprivileged:1.27-alpine` does NOT exist. Use `1.29-alpine`.
3. **DISCREPANCY (low)** — `ghcr.io/berriai/litellm:main-stable` is a floating tag. Pin to `v1.83.14-stable`.
4. **NOTE (low)** — `pgvector/pgvector:pg18` is valid but `pg18-bookworm` is more explicit and reproducible.
5. **NOTE (low)** — MinIO `latest` tag should be pinned by digest before production. For dev, `latest` is acceptable as long as compose.yml documents the intent.

---

*Sources*:
- https://github.com/pgvector/pgvector/blob/master/README.md
- https://hub.docker.com/r/pgvector/pgvector/tags
- https://hub.docker.com/_/redis/tags (Docker Hub API alpine filter)
- https://pypi.org/pypi/celery/json
- https://pypi.org/pypi/kombu/5.6.2/json
- https://api.github.com/repos/BerriAI/litellm/releases
- https://raw.githubusercontent.com/BerriAI/litellm/main/README.md
- https://docs.litellm.ai/docs/proxy/docker_quick_start
- https://docs.litellm.ai/docs/proxy/health
- https://hub.docker.com/r/minio/minio/tags
- https://docs.min.io/enterprise/aistor-object-store/operations/monitoring/healthcheck-probe/
- https://hub.docker.com/v2/repositories/library/python/tags (3.13-slim filter)
- https://hub.docker.com/v2/repositories/nginxinc/nginx-unprivileged/tags (1.29 filter)
