# Database Migrations

This directory contains database migration scripts for the Screen Recorder Server.

## Setup

1. Install Alembic:

```bash
pip install alembic
```

2. Initialize Alembic (if not already done):

```bash
cd server
alembic init migrations
```

3. Configure `alembic.ini`:

```ini
[alembic]
script_location = migrations
sqlalchemy.url = sqlite:///screenrecorder.db
```

## Creating Migrations

1. Generate a new migration:

```bash
alembic revision --autogenerate -m "Description of changes"
```

2. Review the generated migration file in `migrations/versions/`

3. Apply the migration:

```bash
alembic upgrade head
```

## Common Commands

- `alembic current` - Show current migration version
- `alembic history` - Show migration history
- `alembic upgrade +1` - Upgrade one version
- `alembic downgrade -1` - Downgrade one version
- `alembic upgrade head` - Upgrade to latest version
- `alembic downgrade base` - Downgrade to initial state

## Migration Best Practices

1. Always review auto-generated migrations before applying
2. Test migrations on a copy of production data first
3. Backup database before applying migrations
4. Keep migrations small and focused
5. Add meaningful descriptions to migrations
