import asyncio
import logging
import html
import os
import json
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
import scraper
import db
from config import TELEGRAM_BOT_TOKEN

# --- PERSONALITY: PINTARBOT BUDDY MODE ---
# Sahabat kerja paling asik dan pengertian!

class InputChannelState(StatesGroup):
    waiting_for_data = State()

class UpdateStatusState(StatesGroup):
    waiting_for_keyword = State()

class AdminState(StatesGroup):
    waiting_for_whitelist_id = State()
    waiting_for_staff_finance = State()

class UpdateHPState(StatesGroup):
    waiting_for_date = State()

class InputChannelState(StatesGroup):
    waiting_for_data = State()

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Temp Store
pending_audit_store = {}
slot_session_store = {}

# --- SECURITY ---
OWNER_ID = 6412057180
def get_allowed_users():
    """Ambil daftar ID yang diizinkan dari Supabase boss!"""
    try:
        res = db.supabase.table('PC_Whitelist').select('telegram_id').execute()
        return [int(item['telegram_id']) for item in res.data]
    except Exception as e:
        print(f"Error Whitelist DB: {e}")
        return [OWNER_ID]

def save_allowed_users(user_id, nama="Staff"):
    """Tambah user ke whitelist database boss!"""
    try:
        db.supabase.table('PC_Whitelist').insert({'telegram_id': user_id, 'nama': nama}).execute()
        return True
    except: return False

def remove_allowed_user(user_id):
    """Hapus user dari whitelist database boss!"""
    try:
        db.supabase.table('PC_Whitelist').delete().eq('telegram_id', user_id).execute()
        return True
    except: return False

def is_authorized(user_id):
    return user_id == OWNER_ID or user_id in get_allowed_users()

def get_progress_bar(current, total):
    """Bikin progress bar cantik boss!"""
    percent = (current / total) * 100
    filled = int(percent / 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"<code>[{bar}] {int(percent)}%</code>"

def get_main_keyboard(user_id):
    rows = [
        [KeyboardButton(text="📺 Kelola Channel"), KeyboardButton(text="⚙️ Operasional")],
        [KeyboardButton(text="💳 Arus Kas")]
    ]
    if user_id == OWNER_ID:
        rows[1].append(KeyboardButton(text="🔐 Admin Panel"))
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Ada perintah apa kita hari ini?")

# --- NAVIGATION HANDLERS ---

@dp.callback_query(F.data == "back_to_main_menu")
async def back_to_lobby(callback: types.CallbackQuery):
    kb = get_main_keyboard(callback.from_user.id)
    try: await callback.message.delete()
    except: pass
    await callback.message.answer("🏠 <b>Menu Utama nongol lagi!</b>\nMau beresin yang mana dulu kita?", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "back_to_ch_manage")
async def back_to_ch_lvl1(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Rekap Channel", callback_data="ch_rekap:start")],
        [InlineKeyboardButton(text="➕ Input Akun Baru", callback_data="ch_add:start")],
        [InlineKeyboardButton(text="🔍 Audit Channel", callback_data="audit_menu:start")],
        [InlineKeyboardButton(text="🏠 Menu Utama", callback_data="back_to_main_menu")]
    ])
    await callback.message.edit_text("📂 <b>KELOLA CHANNEL</b>\n\nMau ngapain kita sekarang?", reply_markup=kb)
    await callback.answer()

# --- HANDLER UTAMA ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if not is_authorized(message.from_user.id): return
    kb = get_main_keyboard(message.from_user.id)
    await message.answer(
        "<b>Oi Boss! Apa kabar hari ini?</b> 😎✨\n\n"
        "Gue udah siap nih nemenin lu tempur di YouTube. Semua data udah gue rapihin, tinggal lu perintah aja mau eksekusi yang mana.\n\n"
        "Kita gaspol bareng hari ini ya! Pilih menunya di bawah: 👇", 
        reply_markup=kb
    )

@dp.message(F.text == "📺 Kelola Channel")
async def cmd_channel_management(message: types.Message, state: FSMContext):
    if not is_authorized(message.from_user.id): return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Rekap Channel", callback_data="ch_rekap:start")],
        [InlineKeyboardButton(text="➕ Input Akun Baru", callback_data="ch_add:start")],
        [InlineKeyboardButton(text="🔍 Audit Channel", callback_data="audit_menu:start")],
        [InlineKeyboardButton(text="🏠 Menu Utama", callback_data="back_to_main_menu")]
    ])
    await message.answer("📂 <b>Okelah boss, kita masuk ke gudang channel!</b>", reply_markup=ReplyKeyboardRemove())
    await message.answer("Mau kita apain nih koleksi channel lu hari ini? Pilih eksekusinya ya:", reply_markup=kb)

@dp.message(F.text == "💳 Arus Kas")
async def cmd_finance_dashboard(message: types.Message, state: FSMContext):
    await state.clear()
    summary = db.get_cashflow_summary()
    
    def format_idr(val):
        return f"Rp {val:,.0f}".replace(",", ".")
    
    now = datetime.now()
    month_name = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"][now.month-1]
    
    text = (
        "💰 <b>DASHBOARD KEUANGAN</b>\n"
        f"🗓 <b>{month_name} {now.year}</b>\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"🟢 <b>PEMASUKAN :</b>\n<code>{format_idr(summary['masuk'])}</code>\n\n"
        f"🔴 <b>PENGELUARAN :</b>\n"
        f"   ├ Operasional: <code>{format_idr(summary['keluar_operasional'])}</code>\n"
        f"   ├ Gaji Staff : <code>{format_idr(summary['gaji_staff'])}</code>\n"
        f"   ╰ TOTAL      : <b>{format_idr(summary['total_keluar'])}</b>\n\n"
        "━━━━━━━━━━━━━━━\n"
        f"📊 <b>SALDO BERSIH :</b>\n<b>{format_idr(summary['saldo'])}</b>\n"
        "━━━━━━━━━━━━━━━\n\n"
        "<i>Laporan mencakup transaksi operasional bulan ini & kewajiban gaji staff.</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Input Masuk", callback_data="fin:add:PENDAPATAN"),
         InlineKeyboardButton(text="💸 Input Keluar", callback_data="fin:add:PENGELUARAN")],
        [InlineKeyboardButton(text="🕒 5 Transaksi Terakhir", callback_data="fin:history")],
        [InlineKeyboardButton(text="🏠 Menu Utama", callback_data="back_to_main_menu")]
    ])
    
    await message.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "fin:history")
async def process_fin_history(callback: types.CallbackQuery):
    history = db.get_last_transactions(5)
    if not history:
        await callback.answer("📭 Belum ada transaksi tercatat boss."); return
        
    def format_idr(val):
        return f"Rp {val:,.0f}".replace(",", ".")
        
    text = "🕒 <b>5 TRANSAKSI TERAKHIR</b>\n━━━━━━━━━━━━━━━\n\n"
    for tx in history:
        icon = "🟢" if str(tx['Tipe']).upper() == 'PENDAPATAN' else "🔴"
        tgl = datetime.strptime(tx['Tanggal'], "%Y-%m-%d").strftime("%d/%m")
        kat = tx.get('Kategori', '-')
        nom = format_idr(float(tx['Nominal']))
        ket = tx.get('Keterangan', '-')
        
        text += f"{icon} <b>{tgl} | {nom}</b>\n"
        text += f"└ <i>{kat} - {ket}</i>\n\n"
        
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="fin:back")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "fin:back")
async def process_fin_back(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await cmd_finance_dashboard(callback.message, state)

@dp.message(F.text == "🔐 Admin Panel")
async def cmd_admin_panel(message: types.Message, state: FSMContext):
    # Cek ID user
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ <b>AKSES DITOLAK!</b>\nMenu ini cuma bisa dibuka sama sang Owner Utama PintarBot. 😎🔒"); return
    
    await _show_admin_dashboard(message, state)

async def _show_admin_dashboard(obj, state: FSMContext):
    """Fungsi internal buat nampilin dashboard admin (Support Message & Callback)"""
    await state.clear()
    text = (
        "🔐 <b>ADMIN PANEL: PUSAT KENDALI</b>\n"
        "━━━━━━━━━━━━━━━\n\n"
        "Selamat datang boss! Di sini lu bisa ngatur siapa aja yang boleh akses bot dan mantau data staff lu.\n\n"
        "Pilih kendali lu hari ini:"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛡️ Kelola Whitelist ID", callback_data="admin:whitelist")],
        [InlineKeyboardButton(text="👥 Kelola Data Staff", callback_data="admin:staff")],
        [InlineKeyboardButton(text="🏠 Menu Utama", callback_data="back_to_main_menu")]
    ])
    
    if isinstance(obj, types.Message):
        await obj.answer(text, reply_markup=kb)
    else:
        await obj.message.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "admin:whitelist")
