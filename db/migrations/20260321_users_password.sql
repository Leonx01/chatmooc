-- Align DB schema with ORM: app.models.Users.password
-- NOTE: MySQL will error if the column already exists; run once.

ALTER TABLE users
  ADD COLUMN password VARCHAR(16) NOT NULL DEFAULT '123456' COMMENT 'User Password' AFTER uname;
