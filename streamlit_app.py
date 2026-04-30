import streamlit as st
import asyncio
import os
import subprocess
import sys
import threading
import time
import requests

st.set_page_config(page_title="PintarBot Control Center", page_icon="🤖")

st.title("🤖 PintarBot Command Center")
st.write("Status: **Online & Running in Background**")

# Tampilkan log sederhana biar keliatan bot-nya kerja
st.info("Bot ini berjalan secara otonom di server Streamlit Cloud. Gunakan Telegram untuk berinteraksi.")

if "bot_process" not in st.session_state:
    st.session_state.bot_process = None

def start_bot():
    if st.session_state.bot_process is None:
        # Jalankan bot.py sebagai subproses biar nggak ganggu Streamlit
        st.session_state.bot_process = subprocess.Popen([sys.executable, "bot.py"])
        st.success("🚀 PintarBot berhasil diaktifkan!")
    else:
        st.warning("⚠️ Bot sudah berjalan boss!")

if st.button("🔴 RESTART BOT"):
    if st.session_state.bot_process:
        st.session_state.bot_process.terminate()
        st.session_state.bot_process = None
    start_bot()

# Jalankan otomatis saat pertama kali dibuka
if st.session_state.bot_process is None:
    start_bot()

# === ANTI-SLEEP: Self-ping setiap 2 jam ===
def keep_alive_ping():
    """Ping diri sendiri setiap 2 jam biar Streamlit ga tidur"""
    app_url = os.environ.get("STREAMLIT_APP_URL", "")
    while True:
        time.sleep(7200)  # 2 jam = 7200 detik
        if app_url:
            try:
                requests.get(app_url, timeout=30)
                print(f"[KEEP-ALIVE] Ping ke {app_url} berhasil!")
            except:
                print("[KEEP-ALIVE] Ping gagal, tapi tetap jalan.")

if "keep_alive_started" not in st.session_state:
    st.session_state.keep_alive_started = True
    t = threading.Thread(target=keep_alive_ping, daemon=True)
    t.start()

st.divider()
st.subheader("📊 Statistik Ringkas")
st.write("- Mode: **PREMIUM Agentic**")
st.write("- Database: **Supabase Cloud**")
st.write("- Keamanan: **Whitelist Active**")
st.write("- Anti-Sleep: **Active (Ping setiap 2 jam)**")

st.write("---")
st.caption("PintarBot Strategic Master Plan - Phase 2.5 (Cloud Deployment)")