async def process_admin_whitelist(callback: types.CallbackQuery):
    users = get_allowed_users()
    text = "🛡️ <b>DAFTAR WHITELIST ID</b>\n━━━━━━━━━━━━━━━\n\n"
    for i, user in enumerate(users):
        label = "👑 Owner" if user == OWNER_ID else f"👤 Staff {i}"
        text += f"• <code>{user}</code> ({label})\n"
        
    text += "\n<i>Staff yang ID-nya ada di sini bisa akses menu bot.</i>"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Tambah ID Baru", callback_data="admin:add_whitelist")],
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin:back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "admin:add_whitelist")
async def process_admin_add_wl_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.waiting_for_whitelist_id)
    await callback.message.edit_text(
        "🆔 <b>TAMBAH WHITELIST</b>\n\nKirimkan <b>ID Telegram</b> staff yang mau lu izinin boss.\nContoh: <code>123456789</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Batal", callback_data="admin:whitelist")]])
    )

@dp.message(AdminState.waiting_for_whitelist_id)
async def process_admin_add_wl_save(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ <b>Format Salah!</b>\nKirimkan angka ID Telegram saja boss."); return
        
    new_id = int(message.text)
    users = get_allowed_users()
    if new_id in users:
        await message.answer("⚠️ ID ini udah ada di daftar boss!"); await state.clear(); return
        
    if save_allowed_users(new_id, f"Staff ({new_id})"):
        await message.answer(f"✅ <b>BERES BOSS!</b>\nID <code>{new_id}</code> sekarang udah punya akses ke bot lu. 🔒🫡")
    else:
        await message.answer("❌ Gagal simpan ke database boss!")
        
    await state.clear()
    # Balik ke menu whitelist
    await cmd_admin_panel(message, state)

@dp.callback_query(F.data == "admin:staff")
async def process_admin_staff_list(callback: types.CallbackQuery):
    staffs = db.get_all_staff()
    # KECUALIKAN DIAN (OWNER)
    staffs = [s for s in staffs if s['Nama'].upper() != 'DIAN']
    
    text = "👥 <b>DAFTAR STAFF PINTAR</b>\n━━━━━━━━━━━━━━━\n\n"
    
    kb_list = []
    for s in staffs:
        text += f"👤 <b>{s['Nama']}</b> ({s['Jabatan']})\n"
        text += f"├ Gaji: <code>{s['Gaji_Pokok']}</code>\n"
        text += f"╰ Tunj: <code>{s['Tunjangan']}</code>\n\n"
        kb_list.append([InlineKeyboardButton(text=f"✍️ Edit {s['Nama']}", callback_data=f"staff_edit:{s['id']}")])
        
    kb_list.append([InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin:back")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("staff_edit:"))
async def process_admin_edit_staff_start(callback: types.CallbackQuery, state: FSMContext):
    staff_id = int(callback.data.split(":")[1])
    # Ambil info staff buat ditampilin
    staffs = db.get_all_staff()
    staff = next((s for s in staffs if s['id'] == staff_id), None)
    
    if not staff:
        await callback.answer("❌ Staff nggak ketemu!"); return
        
    await state.update_data(edit_staff_id=staff_id)
    await state.set_state(AdminState.waiting_for_staff_finance)
    
    await callback.message.edit_text(
        f"✍️ <b>EDIT FINANSIAL: {staff['Nama']}</b>\n\n"
        f"Gaji Pokok saat ini: <code>{staff['Gaji_Pokok']}</code>\n"
        f"Tunjangan saat ini: <code>{staff['Tunjangan']}</code>\n\n"
        "Kirimkan nominal baru dengan format:\n"
        "<code>Gaji Tunjangan</code>\n\n"
        "Contoh: <code>2000000 500000</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Batal", callback_data="admin:staff")]])
    )

@dp.message(AdminState.waiting_for_staff_finance)
async def process_admin_edit_staff_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    staff_id = data.get('edit_staff_id')
    
    try:
        parts = message.text.split("*")
        if len(parts) != 2: raise ValueError
        gp = int(parts[0].strip())
        tj = int(parts[1].strip())
    except:
        await message.answer("❌ <b>Format Salah!</b>\nGunakan format: <code>Gaji*Tunjangan</code>\nContoh: <code>2500000*500000</code>"); return
        
    db.update_staff_finance(staff_id, gp, tj)
    await message.answer(f"✅ <b>BERHASIL!</b>\nData finansial staff sudah diupdate di Supabase. 💰🦾")
    await state.clear()
    # Balik ke list
    await cmd_admin_panel(message, state)

@dp.callback_query(F.data == "admin:back")
async def process_admin_back(callback: types.CallbackQuery, state: FSMContext):
    # Pastikan yang klik adalah Owner
    if callback.from_user.id != OWNER_ID:
        await callback.answer("⛔ Akses Terlarang!", show_alert=True); return
    await callback.message.delete()
    # Panggil dashboard admin lewat fungsi internal
    await _show_admin_dashboard(callback, state)

@dp.message(F.text == "⚙️ Operasional")
async def cmd_operasional_menu(message: types.Message, state: FSMContext):
    if not is_authorized(message.from_user.id): return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Info HP", callback_data="hp:menu")],
        [InlineKeyboardButton(text="📅 Jadwal Harian", callback_data="sched:view")],
        [InlineKeyboardButton(text="🏠 Menu Utama", callback_data="back_to_main_menu")]
    ])
    await message.answer("⚙️ <b>Siap boss! Menu operasional udah kebuka.</b>", reply_markup=ReplyKeyboardRemove())
    await message.answer("Mau ngecek HP atau liat jadwal tempur hari ini? Gas pilih boss:", reply_markup=kb)

# --- CHANNEL MANAGEMENT (REKAP, ADD, SEARCH) ---

@dp.callback_query(F.data == "ch_rekap:start")
async def process_rekap_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    stats = db.get_channel_stats()
    text = (
        f"📊 <b>REKAP CHANNEL</b>\n\n"
        f"🟢 PROSES: {stats['PROSES']}\n"
        f"🟡 STANDBY: {stats['STANDBY']}\n"
        f"🔴 BUSUK: {stats['BUSUK']}\n"
        f"⛔ SUSPEND: {stats['SUSPEND']}\n"
        f"💰 SOLD (Bulan Ini): {stats['SOLD']}\n\n"
        f"📈 <b>TOTAL: {stats['TOTAL']} Akun</b>\n\n"
        "🔍 <b>MAU CARI AKUN BOSS?</b>\n"
        "Langsung ketik aja email atau link channelnya di sini, terus kirim pesan! Nanti gue cariin dalemannya. 😎✨"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 List PROSES", callback_data="list:PROSES:0"),
         InlineKeyboardButton(text="📂 List STANDBY", callback_data="list:STANDBY:0")],
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="back_to_ch_manage")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await state.set_state(UpdateStatusState.waiting_for_keyword)
    await callback.answer()

