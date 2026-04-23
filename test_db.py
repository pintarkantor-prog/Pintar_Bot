import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    print("Testing connection...")
    response = supabase.table('Channel_Pintar').select('*').execute()
    data = response.data
    print(f"Total rows retrieved: {len(data)}")
    if len(data) > 0:
        print("Sample row:", data[0])
except Exception as e:
    print("Error:", e)
