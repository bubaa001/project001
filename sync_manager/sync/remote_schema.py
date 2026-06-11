"""
Ensure the remote Supabase Postgres database has the necessary tables
for our app's models.  This is called once on first sync and is idempotent
(uses CREATE TABLE IF NOT EXISTS).

Because we sync via the Supabase REST API (not a direct Postgres connection),
table creation happens through the Supabase Management API / SQL endpoint.
"""
import logging
from ONLportal.supabase_client import supabase

logger = logging.getLogger('sync_manager.remote_schema')

# SQL DDL for each table we sync.
# These mirror the Django models but use Postgres types.
# We use TEXT primary keys (Supabase uuid preferred, but we use bigint for
# simplicity matching local SQLite auto-increment IDs).
#
# NOTE: The `id` column on the remote side is BIGINT to match local SQLite PKs,
# but we do NOT make it a GENERATED ALWAYS AS IDENTITY — we want the local
# ID to be preserved so relationships work.

REMOTE_SCHEMA_SQL = """
-- Custom User table (mirrors accounts.User)
CREATE TABLE IF NOT EXISTS accounts_user (
    id                BIGINT PRIMARY KEY,
    password          VARCHAR(128) NOT NULL,
    last_login        TIMESTAMPTZ,
    is_superuser      BOOLEAN NOT NULL DEFAULT FALSE,
    username          VARCHAR(150) NOT NULL UNIQUE,
    first_name        VARCHAR(150) NOT NULL DEFAULT '',
    last_name         VARCHAR(150) NOT NULL DEFAULT '',
    email             VARCHAR(254) NOT NULL DEFAULT '',
    is_staff          BOOLEAN NOT NULL DEFAULT FALSE,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    date_joined       TIMESTAMPTZ NOT NULL DEFAULT now(),
    role              VARCHAR(20) NOT NULL DEFAULT 'student',
    is_approved       BOOLEAN NOT NULL DEFAULT FALSE,
    xp                INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS accounts_academicclass (
    id                BIGINT PRIMARY KEY,
    code              VARCHAR(20) NOT NULL UNIQUE,
    title             VARCHAR(200) NOT NULL,
    schedule_string   VARCHAR(100) NOT NULL DEFAULT '',
    meeting_link      VARCHAR(200) NOT NULL DEFAULT '',
    instructor_id     BIGINT REFERENCES accounts_user(id),
    slug              VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS accounts_academicclass_students (
    id                BIGINT PRIMARY KEY,
    academicclass_id  BIGINT NOT NULL REFERENCES accounts_academicclass(id) ON DELETE CASCADE,
    user_id           BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
    UNIQUE(academicclass_id, user_id)
);

CREATE TABLE IF NOT EXISTS accounts_module (
    id                BIGINT PRIMARY KEY,
    academic_class_id BIGINT NOT NULL REFERENCES accounts_academicclass(id) ON DELETE CASCADE,
    title             VARCHAR(200) NOT NULL,
    "order"           INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS accounts_classcontent (
    id                BIGINT PRIMARY KEY,
    academic_class_id BIGINT NOT NULL REFERENCES accounts_academicclass(id) ON DELETE CASCADE,
    module_id         BIGINT REFERENCES accounts_module(id) ON DELETE SET NULL,
    title             VARCHAR(200) NOT NULL,
    description       TEXT,
    file              VARCHAR(255),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    "order"           INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS accounts_archivecategory (
    id                BIGINT PRIMARY KEY,
    name              VARCHAR(100) NOT NULL UNIQUE,
    slug              VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS accounts_archiveitem (
    id                BIGINT PRIMARY KEY,
    category_id       BIGINT NOT NULL REFERENCES accounts_archivecategory(id) ON DELETE CASCADE,
    title             VARCHAR(200) NOT NULL,
    subtitle          VARCHAR(200),
    description       TEXT NOT NULL DEFAULT '',
    layout_variant    VARCHAR(20) NOT NULL DEFAULT 'standard',
    status_label      VARCHAR(20) NOT NULL DEFAULT 'COMPLETED',
    timestamp_string  VARCHAR(50) NOT NULL DEFAULT '',
    is_italic         BOOLEAN NOT NULL DEFAULT FALSE,
    has_certificate   BOOLEAN NOT NULL DEFAULT FALSE,
    certificate_url   TEXT,
    has_actions       BOOLEAN NOT NULL DEFAULT FALSE,
    download_url      TEXT,
    is_featured       BOOLEAN NOT NULL DEFAULT FALSE,
    cover_image       VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS accounts_quiz (
    id                BIGINT PRIMARY KEY,
    title             VARCHAR(255) NOT NULL,
    description       TEXT,
    creator_id        BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
    academic_class_id BIGINT REFERENCES accounts_academicclass(id) ON DELETE CASCADE,
    module_id         BIGINT REFERENCES accounts_module(id) ON DELETE SET NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS accounts_question (
    id                BIGINT PRIMARY KEY,
    quiz_id           BIGINT NOT NULL REFERENCES accounts_quiz(id) ON DELETE CASCADE,
    text              TEXT NOT NULL,
    "order"           INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS accounts_choice (
    id                BIGINT PRIMARY KEY,
    question_id       BIGINT NOT NULL REFERENCES accounts_question(id) ON DELETE CASCADE,
    text              VARCHAR(255) NOT NULL,
    is_correct        BOOLEAN NOT NULL DEFAULT FALSE,
    "order"           INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS accounts_librarybook (
    id                BIGINT PRIMARY KEY,
    title             VARCHAR(200) NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    file              VARCHAR(255),
    thumbnail         VARCHAR(255),
    uploaded_by_id    BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
    uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    academic_class_id BIGINT REFERENCES accounts_academicclass(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS accounts_instructorprofile (
    id                BIGINT PRIMARY KEY,
    user_id           BIGINT NOT NULL UNIQUE REFERENCES accounts_user(id) ON DELETE CASCADE,
    title_role        VARCHAR(200),
    bio               TEXT,
    avatar            VARCHAR(255),
    established_year  INTEGER NOT NULL DEFAULT 2024,
    academic_focus    JSONB NOT NULL DEFAULT '[]'::jsonb,
    methodologies     JSONB NOT NULL DEFAULT '[]'::jsonb,
    manuscripts       JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS accounts_studentquizsubmission (
    id                BIGINT PRIMARY KEY,
    student_id        BIGINT NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
    quiz_id           BIGINT NOT NULL REFERENCES accounts_quiz(id) ON DELETE CASCADE,
    score             INTEGER NOT NULL DEFAULT 0,
    total             INTEGER NOT NULL DEFAULT 0,
    answers           JSONB NOT NULL DEFAULT '{}'::jsonb,
    submitted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(student_id, quiz_id)
);
"""