@dp.callback_query(F.data.startswith("list:"))
async def process_list_channels_paged(callback: types.CallbackQuery):
    _, status, offset = callback.data.split(":")
    offset = int(offset)
    
    if status == 'PROSES':
        all_hp = db.get_all_hp_labels_sorted()
        hp_pair = all_hp[offset:offset+2]
        
        if not hp_pair:
            await callback.answer("🏁 Udah sampe ujung boss!")
            return
            
        channels = db.get_channels_by_hp_list(hp_pair)
        text = f"📂 <b>LIST AKUN: PROSES</b>\n<i>Fokus: {', '.join([f'HP {h}' if 'HP' not in str(h) else h for h in hp_pair])}</i>\n━━━━━━━━━━━━━━━\n\n"
        
        for hp in hp_pair:
            hp_label = f"HP {hp}" if "HP" not in str(hp) else hp
            hp_chans = [c for c in channels if str(c['HP']) == str(hp)]
            text += f"<b>╭─📱 {hp_label}</b>\n"
            if not hp_chans:
                text += "<b>│</b>  <i>(Kosong)</i>\n"
            else:
                for c in hp_chans:
                    text += f"<b>│</b>  ▪️ {html.escape(c['NAMA_CHANNEL'])}\n"
            text += "<b>╰──────────────</b>\n\n"
            
        btn_hp_pair = ", ".join([f"HP {h}" if "HP" not in str(h) else h for h in hp_pair])
        kb_list = [
            [InlineKeyboardButton(text=f"🔍 Cek Detail ({btn_hp_pair})", callback_data=f"view_bulk:{offset}")]
        ]
        
        nav_buttons = []
        if offset > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Sebelumnya", callback_data=f"list:PROSES:{max(0, offset-2)}"))
        if offset + 2 < len(all_hp):
            nav_buttons.append(InlineKeyboardButton(text="Selanjutnya ➡️", callback_data=f"list:PROSES:{offset+2}"))
        
        if nav_buttons: kb_list.append(nav_buttons)
        kb_list.append([InlineKeyboardButton(text="⬅️ Kembali ke Rekap", callback_data="ch_rekap:start")])
        
    elif status == 'READY_TO_SELL':
        # --- LOGIKA SIAP JUAL: PROSES & STANDBY >= 1000 SUBS ---
        limit = 6
        all_ready = db.get_all_ready_to_sell()
        channels = all_ready[offset:offset+limit]
        
        if not channels and offset == 0:
            await callback.answer("📭 Belum ada yang tembus 1000 subs boss. Semangat!")
            return
            
        text = f"💰 <b>CHANNEL SIAP JUAL</b>\n<i>Halaman {int(offset/limit)+1}</i>\n━━━━━━━━━━━━━━━\n\n"
        
        for ch in channels:
            text += f"📺 <b>{html.escape(ch['NAMA_CHANNEL'])}</b>\n"
            text += f"<b>├</b> 📧 <code>{ch['EMAIL']}</code>\n"
            text += f"<b>├</b> 🔑 <code>{ch['PASSWORD']}</code>\n"
            text += f"<b>├</b> 📊 Subs: <b>{ch.get('SUBSCRIBE', 0)}</b>\n"
            text += f"<b>├</b> 🔗 <a href='{ch['LINK_CHANNEL']}'>Link Channel</a>\n"
            text += f"<b>╰</b> 📍 Status: <b>{ch['STATUS']}</b>\n\n"
            
        nav_buttons = []
        if offset > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Sebelumnya", callback_data=f"list:READY_TO_SELL:{max(0, offset-limit)}"))
        if offset + limit < len(all_ready):
            nav_buttons.append(InlineKeyboardButton(text="Selanjutnya ➡️", callback_data=f"list:READY_TO_SELL:{offset+limit}"))
            
        kb_list = []
        if nav_buttons: kb_list.append(nav_buttons)
        kb_list.append([InlineKeyboardButton(text="⬅️ Kembali", callback_data="audit_menu:start")])
        
    else:
        # --- LOGIKA STANDBY: PER 6 AKUN (DETAIL LANGSUNG) ---
        limit = 6
        channels = db.get_channels_by_status_paged(status, limit=limit, offset=offset)
        
        if not channels and offset == 0:
            await callback.answer(f"📭 Nggak ada akun status {status} boss.")
            return
            
        text = f"📂 <b>LIST AKUN: {status}</b>\n<i>Halaman {int(offset/limit)+1}</i>\n━━━━━━━━━━━━━━━\n\n"
        
        for ch in channels:
            text += f"📺 <b>{html.escape(ch['NAMA_CHANNEL'])}</b>\n"
            text += f"<b>├</b> 📧 <code>{ch['EMAIL']}</code>\n"
            text += f"<b>├</b> 🔑 <code>{ch['PASSWORD']}</code>\n"
            text += f"<b>├</b> 📊 Subs: <b>{ch.get('SUBSCRIBE', 0)}</b>\n"
            text += f"<b>╰</b> 🔗 <a href='{ch['LINK_CHANNEL']}'>Link Channel</a>\n\n"
            
        nav_buttons = []
        if offset > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Sebelumnya", callback_data=f"list:{status}:{max(0, offset-limit)}"))
        if len(channels) == limit:
            nav_buttons.append(InlineKeyboardButton(text="Selanjutnya ➡️", callback_data=f"list:{status}:{offset+limit}"))
            
        kb_list = []
        if nav_buttons: kb_list.append(nav_buttons)
        
        # Tombol kembali dinamis
        back_to = "audit_menu:start" if status == 'SOLD' else "ch_rekap:start"
        kb_list.append([InlineKeyboardButton(text="⬅️ Kembali", callback_data=back_to)])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list), disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("view_bulk:"))
