"""Contact enrichment via Hunter.io.

Pipeline: upload -> mapping -> resolve -> hunter fan-out -> propose -> review -> commit.

Mirrors the shape of app/pipeline (async job with explicit status transitions and
SSE progress) but writes to its own tables, because review_bundles and friends
require a NOT NULL communication_id that an enrichment job has no value for.
"""