def ensure_remote_schema() -> None:
    """
    Idempotent: execute the DDL above on the remote Supabase Postgres.
    Uses the Supabase Management API (SQL endpoint) via the service key.
    """
    logger.info("Ensuring remote schema exists on Supabase...")
    try:
        # The supabase-py client's rpc() can run arbitrary SQL if the
        # Postgres extension pg_exec is installed.  For simplicity and
        # reliability we use the REST API directly.
        import requests
        from django.conf import settings

        # Strip extra whitespace and split into individual statements
        statements = [s.strip() for s in REMOTE_SCHEMA_SQL.split(';') if s.strip()]

        for stmt in statements:
            stmt = stmt.strip() + ';'
            resp = requests.post(
                f"{settings.SUPABASE_URL}/rest/v1/rpc/exec_sql",
                headers={
                    'apikey': settings.SUPABASE_KEY,
                    'Authorization': f'Bearer {settings.SUPABASE_KEY}',
                    'Content-Type': 'application/json',
                },
                json={'query': stmt},
                timeout=30,
            )
            if resp.status_code not in (200, 201, 204):
                logger.warning("Schema statement returned %d: %s", resp.status_code, resp.text[:200])

        logger.info("Remote schema check completed.")
    except Exception as exc:
        logger.error("Failed to ensure remote schema: %s", exc)
        raise
