import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(
    page_title="WhatsApp Blast Dashboard",
    page_icon="📲",
    layout="wide"
)

# Header App
st.title("📲 WhatsApp Broadcast & Blast Tool")
st.caption("Aplikasi pengiriman pesan massal terintegrasi menggunakan Streamlit & Python API")

# Sidebar: Pengaturan API / Gateway
st.sidebar.header("⚙️ Konfigurasi API Gateway")
api_provider = st.sidebar.selectbox(
    "Pilih Provider API",
    ["Green-API", "Custom API HTTP POST"]
)

instance_id = st.sidebar.text_input("Instance ID / ID Akun", type="password")
api_token = st.sidebar.text_input("API Token / Key", type="password")

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Pengaturan Anti-Banned")
delay_time = st.sidebar.slider("Jeda Antar Pesan (detik)", min_value=3, max_value=30, value=7)

# Main Layout
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Unggah Daftar Kontak (CSV / Excel)")
    uploaded_file = st.file_uploader("Upload file CSV atau XLSX", type=["csv", "xlsx"])
    
    df = None
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            # Kolom harus dibersihkan
            df.columns = [c.strip().lower() for c in df.columns]
            
            st.success(f"Berhasil memuat {len(df)} kontak!")
            st.dataframe(df.head(5), use_container_width=True)
            
        except Exception as e:
            st.error(f"Gagal membaca file: {e}")

    st.subheader("2. Template Pesan")
    message_template = st.text_area(
        "Tulis Pesan (Gunakan nama kolom sebagai variabel, misal: {nama}, {no_hp})",
        height=180,
        placeholder="Halo {nama},\n\nTerima kasih telah berbelanja di toko kami. Berikut info promo..."
    )

with col2:
    st.subheader("3. Pratinjau Pesan (Preview)")
    if df is not None and message_template and not df.empty:
        sample_row = df.iloc[0].to_dict()
        try:
            preview_text = message_template.format(**sample_row)
            st.info("Contoh tampilan pesan ke kontak pertama:")
            st.text_area("Pratinjau", value=preview_text, height=180, disabled=True)
        except KeyError as e:
            st.warning(f"Variabel {{{e.args[0]}}} di template tidak ditemukan pada kolom file!")
    else:
        st.write("Unggah file dan tulis template pesan untuk melihat pratinjau.")

# Fungsi Pengiriman Pesan
def send_wa_message(instance, token, phone, text):
    # Formating Nomor HP (Hapus tanda + atau spasi, ubah '08' jadi '628')
    phone = str(phone).strip().replace("+", "").replace("-", "").replace(" ", "")
    if phone.startswith("0"):
        phone = "62" + phone[1:]
    if phone.endswith(".0"): # Mengatasi format float excel
        phone = phone[:-2]

    url = f"https://api.green-api.com/waInstance{instance}/sendMessage/{token}"
    payload = {
        "chatId": f"{phone}@c.us",
        "message": text
    }
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code == 200, response.text
    except Exception as e:
        return False, str(e)

# Section Tombol Eksekusi
st.markdown("---")
st.subheader("4. Eksekusi Pengiriman")

if st.button("🚀 Mulai Kirim Broadcast", type="primary"):
    if not instance_id or not api_token:
        st.error("Harap isi Instance ID dan API Token di sidebar!")
    elif df is None or df.empty:
        st.error("Harap unggah file kontak terlebih dahulu!")
    elif not message_template:
        st.error("Harap isi template pesan!")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_area = st.container()
        
        total_contacts = len(df)
        success_count = 0
        failed_count = 0
        
        for idx, row in df.iterrows():
            # Format pesan sesuai data baris
            try:
                formatted_message = message_template.format(**row.to_dict())
            except Exception as e:
                formatted_message = message_template

            phone_number = row.get('no_hp', row.get('telepon', row.get('phone', '')))
            
            status_text.text(f"Mengirim pesan ke {phone_number} ({idx+1}/{total_contacts})...")
            
            # Kirim request
            is_success, log_msg = send_wa_message(instance_id, api_token, phone_number, formatted_message)
            
            if is_success:
                success_count += 1
                log_area.caption(f"✅ [{idx+1}] Berhasil kirim ke: {phone_number}")
            else:
                failed_count += 1
                log_area.error(f"❌ [{idx+1}] Gagal kirim ke: {phone_number} | Status: {log_msg}")

            # Update progress bar
            progress_bar.progress((idx + 1) / total_contacts)
            
            # Jeda waktu (delay)
            if idx < total_contacts - 1:
                time.sleep(delay_time)

        st.success(f" Selesai! Berhasil: {success_count} | Gagal: {failed_count}")
