# Source-of-truth amendment — FU-20260513204522-create-scripts-minio-bootstrap-sh-referenced-by-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P02-S06-T003 | wiring | Create scripts/minio-bootstrap.sh referenced by docker-compose minio-init | Runtime follow-up P02-S06-T001 | current | planned | medium | human | P02-S06-T001 | api:rag-docs | scripts/minio-bootstrap.sh | — | — | — | — | runtime-followup#FU-20260513204522-create-scripts-minio-bootstrap-sh-referenced-by- | runtime-followup#FU-20260513204522-create-scripts-minio-bootstrap-sh-referenced-by- | scripts/minio-bootstrap.sh exists and creates bucket $S3_BUCKET_DOCUMENTS via mc alias set + mc mb --ignore-existing. dev-restart.sh --reset on a clean repo creates the bucket without manual boto3 intervention. | Clean docker volume rm p02-s06-t001_minio_data, run docker compose up minio-init, ensure exit 0 and bucket exists via boto3 list_buckets. |
```
