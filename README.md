# ONLportal — Offline-First Django LMS

A learning management system built with Django 6.0 that runs offline on SQLite and
automatically syncs data to Supabase (PostgreSQL) whenever an internet connection is
available. No manual "Sync" button needed.

## Quick Start

```bash
# 1. Clone & enter the project
cd ONLportal

# 2. Create and activate a virtual environment
python -m venv venv
source venv/Scripts/activate   # Windows (Git Bash)
# or: venv\Scripts\activate    # Windows (cmd)

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations (SQLite)
python manage.py migrate

# 5. Create a superuser (for Django Admin)
python manage.py createsuperuser
```

## Running the App

You need **two terminals**:

### Terminal 1 — Django development server

```bash
source venv/Scripts/activate
python manage.py runserver
```

Open http://localhost:8000 in your browser.

### Terminal 2 — Background sync worker (django-q2)

```bash
source venv/Scripts/activate
python manage.py qcluster
```

This starts the background task cluster that:
- Checks internet connectivity every **30 seconds**
- Pushes pending changes to Supabase every **60 seconds** (only when online)
- Processes immediate sync tasks queued by user actions

## Environment Variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-django-secret-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=sb_publishable_...
DATABASE_URL=postgresql://postgres.xxx:password@aws-0-eu-west-1.pooler.supabase.com:6543/postgres
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=Your Name <you@gmail.com>
```

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django secret key |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Supabase publishable (anon) key |
| `DATABASE_URL` | Supabase connection string (used for optional direct access) |

## How Offline Sync Works

```
┌──────────────────────────────────────────────────────┐
│  User does something (register, upload book, quiz)   │
│                    │                                  │
│                    ▼                                  │
│           Save to local SQLite                        │
│                    │                                  │
│                    ▼                                  │
│     Django signal creates SyncRecord (status=pending) │
│                    │                                  │
│     ┌──────────────┴──────────────┐                  │
│     │  Immediate async task       │  Cron (every 60s)│
│     │  (register, book, quiz)     │  (everything)    │
│     └──────────────┬──────────────┘                  │
│                    │                                  │
│                    ▼                                  │
│            is_online()? ──No──► skip, try later       │
│                    │ Yes                              │
│                    ▼                                  │
│      1. Upload files → Supabase Storage               │
│      2. Upsert rows  → Supabase PostgreSQL            │
│      3. Mark record  → status=synced                  │
└──────────────────────────────────────────────────────┘
```

### What gets synced automatically

| Model | Syncs |
|---|---|
| `User` | New registrations, updates (passwords are **never** synced) |
| `AcademicClass` | Classes, student enrollments |
| `Module`, `ClassContent` | Course structure, files |
| `Quiz`, `Question`, `Choice` | Quiz questions and answers |
| `StudentQuizSubmission` | Student quiz results, XP |
| `LibraryBook` | Book metadata + file uploads to Supabase Storage |
| `InstructorProfile` | Profile data, avatar |
| `ArchiveItem`, `ArchiveCategory` | Archive content |

### Immediate sync triggers

The following user actions queue an **immediate** sync attempt (in addition to the cron cycle):

- New user registration
- Library book upload
- Quiz submission

## Viewing Sync Status

Open Django Admin at http://localhost:8000/admin/sync_manager/syncrecord/

Columns:
- **Status** — `pending` (waiting), `synced` (done), `failed` (error)
- **Action** — `create`, `update`, or `delete`
- **Table** — which remote table the record targets
- **Retry count** — how many times it's been attempted
- **Error message** — why it failed (if `failed`)

## Troubleshooting

### Check if Supabase is reachable

```bash
python manage.py shell -c "
from sync_manager.sync.connectivity import is_online
print('Online:', is_online())
"
```

### Reset failed sync records

```bash
python manage.py shell -c "
from sync_manager.models import SyncRecord
SyncRecord.objects.filter(status='failed').update(status='pending', retry_count=0)
"
```

### Ensure remote tables exist on Supabase

```bash
python manage.py shell -c "
from sync_manager.sync.remote_schema import ensure_remote_schema
ensure_remote_schema()
"
```

### Run a sync cycle manually

```bash
python manage.py shell -c "
from sync_manager.sync.tasks import sync_pending_records
print(sync_pending_records())
"
```

### Sync worker not starting?

Verify the cluster command is available:

```bash
python manage.py qcluster --help
```

If you see a `retry/timeout` warning — it's cosmetic and can be ignored.

## Project Structure

```
ONLportal/
├── accounts/              # Main app: models, views, forms, templates
├── sync_manager/          # Offline sync engine
│   ├── models.py          # SyncRecord (outbox table)
│   ├── signals.py         # Auto-capture all model writes
│   ├── triggers.py        # Immediate sync task helpers
│   ├── scheduler.py       # django-q2 cron entry points
│   └── sync/
│       ├── connectivity.py # Supabase reachability check
│       ├── tasks.py        # Core sync engine (upsert/delete)
│       ├── file_uploader.py# Push files to Supabase Storage
│       └── remote_schema.py# Ensure remote tables exist
├── ONLportal/             # Django project settings, urls, wsgi
├── templates/             # HTML templates
├── media/                 # Uploaded files (local)
├── db.sqlite3             # Local SQLite database
├── manage.py
└── requirements.txt
```

## Tech Stack

- **Django 6.0** — web framework
- **SQLite** — local offline database
- **Supabase** — remote PostgreSQL + file storage
- **django-q2** — background task queue (Django ORM broker, no Redis needed)
- **supabase-py** — Supabase client SDK
