-- ═══════════════════════════════════════════════════════════════════════════
-- Migration: Convert from per-user job pools to a global job pool.
--
-- Run this ONCE on your Supabase PostgreSQL database BEFORE deploying the
-- updated code.  The migration is idempotent (safe to re-run).
--
-- What it does:
--   1. Drops the old UNIQUE(source, source_id, user_id) constraint.
--   2. Deduplicates: keeps one row per (source, source_id) — the earliest.
--   3. Drops the user_id column and its index.
--   4. Creates a new global UNIQUE(source, source_id) constraint.
--
-- ⚠️  BACKUP YOUR DATABASE before running this.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- 1. Drop the old 3-column unique constraint
DO $$
DECLARE
    old_constraint text;
BEGIN
    SELECT conname INTO old_constraint
    FROM pg_constraint
    WHERE conrelid = 'jobs'::regclass AND contype = 'u'
      AND conname LIKE '%source%source_id%';
    IF old_constraint IS NOT NULL THEN
        EXECUTE 'ALTER TABLE jobs DROP CONSTRAINT ' || old_constraint;
        RAISE NOTICE 'Dropped constraint: %', old_constraint;
    ELSE
        RAISE NOTICE 'No old constraint found — skipping';
    END IF;
END $$;

-- 2. Deduplicate: remap profile_job_matches then delete duplicate jobs.
--    Keeps the earliest row (MIN id) per (source, source_id).
DO $$
DECLARE
    dup_count int;
BEGIN
    -- Remap profile_job_matches to point to the surviving job row
    UPDATE profile_job_matches pjm
    SET job_id = surviving.min_id
    FROM (
        SELECT source, source_id, MIN(id) as min_id
        FROM jobs
        GROUP BY source, source_id
        HAVING COUNT(*) > 1
    ) surviving
    WHERE pjm.job_id IN (
        SELECT j2.id FROM jobs j2
        WHERE j2.source = surviving.source
          AND j2.source_id = surviving.source_id
          AND j2.id <> surviving.min_id
    );

    -- Delete duplicate job rows (keep MIN id)
    DELETE FROM jobs j1
    USING jobs j2
    WHERE j1.source = j2.source
      AND j1.source_id = j2.source_id
      AND j1.id > j2.id;

    GET DIAGNOSTICS dup_count = ROW_COUNT;
    RAISE NOTICE 'Removed % duplicate job rows', dup_count;
END $$;

-- 3. Clean up orphaned profile_job_matches (same profile+job after remap)
DELETE FROM profile_job_matches a
USING profile_job_matches b
WHERE a.profile_id = b.profile_id
  AND a.job_id = b.job_id
  AND a.ctid > b.ctid;

-- 4. Drop user_id column and index
ALTER TABLE jobs DROP COLUMN IF EXISTS user_id;
DROP INDEX IF EXISTS idx_jobs_user;

-- 5. Create new global unique constraint
ALTER TABLE jobs ADD CONSTRAINT jobs_source_source_id_key
    UNIQUE (source, source_id);

COMMIT;

-- Verification queries (run after COMMIT)
-- Should return 0 (no duplicates)
SELECT COUNT(*) as duplicate_count
FROM (
    SELECT source, source_id, COUNT(*)
    FROM jobs GROUP BY source, source_id HAVING COUNT(*) > 1
) sub;

-- Should show the new constraint
SELECT conname FROM pg_constraint
WHERE conrelid = 'jobs'::regclass AND conname = 'jobs_source_source_id_key';