async def process_view_bulk_details(callback: types.CallbackQuery):
    offset = int(callback.data.split(":")[1])
    all_hp = db.get_all_hp_labels_sorted()
    hp_pair = all_hp[offset:offset+2]
    channels = db.get_channels_by_hp_list(hp_pair)
    
    if not channels:
        await callback.answer("📭 HP ini lagi kosong boss."); return
        
    # Natural Sort Manual
    def natural_sort_key(s):
        return [int(text) if text.isdigit() else text.lower()
                for text in re.split('([0-9]+)', str(s))]
    channels.sort(key=lambda x: natural_sort_key(x['HP']))
    
    text = f"📋 <b>DETAIL AKUN: {', '.join([f'HP {h}' if 'HP' not in str(h) else h for h in hp_pair])}</b>\n━━━━━━━━━━━━━━━\n\n"
    
    for ch in channels:
        hp_label = f"HP {ch['HP']}" if "HP" not in str(ch['HP']) else ch['HP']
        text += f"<b>╭─📱 {hp_label}</b> | <b>{html.escape(ch['NAMA_CHANNEL'])}</b>\n"
        text += f"<b>├</b> 📧 <code>{ch['EMAIL']}</code>\n"
        text += f"<b>├</b> 🔑 <code>{ch['PASSWORD']}</code>\n"
        text += f"<b>├</b> 📊 Subs: <b>{ch.get('SUBSCRIBE', 0)}</b>\n"
        text += f"<b>╰</b> 🔗 <a href='{ch['LINK_CHANNEL']}'>Link Channel</a>\n\n"
        
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data=f"list:PROSES:{offset}")]])
    
    if len(text) > 4000:
        await callback.message.answer("⚠️ Datanya kepanjangan boss, gue kirim bertahap ya.")
    
    await callback.message.answer(text, reply_markup=kb, disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(F.data == "ch_add:start")
async def process_ch_add_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(InputChannelState.waiting_for_data)
    text = (
        "📝 <b>INPUT CHANNEL BARU</b>\n\n"
        "Kirim format: <code>Email*Pass*Nama*Subs*Link</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="back_to_ch_manage")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.message(InputChannelState.waiting_for_data)
async def process_input_data(message: types.Message, state: FSMContext):
    data = message.text.split("*")
    if len(data) < 5:
        await message.answer("❌ <b>Format Salah Boss!</b>\nContoh: <code>Email*Pass*Nama*Subs*Link</code>")
        return
        
    email, password, nama, subs, link = [d.strip() for d in data[:5]]
    user_name = "PINTARBOT"
    tgl_now = db.get_now_indo()
    
    try:
        db.add_new_channel({
            'TANGGAL': tgl_now,
            'EMAIL': email, 
            'PASSWORD': password, 
            'NAMA_CHANNEL': nama, 
            'SUBSCRIBE': subs, 
            'LINK_CHANNEL': link, 
            'STATUS': 'STANDBY',
            'PENCATAT': user_name,
            'HP': None,
            'SLOT': None,
            'EDITED': f"New: {user_name} ({tgl_now})"
        })
        await message.answer(f"✅ <b>Mantap Boss!</b> <code>{nama}</code> udah masuk status STANDBY.")
        await state.clear()
        await cmd_channel_management(message, state)
    except Exception as e: 
        await message.answer(f"❌ Gagal boss: {str(e)}")

@dp.message(UpdateStatusState.waiting_for_keyword)
async def process_search_casual(message: types.Message, state: FSMContext):
    if message.text.startswith("/"): return
    data = db.find_channel(message.text)
    if not data: await message.answer("❌ Nggak ketemu boss. Keyword lain:"); return
    await state.clear(); text = f"🔍 <b>Hasil Temuan ({len(data)}):</b>\n\n"
    kb_list = []
    for ch in data:
        text += f"📌 <b>{ch['NAMA_CHANNEL']}</b>\n📧 {ch['EMAIL']}\n📊 Status: {ch['STATUS']}\n\n"
        kb_list.append([InlineKeyboardButton(text=f"📂 Detail: {ch['NAMA_CHANNEL']}", callback_data=f"ch_view:{ch['id']}")])
    kb_list.append([InlineKeyboardButton(text="⬅️ Kembali", callback_data="ch_rekap:start")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))

@dp.callback_query(F.data.startswith("ch_view:"))
async def process_ch_detail_view(callback: types.CallbackQuery):
    ch_id = callback.data.split(":")[1]
    ch = db.get_channel_by_id(ch_id)
    if not ch: await callback.answer("❌ Datanya raib boss!"); return
    text = f"📄 <b>DETAIL: {ch['NAMA_CHANNEL']}</b>\n━━━━━━━━━━━━━━━\n📧 Email: <code>{ch['EMAIL']}</code>\n🔑 Pass: <code>{ch['PASSWORD']}</code>\n📊 Subs: {ch.get('SUBSCRIBE', 0)}\n📍 Status: {ch['STATUS']}\n📱 HP: {ch.get('HP', '-')}\n🔗 <a href='{ch['LINK_CHANNEL']}'>Link Channel</a>\n━━━━━━━━━━━━━━━"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 PROSES", callback_data=f"ch_set:{ch_id}:PROSES"),
         InlineKeyboardButton(text="🟡 STANDBY", callback_data=f"ch_set:{ch_id}:STANDBY")],
        [InlineKeyboardButton(text="💰 SOLD", callback_data=f"ch_set:{ch_id}:SOLD"),
         InlineKeyboardButton(text="🔴 BUSUK", callback_data=f"ch_set:{ch_id}:BUSUK")],
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="ch_rekap:start")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True); await callback.answer()

# --- AUDIT & QUICK REPLACE ---

@dp.callback_query(F.data == "audit_menu:start")
async def cmd_audit_menu_casual(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Audit Channel Proses", callback_data="audit:PROSES")],
        [InlineKeyboardButton(text="🟡 Audit Channel Standby", callback_data="audit:STANDBY")],
        [InlineKeyboardButton(text="💰 Cek Channel Siap Jual", callback_data="list:READY_TO_SELL:0")],
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="back_to_ch_manage")]
    ])
    await callback.message.edit_text("🔎 <b>MENU AUDIT</b>\n\nMau gue cekin yang statusnya apa nih? Biar ketauan mana yang masih seger mana yang udah busuk. 😂", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("audit:"))
async def process_audit_mass(callback: types.CallbackQuery):
    action = callback.data.split(":")[1]
    if action == "view_siap_jual":
        await process_view_siap_jual_realtime(callback)
        return
    
    # Message awal progres
    status_msg = await callback.message.edit_text(f"🚀 <b>MEMULAI AUDIT {action}...</b>\n\n{get_progress_bar(0, 100)}\n<i>Sabar ya boss, mesin lagi dipanasin!</i>")
    await callback.answer()
    await cmd_audit_all_casual(callback.message, action, user_id=callback.from_user.id, status_msg=status_msg)

