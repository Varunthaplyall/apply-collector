#!/usr/bin/env python3
"""
One-time backfill: compute embeddings for all existing jobs that don't have one.

Usage:
    python scripts/backfill_embeddings.py              # all jobs (batched)
    python scripts/backfill_embeddings.py --limit 100  # first 100 only
    python scripts/backfill_embeddings.py --dry-run    # show count, don't update

The embedding model (paraphrase-MiniLM-L3-v2, 384-dim, 17MB) is loaded once and reused.
Expects ~50-200 jobs/second depending on hardware.
"""

import sys
import time
from pathlib import Path

# Ensure the project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from data_collection.database import (
    get_connection, get_jobs_without_embeddings, update_job_embedding,
)
from data_collection.embedding import embed_texts


def main():
    dry_run = "--dry-run" in sys.argv
    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
    batch_size = 64

    conn = get_connection()

    # Schema migration is handled by init_db() in the main app — skip here
    # to avoid statement timeouts on constraint re-creation in large tables.
    col = conn.execute(
        """SELECT 1 FROM information_schema.columns
           WHERE table_name = 'jobs' AND column_name = 'embedding'"""
    ).fetchone()
    if not col:
        print("ERROR: 'embedding' column not found. Run the app's init_db() first.")
        conn.close()
        return

    # Count pending
    pending = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE embedding IS NULL"
    ).fetchone()[0]
    print(f"Jobs needing embeddings: {pending}")
    if pending == 0:
        print("All jobs already have embeddings.")
        conn.close()
        return

    if dry_run:
        print("Dry run — no changes made.")
        conn.close()
        return

    effective_limit = min(limit, pending) if limit else pending
    print(f"Will process {effective_limit} jobs in batches of {batch_size}...")
    print()

    processed = 0
    errors = 0
    t_start = time.time()

    while processed < effective_limit:
        batch_limit = min(batch_size, effective_limit - processed)
        rows = get_jobs_without_embeddings(conn, limit=batch_limit)

        if not rows:
            break

        # Build text inputs for batch embedding
        texts = []
        for row in rows:
            desc = (row.get("description") or "")[:500].strip()
            parts = [
                (row.get("title") or "").strip(),
                (row.get("company") or "").strip(),
            ]
            loc = (row.get("location") or "").strip()
            if loc:
                parts.append(loc)
            if desc:
                parts.append(desc)
            texts.append(" | ".join(parts))

        try:
            embeddings = embed_texts(texts, batch_size=batch_size)
        except Exception as e:
            print(f"  ERROR embedding batch: {e}")
            errors += len(rows)
            processed += len(rows)
            continue

        # Store embeddings
        for row, embedding in zip(rows, embeddings):
            try:
                update_job_embedding(conn, row["id"], embedding)
            except Exception as e:
                print(f"  ERROR storing embedding for job {row['id']}: {e}")
                errors += 1

        conn.commit()
        processed += len(rows)

        elapsed = time.time() - t_start
        rate = processed / elapsed if elapsed > 0 else 0
        pct = processed / effective_limit * 100
        print(f"  [{processed:>6}/{effective_limit}] {pct:5.1f}%  "
              f"({rate:.0f} jobs/s)  errors: {errors}")

    t_total = time.time() - t_start
    print()
    print(f"Done: {processed} jobs processed in {t_total:.1f}s "
          f"({processed / t_total:.0f} jobs/s)")
    if errors:
        print(f"Errors: {errors}")
    print(f"Remaining without embeddings: "
          f"{conn.execute('SELECT COUNT(*) FROM jobs WHERE embedding IS NULL').fetchone()[0]}")
    conn.close()


if __name__ == "__main__":
    main()
