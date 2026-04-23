import os
import re
from datetime import datetime
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_audit_targets(status_filter='PROSES'):
    """Ambil channel buat diaudit boss!"""
    response = supabase.table('Channel_Pintar') \
        .select('*') \
        .eq('STATUS', status_filter) \
        .order('id') \
        .execute()
    return response.data

def update_audit_result(ch_id, new_subs, new_status=None):
    """Update hasil audit ke database boss!"""
    data = {
        'SUBSCRIBE': new_subs,
        'EDITED': f"Audit: PINTARBOT ({datetime.now().strftime('%d/%m/%Y %H:%M')})"
    }
    if new_status:
        data['STATUS'] = new_status
        
        # --- AUTO-ASSIGN HP JIKA PINDAH KE PROSES VIA AUDIT ---
        if new_status.upper() == 'PROSES':
            current = get_channel_by_id(ch_id)
            if not current.get('HP'):
                hp_label, slot_num = get_next_available_slot()
                if hp_label:
                    data['HP'] = hp_label
                    data['SLOT'] = slot_num

        # Jika akun mati/dijual, bersihkan HP dan SLOT
        if new_status.upper() in ['SUSPEND', 'BUSUK', 'SOLD']:
            data['HP'] = None
            data['SLOT'] = None
            
    response = supabase.table('Channel_Pintar').update(data).eq('id', ch_id).execute()
    return response.data

def update_channel_status(ch_id, status):
    """Ganti status channel boss!"""
    data = {
        'STATUS': status,
        'EDITED': f"Up: PINTARBOT ({datetime.now().strftime('%d/%m/%Y %H:%M')})"
    }
    
    # --- AUTO-ASSIGN HP JIKA PINDAH KE PROSES ---
    if status.upper() == 'PROSES':
        current = get_channel_by_id(ch_id)
        # Jika belum punya HP atau HP-nya None
        if not current.get('HP'):
            hp_label, slot_num = get_next_available_slot()
            if hp_label:
                data['HP'] = hp_label
                data['SLOT'] = slot_num
    
    # Jika akun mati/dijual, bersihkan HP dan SLOT
    if status.upper() in ['SUSPEND', 'BUSUK', 'SOLD']:
        data['HP'] = None
        data['SLOT'] = None
        
    response = supabase.table('Channel_Pintar').update(data).eq('id', ch_id).execute()
    return response.data

def get_channel_by_id(ch_id):
    """Cari info satu channel doang boss!"""
    response = supabase.table('Channel_Pintar').select('*').eq('id', ch_id).execute()
    return response.data[0] if response.data else None

def find_channel(keyword):
    """Cari channel pake keyword boss!"""
    response = supabase.table('Channel_Pintar') \
        .select('*') \
        .or_(f"EMAIL.ilike.%{keyword}%,LINK_CHANNEL.ilike.%{keyword}%") \
        .execute()
    return response.data

def add_new_channel(data):
    """Input channel baru ke database boss!"""
    response = supabase.table('Channel_Pintar').insert(data).execute()
    return response.data

def get_all_hp_labels():
    """Ambil daftar label HP boss!"""
    response = supabase.table('Data_HP').select('NAMA_HP').order('NAMA_HP').execute()
    return [item['NAMA_HP'] for item in response.data]

def get_all_hp_labels_sorted():
    """Ambil daftar label HP yang SEDANG DIPAKAI di Channel_Pintar boss!"""
    response = supabase.table('Channel_Pintar') \
        .select('HP') \
        .eq('STATUS', 'PROSES') \
        .execute()
    
    # Ambil unik dan buang yang None atau string kosong
    labels = sorted(list(set([item['HP'] for item in response.data if item['HP']])))
    
    def natural_sort_key(s):
        return [int(text) if text.isdigit() else text.lower()
                for text in re.split('([0-9]+)', str(s))]
    
    return sorted(labels, key=natural_sort_key)

def get_all_hp_full():
    """Ambil data lengkap semua HP boss!"""
    response = supabase.table('Data_HP').select('*').order('NAMA_HP').execute()
    return response.data

def get_next_available_slot():
    """Cari HP yang slotnya masih bolong (PROSES < 3) boss!"""
    hp_labels = get_all_hp_labels()
    for label in hp_labels:
        res = supabase.table('Channel_Pintar').select('id', count='exact').eq('HP', label).eq('STATUS', 'PROSES').execute()
        if res.count < 3:
            return label, res.count + 1
    return None, None

def get_one_standby(exclude_ids=None):
    """Ambil satu peluru dari stok STANDBY boss!"""
    query = supabase.table('Channel_Pintar').select('*').eq('STATUS', 'STANDBY')
    if exclude_ids:
        query = query.not_.in_('id', exclude_ids)
    response = query.order('id').limit(1).execute()
    return response.data[0] if response.data else None

