import streamlit as st
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3
import time

# Matikan peringatan SSL insecure
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="WhatsApp Blast Dashboard",
    page_icon="📲",
    layout="wide"
)

st.title("📲 WhatsApp Broadcast & Blast Tool")
st.caption("Aplikasi pengiriman pesan massal terintegrasi")

if "is_running" not in st.session_state:
    st.session_state.is_running = False

# Sidebar Configuration
st.sidebar.header("⚙️ Konfigurasi API Gateway")
instance_id = st.sidebar.text_input("Instance ID / ID Akun", type="password")
api_token = st.sidebar.text_input("API Token / Key", type="password")

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ Pengaturan Pengiriman")
delay_time = st.sidebar.slider("Jeda Antar Pesan (detik)", min_value=3, max_value=30, value=7)
timeout_setting = st.sidebar.slider("Timeout API (detik)", min_value=15, max_value=60, value=30)

# Layout
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
            
            df.columns = [c.strip().lower() for c in df.columns]
            st.success(f"Berhasil memuat {len(df)} kontak!")
            st.dataframe(df.head(5), use_container_width=True)
        except Exception as e:
            st.error(f"Gagal membaca file: {e}")

    st.subheader("2. Link Gambar (Opsional)")
    image_url_input = st.text_input("URL Gambar (Contoh: https://i.imgur.com/vRW9gze.jpg)", placeholder="https://...")

    st.subheader("3. Template Pesan / Caption")
    message_template = st.text_area(
        "Tulis Pesan (Gunakan nama kolom sebagai variabel, misal: {nama}, {no_hp})",
        height=150,
        placeholder="Halo {nama},\n\nTerima kasih telah berbelanja..."
    )

# Otomatis perbaiki URL Imgur biasa ke direct image (.jpg)
if image_url_input:
    image_url_input = image_url_input.strip()
    if "imgur.com/" in image_url_input and not image_url_input.endswith(('.jpg', '.png', '.jpeg')):
        image_id = image_url_input.split("/")[-1]
        image_url_input = f"https://i.imgur.com/{image_id}.jpg"

with col2:
    st.subheader("4. Pratinjau Pesan (Preview)")
    if df is not None and message_template and not df.empty:
        sample_row = df.iloc[0].to_dict()
        try:
            preview_text = message_template.format(**sample_row)
            st.info("Contoh tampilan pesan ke kontak pertama:")
            if image_url_input:
                st.image(image_url_input, width=200)
            st.text_area("Pratinjau Teks", value=preview_text, height=150, disabled=True)
        except KeyError as e:
            st.warning(f"Variabel {{{e.args[0]}}} di template tidak ditemukan pada kolom file!")
    else:
        st.write("Unggah file dan tulis template pesan untuk melihat pratinjau.")

# Session HTTP khusus dengan Browser User-Agent
def get_http_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json'
    })
    retry = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def format_phone(phone):
    phone = str(phone).strip().replace("+", "").replace("-", "").replace(" ", "")
    if phone.startswith("0"):
        phone = "62" + phone[1:]
    if phone.endswith(".0"):
        phone = phone[:-2]
    return phone

# API Request: Kirim Teks
def send_wa_text(instance, token, phone, text, timeout):
    url = f"https://api.green-api.com/waInstance{instance}/sendMessage/{token}"
    payload = {"chatId": f"{phone}@c.us", "message": text}
    try:
        session = get_http_session()
        response = session.post(url, json=payload, verify=False, timeout=timeout)
        return response.status_code == 200, response.text
    except Exception as e:
        return False, str(e)

# API Request: Kirim Gambar via URL
def send_wa_file_by_url(instance, token, phone, url_file, caption, timeout):
    url = f"https://api.green-api.com/waInstance{instance}/sendFileByUrl/{token}"
    payload = {
        "chatId": f"{phone}@c.us",
        "urlFile": url_file,
        "fileName": "promo.jpg",
        "caption": caption
    }
    try:
        session = get_http_session()
        response = session.post(url, json=payload, verify=False, timeout=timeout)
        return response.status_code == 200, response.text
    except Exception as e:
        return False, str(e)

# Section Tombol Eksekusi & Cancel
st.markdown("---")
st.subheader("5. Eksekusi Pengiriman")

btn_col1, btn_col2 = st.columns([1, 1])
with btn_col1:
    start_btn = st.button("🚀 Mulai Kirim Broadcast", type="primary", use_container_width=True)
with btn_col2:
    stop_btn = st.button("🛑 Stop / Cancel Pengiriman", type="secondary", use_container_width=True)

if stop_btn:
    st.session_state.is_running = False

if start_btn:
    if not instance_id or not api_token:
        st.error("Harap isi Instance ID dan API Token di sidebar!")
    elif df is None or df.empty:
        st.error("Harap unggah file kontak terlebih dahulu!")
    elif not message_template:
        st.error("Harap isi template pesan!")
    else:
        st.session_state.is_running = True
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_area = st.container()
        
        total_contacts = len(df)
        success_count = 0
        failed_count = 0

        for idx, row in df.iterrows():
            if not st.session_state.is_running:
                st.warning(f"🛑 Pengiriman Dibatalkan oleh Pengguna pada kontak ke-{idx+1}!")
                break

            try:
                formatted_message = message_template.format(**row.to_dict())
            except Exception:
                formatted_message = message_template

            phone_number = format_phone(row.get('no_hp', row.get('telepon', row.get('phone', ''))))
            status_text.text(f"Mengirim pesan ke {phone_number} ({idx+1}/{total_contacts})...")
            
            # Kirim Gambar atau Teks
            if image_url_input:
                is_success, log_msg = send_wa_file_by_url(instance_id, api_token, phone_number, image_url_input, formatted_message, timeout_setting)
            else:
                is_success, log_msg = send_wa_text(instance_id, api_token, phone_number, formatted_message, timeout_setting)
            
            if is_success:
                success_count += 1
                log_area.caption(f"✅ [{idx+1}] Berhasil kirim ke: {phone_number}")
            else:
                failed_count += 1
                log_area.error(f"❌ [{idx+1}] Gagal kirim ke: {phone_number} | Details: {log_msg}")

            progress_bar.progress((idx + 1) / total_contacts)
            
            if idx < total_contacts - 1:
                time.sleep(delay_time)

        if st.session_state.is_running:
            st.success(f"🎉 Selesai! Total Berhasil: {success_count} | Gagal: {failed_count}")
        st.session_state.is_running = False