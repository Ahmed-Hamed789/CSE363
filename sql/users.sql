-- Run once as the RDS master user (cse363admin) against the `postgres` database.
-- Already applied during Milestone 1 — kept here as the documented source of truth.
-- See evidence/rds-database-isolation-proof.txt for proof of the isolation this creates.

CREATE DATABASE docs_db;
CREATE DATABASE quiz_db;

CREATE USER docs_user WITH PASSWORD '...';
CREATE USER quiz_user WITH PASSWORD '...';

REVOKE ALL ON DATABASE docs_db FROM PUBLIC;
REVOKE ALL ON DATABASE quiz_db FROM PUBLIC;

GRANT ALL PRIVILEGES ON DATABASE docs_db TO docs_user;
GRANT ALL PRIVILEGES ON DATABASE quiz_db TO quiz_user;

-- Lets each service user create its own tables (Milestone 2 needs this —
-- the services below run CREATE TABLE IF NOT EXISTS on startup).
\connect docs_db
GRANT USAGE, CREATE ON SCHEMA public TO docs_user;

\connect quiz_db
GRANT USAGE, CREATE ON SCHEMA public TO quiz_user;