async def cmd_audit_all_casual(message: types.Message, status_filter, user_id, status_msg=None):
    try:
        targets = db.get_audit_targets(status_filter)
        total = len(targets)
        if not targets: 
            if status_msg: await status_msg.edit_text("📭 Nggak ada akun boss.")
            else: await message.answer("📭 Nggak ada akun boss.")
            return
            
        findings_data = []; pending_changes = []
        batch_size = 5 # Kita proses per 5 akun biar update bar-nya enak
        
        for i in range(0, total, batch_size):
            batch = targets[i:i+batch_size]
            current_count = min(i + batch_size, total)
            
            # Update Bar
            if status_msg:
                await status_msg.edit_text(
                    f"🚀 <b>LAGI AUDIT {status_filter}...</b>\n\n"
                    f"{get_progress_bar(current_count, total)}\n"
                    f"<i>Memproses {current_count} dari {total} akun...</i>"
                )
            
            batch_urls = [ch['LINK_CHANNEL'] for ch in batch if ch.get('LINK_CHANNEL')]
            bulk_results = scraper.scrape_youtube_channels_bulk(batch_urls)
            
            for ch in batch:
                url = ch.get('LINK_CHANNEL', ''); res = bulk_results.get(url, {'subs': 0, 'status': 'ERROR'})
                if res['status'] == 'ERROR': continue
                
                subs_lama = int(str(ch.get('SUBSCRIBE', '0')).replace(".","").replace(",",""))
                subs_baru = res['subs'] if not res.get('hidden') else subs_lama
                
                # Logic Busuk Baru
                is_busuk = False; is_mau_busuk = False; b_reason = ""; views = res.get('views', [])
                if views:
                    v1 = views[0]
                    v2 = views[1] if len(views) > 1 else 999
                    
                    if v1 < 5:
                        is_busuk = True; b_reason = "View < 5"
                    elif v1 < 100 and v2 < 100:
                        is_busuk = True; b_reason = "2 Video < 100"
                    elif 6 <= v1 <= 20:
                        is_mau_busuk = True; b_reason = "MAU BUSUK"
                        
                is_sus = res['status'] == 'SUSPEND'
                
                # Data buat summary & update
                findings_data.append({'ch':ch, 'res':res, 'is_busuk':is_busuk, 'is_mau_busuk':is_mau_busuk, 'is_sus':is_sus, 'subs_lama':subs_lama, 'subs_baru':subs_baru, 'b_reason':b_reason})
                
                # Koleksi data buat update subs nanti
                if subs_baru != subs_lama:
                    pending_changes.append({'id':ch['id'], 'subs_baru':subs_baru})
            
            # Koleksi data buat detail busuk/suspend
            if is_busuk or is_sus:
                # Kita pake store terpisah buat detail eksekusi
                pass 

        def hp_sort_key(item):
            nums = re.findall(r'\d+', str(item['ch'].get('HP', '999')))
            return int(nums[0]) if nums else 999
        findings_data.sort(key=hp_sort_key)
        
        # Hitung Summary
        count_naik = len([f for f in findings_data if not f['is_sus'] and not f['is_busuk'] and f['subs_baru'] > f['subs_lama']])
        count_busuk = len([f for f in findings_data if f['is_busuk']])
        count_mau_busuk = len([f for f in findings_data if f['is_mau_busuk']])
        count_sus = len([f for f in findings_data if f['is_sus']])
        
        # --- AUTO UPDATE DATABASE (SUBSCRIBE) ---
        update_count = 0
        for f in findings_data:
            try:
                db.supabase.table('Channel_Pintar').update({'SUBSCRIBE': f['subs_baru']}).eq('id', f['ch']['id']).execute()
                update_count += 1
            except: continue

        # --- TAMPILKAN SUMMARY DASHBOARD ---
        summary = (
            f"📊 <b>DASHBOARD AUDIT: {status_filter}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"✅ Total Diaudit: <b>{total} Akun</b>\n"
            f"🚀 Akun Naik: <b>{count_naik}</b>\n"
            f"🥀 Akun Busuk: <b>{count_busuk}</b>\n"
            f"🟡 Mau Busuk: <b>{count_mau_busuk}</b>\n"
            f"⛔ Akun Suspend: <b>{count_sus}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔄 <b>Status DB:</b> Berhasil sinkron <b>{update_count}</b> data subscribe terbaru! ✨"
        )
        
        # Simpan data buat tombol eksekusi detail & navigasi balik
        pending_audit_store[user_id] = {
            'naik_list': [f for f in findings_data if f['subs_baru'] > f['subs_lama']],
            'busuk_list': [f for f in findings_data if f['is_busuk']],
            'mau_busuk_list': [f for f in findings_data if f['is_mau_busuk']],
            'suspend_list': [f for f in findings_data if f['is_sus']]
        }
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Detail Naik", callback_data="audit_detail:NAIK"),
             InlineKeyboardButton(text="🟡 Detail Mau Busuk", callback_data="audit_detail:MAU_BUSUK")],
            [InlineKeyboardButton(text="🥀 Detail Busuk", callback_data="audit_detail:BUSUK"),
             InlineKeyboardButton(text="⛔ Detail Suspend", callback_data="audit_detail:SUSPEND")],
            [InlineKeyboardButton(text="⬅️ Kembali", callback_data="back_to_ch_manage")]
        ])
        
        pending_audit_store[user_id]['summary_text'] = summary
        pending_audit_store[user_id]['summary_kb'] = kb
            
        await message.answer(summary, reply_markup=kb)
        
        # Hapus progress bar biar gak nyampah
        try: await status_msg.delete()
        except: pass
    except Exception as e: await message.answer(f"❌ Error Audit: {str(e)}")

@dp.callback_query(F.data.startswith("audit_detail:"))
async def process_view_audit_specific_details(callback: types.CallbackQuery):
    mode = callback.data.split(":")[1] # NAIK, BUSUK, MAU_BUSUK, SUSPEND
    data = pending_audit_store.get(callback.from_user.id)
    if not data: await callback.answer("⚠️ Data basi boss."); return
    
    key_map = {
        'NAIK': 'naik_list',
        'BUSUK': 'busuk_list',
        'MAU_BUSUK': 'mau_busuk_list',
        'SUSPEND': 'suspend_list'
    }
    items = data.get(key_map.get(mode, ''))
    if not items: await callback.answer(f"📭 Nggak ada data {mode} boss."); return
    
    text = f"🔍 <b>DETAIL AKUN {mode}</b>\n━━━━━━━━━━━━━━━\n\n"
    kb_list = []
    
    # Sortir by HP
    items.sort(key=lambda x: int(re.findall(r'\d+', str(x['ch'].get('HP','999')))[0]) if re.findall(r'\d+', str(x['ch'].get('HP',''))) else 999)

    for f in items:
        hp = html.escape(str(f['ch'].get('HP', '-')))
        nama = html.escape(str(f['ch']['NAMA_CHANNEL']))
        email = html.escape(str(f['ch']['EMAIL']))
        link = f['ch'].get('LINK_CHANNEL', '#')
        baru = f['subs_baru']
        
        if mode in ['NAIK', 'MAU_BUSUK']:
            entry = (
                f"📱 <b>HP {hp}</b> | <b>{nama}</b>\n"
                f"📊 Subs: <b>{baru}</b>\n"
                f"🔗 <a href='{link}'>Link Channel</a>\n\n"
            )
        else:
            entry = f"📱 <b>HP {hp}</b> > {nama}\n📧 {email}\n⚠️ Status: {mode} | {f['subs_lama']} ➡️ {baru}\n\n"
            
        text += entry
        
    if mode in ['BUSUK', 'SUSPEND']:
        kb_list.append([
            InlineKeyboardButton(text=f"💀 Ganti Semua Akun {mode} Sekarang!", callback_data=f"audit_bulk_replace:{mode}"),
        ])
            
    kb_list.append([InlineKeyboardButton(text="⬅️ Kembali ke Audit", callback_data="back_to_audit_summary")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list), disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(F.data.startswith("audit_bulk_replace:"))
async def process_audit_bulk_replace(callback: types.CallbackQuery):
    mode = callback.data.split(":")[1]
    data = pending_audit_store.get(callback.from_user.id)
    if not data: await callback.answer("⚠️ Data basi boss."); return
    
    items = data['busuk_list'] if mode == 'BUSUK' else data['suspend_list']
    if not items: await callback.answer("📭 Gak ada akun buat diganti boss."); return
    
    await callback.message.answer(f"⚔️ <b>EKSEKUSI MASSAL DIMULAI!</b>\nMarking <b>{len(items)}</b> akun ke status <b>{mode}</b>...")
    
    hp_queue = []
    user_name = "PINTARBOT"
    for f in items:
        try:
            db.update_audit_result(f['ch']['id'], 0, mode, user_name)
            hp_queue.append(str(f['ch'].get('HP', '-')))
        except: continue
        
    # Urutkan HP biar rapi gantinya
    hp_queue = sorted(list(set(hp_queue)), key=lambda x: int(re.findall(r'\d+', x)[0]) if re.findall(r'\d+', x) else 999)
    
    # Simpan antrean di memori
    pending_audit_store[callback.from_user.id]['replacement_queue'] = hp_queue
    pending_audit_store[callback.from_user.id]['audit_mode'] = mode
    
    await callback.message.answer(f"✅ <b>BERES BOSS!</b>\nSekarang HP yang kosong ada: <b>{', '.join(hp_queue)}</b>.\n\nKita isi satu-satu ya! Siap?")
    await trigger_next_queue_item(callback.message, callback.from_user.id)
    await callback.answer()

async def trigger_next_queue_item(message: types.Message, user_id: int):
    data = pending_audit_store.get(user_id)
    if not data or not data.get('replacement_queue'):
        await message.answer("🏁 <b>MANTAP BOSS!</b>\nSemua antrean ganti akun udah beres dikerjain. HP lu sekarang full semua! 📱✨")
        return
    
    hp_target = data['replacement_queue'].pop(0) # Ambil satu dari depan
    ch_new = db.get_one_standby()
    
    if not ch_new:
        await message.answer(f"⚠️ <b>STOK STANDBY HABIS!</b>\nGue mau ganti buat <b>HP {hp_target}</b> tapi gudang kosong boss. Antrean gue stop ya.")
        return
        
    slot_session_store[user_id] = {'ch': ch_new, 'target_hp': hp_target, 'audit_mode': data['audit_mode']}
    
    text = (
        f"📱 <b>ANTREAN GANTI AKUN: HP {hp_target}</b>\n"
        f"Sisa antrean: <b>{len(data['replacement_queue'])} HP</b> lagi.\n\n"
        f"Silakan login di HP {hp_target} pake akun ini:\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📧 Email: <code>{ch_new['EMAIL']}</code>\n"
        f"🔑 Pass: <code>{ch_new['PASSWORD']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ <b>Hasilnya gimana boss?</b>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Berhasil Login", callback_data="slot_action:success")],
        [InlineKeyboardButton(text="❌ Akun Standby Sakit", callback_data=f"slot_quick:{hp_target}")],
        [InlineKeyboardButton(text="🏠 Berhenti Dulu", callback_data="back_to_ch_manage")]
    ])
    
    await message.answer(text, reply_markup=kb, disable_web_page_preview=True)

