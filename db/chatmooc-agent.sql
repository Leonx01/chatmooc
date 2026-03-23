-- chatmooc-agent.sql
-- Only based on: db/schema.md
-- Target: MySQL 8.x (InnoDB, utf8mb4)
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS exercises;
DROP TABLE IF EXISTS flashcards;
DROP TABLE IF EXISTS units;
DROP TABLE IF EXISTS session_resources;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS resources;
DROP TABLE IF EXISTS paths;
DROP TABLE IF EXISTS users;

-- 1) User (users)
CREATE TABLE users (
  uid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'User ID (UUID)',
  uname VARCHAR(50) NOT NULL COMMENT 'Username',
  password VARCHAR(16) NOT NULL DEFAULT '123456' COMMENT 'User Password',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Account created time',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last updated time',
  PRIMARY KEY (uid),
  UNIQUE KEY uk_users_uname (uname)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

-- 2) Resource (resources)
CREATE TABLE resources (
  rid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Resource ID (UUID)',
  uid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Owner user ID (UUID)',
  url VARCHAR(256) NULL COMMENT 'Resource URL (legacy or external)',
  storage_provider VARCHAR(20) NULL COMMENT 'Storage provider (local/oss)',
  storage_key VARCHAR(512) NULL COMMENT 'Storage object key',
  rname VARCHAR(100) NOT NULL COMMENT 'Resource name',
  rtype VARCHAR(20) NOT NULL COMMENT 'Resource type (doc/video/audio/etc.)',
  content LONGTEXT NULL COMMENT 'Raw extracted text content',
  summary TEXT NULL COMMENT 'Generated summary (optional)',
  keywords JSON NULL COMMENT 'Keywords (JSON array/object)',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created time',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated time',
  status INT DEFAULT 0 COMMENT '0=pending, 1=parsing, 2=parsed',
  PRIMARY KEY (rid),
  KEY idx_resources_uid_created (uid, created_at),
  KEY idx_resources_rtype (rtype),
  CONSTRAINT fk_resources_uid
    FOREIGN KEY (uid) REFERENCES users(uid)
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

-- 3) Session (sessions)
CREATE TABLE sessions (
  sid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Session ID (UUID)',
  uid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Owner user ID (UUID)',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Session start time',
  PRIMARY KEY (sid),
  KEY idx_sessions_uid_created (uid, created_at),
  CONSTRAINT fk_sessions_uid
    FOREIGN KEY (uid) REFERENCES users(uid)
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

-- 4) SessionResource (session_resources)
CREATE TABLE session_resources (
  sid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Session ID (UUID)',
  rid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Resource ID (UUID)',
  added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Time resource added to session',
  PRIMARY KEY (sid, rid),
  KEY idx_session_resources_rid (rid),
  CONSTRAINT fk_session_resources_sid
    FOREIGN KEY (sid) REFERENCES sessions(sid)
    ON DELETE CASCADE,
  CONSTRAINT fk_session_resources_rid
    FOREIGN KEY (rid) REFERENCES resources(rid)
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

-- 5) Path (paths)
CREATE TABLE paths (
  pid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Path ID (UUID)',
  description TEXT NULL COMMENT 'Path description',
  PRIMARY KEY (pid)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

-- 6) Unit (units)
CREATE TABLE units (
  unit_id CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Unit ID (UUID)',
  pid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Path ID (UUID)',
  uid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Owner user ID (UUID)',
  sid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NULL COMMENT 'Optional session ID (UUID)',
  core_concepts JSON NULL COMMENT 'Core concepts (JSON array/object)',
  goal VARCHAR(200) NOT NULL COMMENT 'Learning goal',
  guide TEXT NOT NULL COMMENT 'Learning guide/outline',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created time',
  completed_at DATETIME NULL COMMENT 'Completed time (optional)',
  status INT DEFAULT 0 COMMENT '0=not_started, 1=in_progress, 2=completed',
  PRIMARY KEY (unit_id),
  KEY idx_units_uid_created (uid, created_at),
  KEY idx_units_pid (pid),
  KEY idx_units_sid (sid),
  CONSTRAINT fk_units_pid
    FOREIGN KEY (pid) REFERENCES paths(pid)
    ON DELETE CASCADE,
  CONSTRAINT fk_units_uid
    FOREIGN KEY (uid) REFERENCES users(uid)
    ON DELETE CASCADE,
  CONSTRAINT fk_units_sid
    FOREIGN KEY (sid) REFERENCES sessions(sid)
    ON DELETE SET NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

-- 7) FlashCard (flashcards)
CREATE TABLE flashcards (
  fcid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Flashcard ID (UUID)',
  unit_id CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Unit ID (UUID)',
  uid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Owner user ID (UUID)',
  question TEXT NOT NULL COMMENT 'Front side / question',
  answer TEXT NOT NULL COMMENT 'Back side / answer',
  review_count INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Review count',
  last_reviewed_at DATETIME NULL COMMENT 'Last reviewed time (optional)',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created time',
  PRIMARY KEY (fcid),
  KEY idx_flashcards_unit_id (unit_id),
  KEY idx_flashcards_uid_created (uid, created_at),
  CONSTRAINT fk_flashcards_unit_id
    FOREIGN KEY (unit_id) REFERENCES units(unit_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_flashcards_uid
    FOREIGN KEY (uid) REFERENCES users(uid)
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

-- 8) Exercise (exercises)
CREATE TABLE exercises (
  eid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Exercise ID (UUID)',
  unit_id CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Unit ID (UUID)',
  uid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Owner user ID (UUID)',
  question TEXT NOT NULL COMMENT 'Question text',
  options JSON NULL COMMENT 'Options (JSON array/object, optional)',
  correct_answer TEXT NOT NULL COMMENT 'Correct answer',
  explanation TEXT NULL COMMENT 'Explanation (optional)',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created time',
  PRIMARY KEY (eid),
  KEY idx_exercises_unit_id (unit_id),
  KEY idx_exercises_uid_created (uid, created_at),
  CONSTRAINT fk_exercises_unit_id
    FOREIGN KEY (unit_id) REFERENCES units(unit_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_exercises_uid
    FOREIGN KEY (uid) REFERENCES users(uid)
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

-- 9) MilvusVector (milvus_vectors)
-- Note:
-- - schema.md mentions `vector VECTOR(768)`, but MySQL 8 community does not provide a stable VECTOR type.
-- - Model embeddings as optional bytes (BLOB). Real vectors typically live in Milvus; db keeps metadata.
-- - A single resource can be split into multiple chunks; enforce UNIQUE(rid, chunk_num).
CREATE TABLE milvus_vectors (
  id CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Vector record ID (UUID)',
  rid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Resource ID (UUID)',
  uid CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL COMMENT 'Owner user ID (UUID)',
  content TEXT NOT NULL COMMENT 'Chunk content used for embedding',
  chunk_num INT UNSIGNED NOT NULL COMMENT 'Chunk index (0-based or 1-based by app convention)',
  vector BLOB NULL COMMENT 'Optional embedding bytes',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created time',
  PRIMARY KEY (id),
  UNIQUE KEY uk_milvus_vectors_rid_chunk (rid, chunk_num),
  KEY idx_milvus_vectors_uid_created (uid, created_at),
  CONSTRAINT fk_milvus_vectors_rid
    FOREIGN KEY (rid) REFERENCES resources(rid)
    ON DELETE CASCADE,
  CONSTRAINT fk_milvus_vectors_uid
    FOREIGN KEY (uid) REFERENCES users(uid)
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

SET FOREIGN_KEY_CHECKS = 1;
