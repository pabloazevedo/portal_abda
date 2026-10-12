-- App mobile: vínculo User↔Musician + refresh tokens
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS musician_id INTEGER NULL
    REFERENCES musicians(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_users_musician_id
  ON users (musician_id)
  WHERE musician_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS api_refresh_tokens (
  id          SERIAL PRIMARY KEY,
  user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash  VARCHAR(64) NOT NULL UNIQUE,
  expires_at  TIMESTAMPTZ NOT NULL,
  revoked_at  TIMESTAMPTZ NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  user_agent  VARCHAR(255) NULL,
  client      VARCHAR(40) NULL
);

CREATE INDEX IF NOT EXISTS ix_api_refresh_tokens_user_id ON api_refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS ix_api_refresh_tokens_expires_at ON api_refresh_tokens (expires_at);
