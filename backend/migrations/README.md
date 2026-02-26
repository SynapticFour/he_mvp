# SPDX-License-Identifier: Apache-2.0

# Migrations

When you need schema changes:

1. Install Alembic: `pip install alembic`
2. Initialize: `alembic init migrations`
3. Configure `alembic.ini` and `migrations/env.py` to use `app.database.engine` and `app.models`.
4. Generate: `alembic revision --autogenerate -m "description"`
5. Apply: `alembic upgrade head`

Until then, `app.database.create_db_and_tables()` and the ALTER TABLE fallbacks handle initial setup.