@dp.callback_query(F.data == "slot_action:skip_queue")
async def process_skip_queue(callback: types.CallbackQuery):
    await callback.message.edit_text("⏭️ <b>HP dilewati...</b> Lanjut ke antrean berikutnya."); await callback.answer()
    await trigger_next_queue_item(callback.message, callback.from_user.id)

@dp.callback_query(F.data.startswith("aud_ask:"))
async def process_audit_confirm_ask(callback: types.CallbackQuery):
    _, mode, ch_id = callback.data.split(":")
    ch = db.get_channel_by_id(int(ch_id))
    hp = html.escape(str(ch.get('HP', '-')))
    
    text = (
        f"⚠️ <b>KONFIRMASI EKSEKUSI</b>\n\n"
        f"Boss beneran mau ganti akun di <b>HP {hp}</b> jadi <b>{mode}</b>?\n"
        f"Akun lama bakal langsung dibuang ke gudang {mode} lho."
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Ya, Ganti Jadi {mode}!", callback_data=f"aud_single:{mode}:{ch_id}")],
        [InlineKeyboardButton(text="❌ Batal / Kembali ke List", callback_data=f"audit_detail:{mode}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "hp:menu")
async def process_view_hp_info(callback: types.CallbackQuery):
    all_hp = db.get_all_hp_full()
    if not all_hp: await callback.answer("📭 Data HP masih kosong boss."); return
    
    now = datetime.now()
    mon_data = []
    for hp in all_hp:
        try:
            m_str = str(hp.get('MASA_AKTIF', '01/01/2000'))
            if '-' in m_str:
                target = datetime.strptime(m_str, "%Y-%m-%d")
            else:
                target = datetime.strptime(m_str, "%d/%m/%Y")
            diff = (target - now).days
        except:
            diff = 999 
            
        hp['sisa'] = diff
        mon_data.append(hp)
        
    def mon_sort_key(x):
        priority = 0 if x['sisa'] < 3 else 1
        nums = re.findall(r'\d+', str(x['NAMA_HP']))
        name_num = int(nums[0]) if nums else 999
        return (priority, name_num)
        
    mon_data.sort(key=mon_sort_key)
    
    text = "📱 <b>MONITORING KARTU HP</b>\n━━━━━━━━━━━━━━━\n\n"
    kb_list = []
    
    for h in mon_data:
        label = html.escape(str(h['NAMA_HP']))
        nomer = html.escape(str(h.get('NOMOR_HP', '-')))
        aktif = h.get('MASA_AKTIF', '-')
        sisa = h['sisa']
        
        if sisa <= 3:
            header = f"🆘 <b>{label} (‼️ SEGERA ISI)</b>"
            kb_list.append([InlineKeyboardButton(text=f"📅 Update Masa Aktif {label}", callback_data=f"hp_upd:{h['id']}")])
        else:
            header = f"📱 <b>{label}</b>"
            
        text += (
            f"{header}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"  📞 <code>Nomer :</code> <code>{nomer}</code>\n"
            f"  ⏳ <code>Exp   :</code> <code>{aktif}</code>\n"
            f"  📅 <code>Sisa  :</code> <b>{sisa} Hari</b>\n"
            f"━━━━━━━━━━━━━━━\n\n"
        )
        
    kb_list.append([InlineKeyboardButton(text="⬅️ Kembali", callback_data="oper_menu:back")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))
    await callback.answer()

@dp.callback_query(F.data.startswith("hp_upd:"))
async def process_hp_update_ask(callback: types.CallbackQuery, state: FSMContext):
    hp_id = callback.data.split(":")[1]
    hp = db.get_hp_by_id(hp_id)
    await state.update_data(hp_id=hp_id)
    await state.set_state(UpdateHPState.waiting_for_date)
    
    text = (
        f"📅 <b>UPDATE MASA AKTIF: {hp['NAMA_HP']}</b>\n\n"
        f"Sekarang: <code>{hp['MASA_AKTIF']}</code>\n"
        f"Kirim tanggal baru boss (Format: <b>DD/MM/YYYY</b>)\n"
        f"Contoh: <code>31/12/2026</code>"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Batal", callback_data="hp:menu")]]))
    await callback.answer()

@dp.message(UpdateHPState.waiting_for_date)
async def process_hp_date_save(message: types.Message, state: FSMContext):
    # Regex buat DD/MM/YYYY
    if not re.match(r'\d{2}/\d{2}/\d{4}', message.text):
        await message.answer("❌ <b>Format Salah Boss!</b>\nGunakan DD/MM/YYYY (Contoh: 31/12/2026)"); return
        
    data = await state.get_data()
    try:
        db.update_hp_masa_aktif(data['hp_id'], message.text)
        await message.answer(f"✅ <b>BERES BOSS!</b>\nMasa aktif HP berhasil diupdate ke <b>{message.text}</b>.")
        await state.clear()
        # Munculkan menu operasional lagi
        await cmd_operasional_menu(message, state)
    except Exception as e: await message.answer(f"❌ Gagal update: {str(e)}")

@dp.callback_query(F.data == "oper_menu:back")
async def process_oper_menu_back(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Info HP", callback_data="hp:menu")],
        [InlineKeyboardButton(text="📅 Jadwal Harian", callback_data="sched:view")],
        [InlineKeyboardButton(text="🏠 Menu Utama", callback_data="back_to_main_menu")]
    ])
    await callback.message.edit_text("⚙️ <b>Menu operasional udah kebuka.</b>\nMau ngecek apa hari ini boss?", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "sched:view")
async def process_view_schedule(callback: types.CallbackQuery):
    channels = db.get_audit_targets('PROSES')
    if not channels:
        await callback.answer("📭 Belum ada akun PROSES boss."); return
        
    # Grouping by HP
    hp_groups = {}
    for ch in channels:
        hp = str(ch.get('HP', '-'))
        if hp not in hp_groups: hp_groups[hp] = []
        hp_groups[hp].append(ch)
        
    # Sorting HP Labels (Natural Sort)
    hp_labels = sorted(hp_groups.keys(), key=lambda x: [int(t) if t.isdigit() else t.lower() for t in re.split('([0-9]+)', x)])
    
    # Real-time Date Header
    days_id = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    now = datetime.now()
    header_date = f"🗓 <b>{days_id[now.weekday()]}, {now.strftime('%d %B %Y')}</b>"
    
    text = (
        f"📅 <b>JADWAL UPLOAD HARIAN</b>\n"
        f"{header_date}\n"
        f"━━━━━━━━━━━━━━━\n\n"
    )
    
    for label in hp_labels:
        ch_list = hp_groups[label]
        
        text += f"📱 <b>HP {label}</b>\n━━━━━━━━━━━━━━━\n"
        
        # Mapping icon ke kolom
        slot_icons = {"PAGI": "🌅", "SIANG": "☀️", "SORE": "🌆"}
        
        # Kumpulin jadwal yang ada jamnya di HP ini
        hp_tasks = []
        for ch in ch_list:
            for col, icon in slot_icons.items():
                jam = str(ch.get(col, 'EMPTY'))
                if jam != 'EMPTY' and jam != 'null':
                    hp_tasks.append({
                        'jam': jam,
                        'icon': icon,
                        'name': html.escape(str(ch['NAMA_CHANNEL']))
                    })
        
        # Urutkan berdasarkan jam
        hp_tasks.sort(key=lambda x: x['jam'])
        
        if not hp_tasks:
            text += "<i>(Belum ada jadwal upload)</i>\n"
        else:
            for task in hp_tasks:
                text += f"{task['icon']} <code>{task['jam']}</code> » <b>{task['name']}</b>\n"
        
        text += "━━━━━━━━━━━━━━━\n\n"
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Buat Jadwal", callback_data="sched:bulk_create")],
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="oper_menu:back")]
    ])
    
    # Handle long message
    if len(text) > 4000:
        await callback.message.answer(text[:4000])
        await callback.message.answer(text[4000:], reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "sched:bulk_create")