def move_standby_to_proses(ch_id, hp_label):
    """Pindahin akun ke PROSES dan tag HP-nya boss!"""
    data = {
        'STATUS': 'PROSES',
        'HP': hp_label,
        'EDITED': f"Up: PINTARBOT ({datetime.now().strftime('%d/%m/%Y %H:%M')})"
    }
    response = supabase.table('Channel_Pintar').update(data).eq('id', ch_id).execute()
    return response.data

def get_channels_by_hp_list(hp_list):
    """Ambil semua channel yang ada di daftar HP tertentu boss!"""
    response = supabase.table('Channel_Pintar') \
        .select('*') \
        .in_('HP', hp_list) \
        .eq('STATUS', 'PROSES') \
        .execute()
    return response.data

def get_channels_by_status_paged(status, limit=20, offset=0):
    """Ambil daftar akun per halaman boss!"""
    response = supabase.table('Channel_Pintar') \
        .select('*') \
        .eq('STATUS', status) \
        .order('id', desc=True) \
        .range(offset, offset + limit - 1) \
        .execute()
    return response.data

def get_all_ready_to_sell():
    """Ambil akun PROSES & STANDBY yang subs-nya >= 1000 boss!"""
    response = supabase.table('Channel_Pintar') \
        .select('*') \
        .in_('STATUS', ['PROSES', 'STANDBY']) \
        .execute()
    
    ready = []
    for ch in response.data:
        try:
            # Bersihin titik/koma kalo ada, terus jadiin int
            subs_val = int(str(ch.get('SUBSCRIBE', '0')).replace('.', '').replace(',', ''))
            if subs_val >= 1000:
                ready.append(ch)
        except:
            continue
    return ready

def get_channel_stats():
    """Ngitung rekap channel kita boss! Akurat & Realtime."""
    counts = {}
    for st in ['PROSES', 'STANDBY', 'BUSUK', 'SUSPEND']:
        res = supabase.table('Channel_Pintar').select('id', count='exact').eq('STATUS', st).execute()
        counts[st] = res.count if res.count is not None else 0
    current_month = datetime.now().strftime('%m/%Y')
    res_sold = supabase.table('Channel_Pintar').select('id', count='exact').eq('STATUS', 'SOLD').ilike('EDITED', f'%{current_month}%').execute()
    counts['SOLD'] = res_sold.count if res_sold.count is not None else 0
    res_total = supabase.table('Channel_Pintar').select('id', count='exact').execute()
    counts['TOTAL'] = res_total.count if res_total.count is not None else 0
    return counts

def update_hp_masa_aktif(hp_id, new_date):
    """Update tanggal masa aktif HP boss!"""
    response = supabase.table('Data_HP').update({'MASA_AKTIF': new_date}).eq('id', hp_id).execute()
    return response.data

def get_hp_by_id(hp_id):
    """Ambil satu info HP boss!"""
    response = supabase.table('Data_HP').select('*').eq('id', hp_id).execute()
    return response.data[0] if response.data else None
def get_staff_salary_total():
    """Hitung total gaji pokok + tunjangan semua staff secara dinamis boss!"""
    res = supabase.table('Staff').select('Gaji_Pokok, Tunjangan').execute()
    total = 0
    for x in res.data:
        gp = int(str(x.get('Gaji_Pokok', 0) or 0))
        tj = int(str(x.get('Tunjangan', 0) or 0))
        total += (gp + tj)
    return total

def get_all_staff():
    """Ambil daftar semua staff boss!"""
    response = supabase.table('Staff').select('*').order('id').execute()
    return response.data

def update_staff_finance(staff_id, gp, tj):
    """Update gaji pokok & tunjangan staff boss!"""
    data = {'Gaji_Pokok': gp, 'Tunjangan': tj}
    response = supabase.table('Staff').update(data).eq('id', staff_id).execute()
    return response.data

def get_cashflow_summary():
    """Laporan Bulanan: Hitung total duit masuk, keluar, dan saldo boss!"""
    now = datetime.now()
    # Ambil awal bulan ini (Format YYYY-MM-01)
    first_day = now.replace(day=1).strftime("%Y-%m-%d")
    
    # Tarik data Arus_Kas dari awal bulan ini sampai sekarang
    res = supabase.table('Arus_Kas').select('Tipe, Nominal').gte('Tanggal', first_day).execute()
    
    masuk = sum([float(item['Nominal']) for item in res.data if str(item['Tipe']).upper() == 'PENDAPATAN'])
    keluar_operasional = sum([float(item['Nominal']) for item in res.data if str(item['Tipe']).upper() == 'PENGELUARAN'])
    
    # Gaji Staff ditarik live dari tabel Staff
    gaji_staff = get_staff_salary_total()
    
    return {
        'masuk': masuk,
        'keluar_operasional': keluar_operasional,
        'gaji_staff': gaji_staff,
        'total_keluar': keluar_operasional + gaji_staff,
        'saldo': masuk - (keluar_operasional + gaji_staff)
    }

def get_last_transactions(limit=5):
    """Tarik 5 histori transaksi terbaru boss!"""
    res = supabase.table('Arus_Kas').select('*').order('Tanggal', desc=True).order('id', desc=True).limit(limit).execute()
    return res.data
