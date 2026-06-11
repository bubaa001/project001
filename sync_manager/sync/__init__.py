"""
Offline → Supabase sync engine.

Modules:
  connectivity   – check whether the Supabase API is reachable
  tasks          – actual django-q2 tasks that push data upstream
  file_uploader  – helper that uploads local FileField content to Supabase Storage
  remote_schema  – helper that ensures the remote Postgres tables exist
"""
