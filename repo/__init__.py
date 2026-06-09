"""Data-access layer (persistence).

Services call into ``repo/`` for storage; nothing here imports ``slack_bolt``.
Currently backed by Supabase Postgres via psycopg3 (see ``repo/db.py``).
"""
