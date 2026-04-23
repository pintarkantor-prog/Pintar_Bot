import streamlit as st
import asyncio
import os
import subprocess
import sys

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

st.divider()
st.subheader("📊 Statistik Ringkas")
st.write("- Mode: **PREMIUM Agentic**")
st.write("- Database: **Supabase Cloud**")
st.write("- Keamanan: **Whitelist Active**")

st.write("---")
st.caption("PintarBot Strategic Master Plan - Phase 2.5 (Cloud Deployment)")
