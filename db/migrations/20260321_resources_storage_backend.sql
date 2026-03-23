-- Ensure resources has storage backend columns and make resources.url nullable.
--
-- Notes:
-- - MySQL generally does not support "ADD COLUMN IF NOT EXISTS", so we use
--   INFORMATION_SCHEMA + dynamic SQL to make the migration re-runnable.

-- 1) Add storage_provider if missing
SET @has_storage_provider := (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'resources'
    AND column_name = 'storage_provider'
);
SET @sql := IF(
  @has_storage_provider = 0,
  'ALTER TABLE resources ADD COLUMN storage_provider VARCHAR(20) NULL COMMENT ''Storage provider (local/oss)'' AFTER url',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2) Add storage_key if missing
SET @has_storage_key := (
  SELECT COUNT(*)
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'resources'
    AND column_name = 'storage_key'
);
SET @sql := IF(
  @has_storage_key = 0,
  'ALTER TABLE resources ADD COLUMN storage_key VARCHAR(512) NULL COMMENT ''Storage object key'' AFTER storage_provider',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3) Make legacy/external url nullable (idempotent)
ALTER TABLE resources
  MODIFY url VARCHAR(256) NULL COMMENT 'Resource URL (legacy or external)';