async def process_sched_bulk_create(callback: types.CallbackQuery):
    await callback.message.answer("⚔️ <b>MEMPROSES JADWAL ESTAFET...</b>\nMenghitung 27 slot & mengatur lompatan istirahat. Sabar boss!")
    
    channels = db.get_audit_targets('PROSES')
    if not channels:
        await callback.message.answer("📭 Gak ada akun PROSES buat dijadwalin boss."); return
        
    # 1. Grouping HPs by (HP-1) % 9
    groups = {i: {} for i in range(9)}
    for ch in channels:
        try:
            hp_label = str(ch.get('HP', '0'))
            hp_num = int(re.findall(r'\d+', hp_label)[0])
            g_idx = (hp_num - 1) % 9
            if hp_label not in groups[g_idx]: groups[g_idx][hp_label] = []
            groups[g_idx][hp_label].append(ch)
        except: continue
        
    # 2. Pick Daily Random Start Group & Shuffle internal accounts
    # Pake seed harian biar konsisten satu hari tapi beda tiap hari
    import random
    seed_val = datetime.now().strftime('%Y%m%d')
    random.seed(seed_val)
    
    start_group_idx = random.randint(0, 8)
    group_order = [(start_group_idx + i) % 9 for i in range(9)]
    
    # Shuffle internal accounts for each HP
    for g in range(9):
        for hp_label in groups[g]:
            random.shuffle(groups[g][hp_label])
            
    # 3. Generate 27 Time Slots (Jumping break 11:31 - 12:44)
    current_time = datetime.strptime("08:15", "%H:%M")
    break_start = datetime.strptime("11:30", "%H:%M")
    break_resume = datetime.strptime("12:45", "%H:%M")
    
    time_slots = []
    for _ in range(27):
        time_slots.append(current_time.strftime("%H:%M"))
        current_time += timedelta(minutes=15)
        if current_time > break_start and current_time < break_resume:
            current_time = break_resume
            
    # 4. Assign Times (Relay style: All Group's Slot 1, then Slot 2, then Slot 3)
    updates_count = 0
    time_idx = 0
    
    # Loop 3 slots (Pagi, Siang, Sore)
    for slot_idx in range(3):
        # Loop each group in rotated order
        for g_idx in group_order:
            if time_idx >= len(time_slots): break
            target_time = time_slots[time_idx]
            time_idx += 1
            
            # Update all HPs in this group for this specific slot index
            for hp_label, ch_list in groups[g_idx].items():
                if slot_idx < len(ch_list):
                    ch = ch_list[slot_idx]
                    # Reset all slots and set the target one
                    update_data = {'PAGI': 'EMPTY', 'SIANG': 'EMPTY', 'SORE': 'EMPTY'}
                    col = ['PAGI', 'SIANG', 'SORE'][slot_idx]
                    update_data[col] = target_time
                    
                    try:
                        db.supabase.table('Channel_Pintar').update(update_data).eq('id', ch['id']).execute()
                        updates_count += 1
                    except: continue
                
    await callback.message.answer(f"✅ <b>ESTAFET BERES BOSS!</b>\nBerhasil menjadwalkan <b>{updates_count}</b> channel.\nJam 11:31-12:44 otomatis dilewati (Istirahat). 😴✨")
    await process_view_schedule(callback)
