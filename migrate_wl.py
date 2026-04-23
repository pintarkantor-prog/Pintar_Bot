from db import supabase
import json
import os

WHITELIST_FILE = "whitelist.json"
OWNER_ID = 6412057180

def migrate():
    print("Memulai migrasi Whitelist ke Supabase (Kolom Baru)...")
    
    # 1. Ambil data dari file lama
    users = []
    if os.path.exists(WHITELIST_FILE):
        try:
            with open(WHITELIST_FILE, "r") as f:
                users = json.load(f)
        except: pass
    
    if OWNER_ID not in users:
        users.append(OWNER_ID)
    
    # 2. Masukkan ke PC_Whitelist
    for uid in users:
        try:
            role = "OWNER" if uid == OWNER_ID else "STAFF"
            supabase.table('PC_Whitelist').insert({
                'telegram_id': uid, 
                'nama': f"{role} ({uid})"
            }).execute()
            print(f"ID {uid} berhasil masuk!")
        except Exception as e:
            print(f"ID {uid} gagal (mungkin udah ada): {e}")

if __name__ == "__main__":
    migrate()
