import os
from supabase import create_client, Client
from decouple import config

supabase: Client = create_client(
    config("SUPABASE_URL"),
    config("SUPABASE_KEY")
)

# Service-role client — bypasses RLS, used only for server-side sync operations.
# NEVER expose this to the frontend.
supabase_service: Client = create_client(
    config("SUPABASE_URL"),
    config("SUPABASE_SERVICE_KEY")
)