async def process_single_audit_upd(callback: types.CallbackQuery):
    _, mode, ch_id = callback.data.split(":")
    if mode == "SKIP": 
        await callback.answer("Okelah boss, kita skip."); return
        
    try:
        # 1. Tandai akun lama jadi BUSUK/SUSPEND
        ch_old = db.get_channel_by_id(int(ch_id))
        hp_target = html.escape(str(ch_old.get('HP', '-')))
        user_name = "PINTARBOT"
        db.update_audit_result(int(ch_id), 0, mode, user_name)
        
        await callback.answer(f"✅ Akun lama di {hp_target} sudah jadi {mode}!", show_alert=True)
        
        # 2. Langsung cari pengganti (Quick Replace)
        ch_new = db.get_one_standby()
        
        # --- UPDATE LIST TEMUAN: Hapus yang udah diproses dari memori ---
        if callback.from_user.id in pending_audit_store:
            store = pending_audit_store[callback.from_user.id]
            mode_key = 'busuk_list' if mode == 'BUSUK' else 'suspend_list'
            if mode_key in store:
                store[mode_key] = [item for item in store[mode_key] if int(item['ch']['id']) != int(ch_id)]
        
        if not ch_new:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔍 Kembali ke List Temuan", callback_data=f"audit_detail:{mode}")]])
            await callback.message.edit_text(f"💀 <b>AKUN LAMA DIBUANG!</b>\nStatus di <b>{hp_target}</b> sekarang <b>{mode}</b>.\n\n⚠️ <b>STOK STANDBY HABIS!</b>\nGue nggak nemu akun pengganti di gudang boss.", reply_markup=kb)
            return
            
        slot_session_store[callback.from_user.id] = {'ch': ch_new, 'target_hp': hp_target, 'audit_mode': mode}
        
        text = (
            f"💀 <b>AKUN LAMA DIBUANG!</b>\n"
            f"Status akun di <b>{hp_target}</b> sekarang <b>{mode}</b>.\n\n"
            f"🔄 <b>GANTI PENGGANTI (STANDBY)</b>\n"
            f"Silakan login di HP {hp_target} pake akun ini:\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📧 Email: <code>{ch_new['EMAIL']}</code>\n"
            f"🔑 Pass: <code>{ch_new['PASSWORD']}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ <b>Gimana hasilnya boss?</b>"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Berhasil Login", callback_data="slot_action:success")],
            [InlineKeyboardButton(text="❌ Akun Standby Sakit", callback_data=f"slot_quick:{hp_target}")],
            [InlineKeyboardButton(text="⬅️ Kembali ke List", callback_data=f"audit_detail:{mode}")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        
    except Exception as e: 
        await callback.answer(f"❌ Gagal eksekusi: {str(e)}")

@dp.callback_query(F.data.startswith("slot_quick:"))
async def process_slot_quick(callback: types.CallbackQuery):
    hp_target = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Ambil list ID yang udah dicoba biar nggak dapet yang itu lagi
    session = slot_session_store.get(user_id, {})
    tried_ids = session.get('tried_ids', [])
    if session.get('ch'):
        tried_ids.append(session['ch']['id'])

    # Cari standby baru tapi skip yang udah dicoba
    ch = db.get_one_standby(exclude_ids=tried_ids)
    if not ch: 
        await callback.message.edit_text("📭 <b>STOK STANDBY HABIS BOSS!</b>\nGak ada akun lain lagi di gudang."); return
        
    slot_session_store[user_id] = {
        'ch': ch, 
        'target_hp': hp_target, 
        'audit_mode': session.get('audit_mode', 'BUSUK'),
        'tried_ids': tried_ids
    }
    
    text = (
        f"📦 <b>CARI PENGGANTI LAIN ({hp_target})</b>\n"
        f"Akun sebelumnya di-skip, ini akun standby lainnya boss:\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📧 Email: <code>{ch['EMAIL']}</code>\n"
        f"🔑 Pass: <code>{ch['PASSWORD']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✍️ <b>Silakan coba login lagi boss.</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Berhasil Login", callback_data="slot_action:success")],
        [InlineKeyboardButton(text="❌ Akun Ini Sakit Juga", callback_data=f"slot_quick:{hp_target}")],
        [InlineKeyboardButton(text="🏠 Batal", callback_data="back_to_ch_manage")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True); await callback.answer()

@dp.callback_query(F.data == "back_to_audit_summary")
async def process_back_to_audit_summary(callback: types.CallbackQuery):
    data = pending_audit_store.get(callback.from_user.id)
    if not data or 'summary_text' not in data:
        await callback.answer("⚠️ Dashboard kadaluarsa boss."); return
    await callback.message.edit_text(data['summary_text'], reply_markup=data['summary_kb'])
    await callback.answer()

@dp.callback_query(F.data == "slot_action:success")
async def process_slot_success(callback: types.CallbackQuery):
    session = slot_session_store.get(callback.from_user.id)
    if not session: await callback.answer("⚠️ Sesi basi boss."); return
    
    try:
        # 1. Update ke PROSES dan pasang label HP
        user_name = "PINTARBOT"
        db.move_standby_to_proses(session['ch']['id'], session['target_hp'], user_name)
        await callback.answer("Berhasil sinkron!")
        
        await callback.message.edit_text(f"🚀 <b>MANTAP BOSS!</b>\nAkun <code>{session['ch']['EMAIL']}</code> sekarang sudah di <b>{session['target_hp']}</b>.\nData sinkron 100%! ✅")
        
        # 2. Cek apakah ada antrean
        data = pending_audit_store.get(callback.from_user.id)
        if data and data.get('replacement_queue'):
            # Kasih jeda dikit biar user bisa baca suksesnya
            await callback.message.answer("⏳ <b>Lanjut ke antrean berikutnya...</b>")
            await trigger_next_queue_item(callback.message, callback.from_user.id)
        else:
            mode = session.get('audit_mode', 'BUSUK')
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Lanjut Beresin List Temuan", callback_data=f"audit_detail:{mode}")],
                [InlineKeyboardButton(text="🏠 Menu Utama", callback_data="back_to_main_menu")]
            ])
            await callback.message.answer("🏁 <b>ANTREAN BERES BOSS!</b>", reply_markup=kb)
            
    except Exception as e:
        await callback.message.answer(f"❌ Gagal sinkron boss: {str(e)}")

# --- OTHER ---

@dp.callback_query(F.data.startswith("ch_set:"))
async def process_ch_set(callback: types.CallbackQuery):
    _, ch_id, new_st = callback.data.split(":")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Ya!", callback_data=f"ch_conf:{ch_id}:{new_st}")],[InlineKeyboardButton(text="❌ Batal", callback_data=f"ch_view:{ch_id}")]])
    await callback.message.edit_text(f"⚠️ Ganti ke <b>{new_st}</b> boss?", reply_markup=kb); await callback.answer()

@dp.callback_query(F.data.startswith("ch_conf:"))
async def process_ch_conf(callback: types.CallbackQuery):
    _, ch_id, new_st = callback.data.split(":")
    user_name = "PINTARBOT"
    db.update_channel_status(ch_id, new_st, user_name); await callback.answer(f"✅ Jadi {new_st}!", show_alert=True)
    # Balik ke detail
    ch = db.get_channel_by_id(ch_id)
    text = f"📄 <b>DETAIL: {ch['NAMA_CHANNEL']}</b>\n━━━━━━━━━━━━━━━\n📧 Email: <code>{ch['EMAIL']}</code>\n🔑 Pass: <code>{ch['PASSWORD']}</code>\n📊 Subs: {ch.get('SUBSCRIBE', 0)}\n📍 Status: {ch['STATUS']}\n📱 HP: {ch.get('HP', '-')}\n🔗 <a href='{ch['LINK_CHANNEL']}'>Link Channel</a>\n━━━━━━━━━━━━━━━"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🟢 PROSES", callback_data=f"ch_set:{ch_id}:PROSES"), InlineKeyboardButton(text="🟡 STANDBY", callback_data=f"ch_set:{ch_id}:STANDBY")],[InlineKeyboardButton(text="💰 SOLD", callback_data=f"ch_set:{ch_id}:SOLD"), InlineKeyboardButton(text="🔴 BUSUK", callback_data=f"ch_set:{ch_id}:BUSUK")],[InlineKeyboardButton(text="⬅️ Kembali", callback_data="ch_rekap:start")]])
    await callback.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)

@dp.callback_query(F.data == "hp:menu")
async def cmd_hp_menu(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📜 Liat Semua HP", callback_data="hp:list")],[InlineKeyboardButton(text="🏠 Menu Utama", callback_data="back_to_main_menu")]])
    await callback.message.edit_text("📱 <b>MANAGEMENT HP</b>", reply_markup=kb); await callback.answer()

@dp.callback_query(F.data == "hp:list")
async def process_hp_list(callback: types.CallbackQuery):
    hp_list = db.get_all_hp_full(); text = "📱 <b>DAFTAR HP</b>\n\n"
    for hp in hp_list: text += f"▪️ <b>{hp['NAMA_HP']}</b> | {hp.get('NOMOR_HP','-')}\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="hp:menu")]])
    await callback.message.edit_text(text, reply_markup=kb); await callback.answer()

@dp.message()
async def handle_unknown_message_casual(message: types.Message):
    if not is_authorized(message.from_user.id): return
    kb = get_main_keyboard(message.from_user.id)
    await message.answer(
        "🤔 <b>Aduh boss, gue gagal paham...</b>\n\n"
        "Lu barusan ngetik apa tuh? Gue nggak ngerti maksudnya. Balik ke menu utama aja yuk biar gue bisa bantuin kerja lagi!", 
        reply_markup=kb
    )

# --- WEB SERVER FOR RENDER (ANTI-SLEEP) ---
async def handle_root(request):
    return web.Response(text="PintarBot is Online! 🚀")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render biasanya ngasih PORT lewat environment variable
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server nangkring di port {port}")

async def main():
    print("PintarBot Buddy Mode PREMIUM is Online!")
    # Jalankan bot dan web server barengan
    await asyncio.gather(
        dp.start_polling(bot),
        start_web_server()
    )

if __name__ == "__main__":
    asyncio.run(main())
