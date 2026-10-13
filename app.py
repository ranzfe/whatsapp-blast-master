import streamlit as st
import pandas as pd
import time
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

st.set_page_config(page_title="WA Blast - WhatsApp Web Automation", page_icon="📲", layout="wide")

st.title("📲 WhatsApp Web Auto Blast (Tanpa API Pihak Ke-3)")
st.caption("Aplikasi mengontrol Chrome secara otomatis dengan menyimpan sesi login WhatsApp Web Anda secara permanen.")

# Folder Simpan Session Login WhatsApp
SESSION_DIR = os.path.join(os.getcwd(), "selenium_wa_session")

# Sidebar Configuration
st.sidebar.header("⚙️ Pengaturan Automasi")
delay_time = st.sidebar.slider("Jeda Antar Pesan (detik)", min_value=5, max_value=30, value=10)
headless_mode = st.sidebar.checkbox("Sembunyikan Browser (Headless Mode)", value=False)

# Inisialisasi Selenium Driver
def init_driver(headless=False):
    chrome_options = Options()
    # Simpan profile agar tidak perlu scan QR terus menerus
    chrome_options.add_argument(f"--user-data-dir={SESSION_DIR}")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    if headless:
        chrome_options.add_argument("--headless=new")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

# Layout App
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Status Login WhatsApp Web")
    if st.button("🔑 Buka / Cek Login WhatsApp Web"):
        with st.spinner("Membuka Chrome untuk verifikasi WhatsApp Web..."):
            driver = init_driver(headless=False)
            driver.get("https://web.whatsapp.com")
            st.info("Browser Chrome dibuka! Silakan Scan QR Code jika belum login. Setelah masuk WhatsApp Web, Anda bisa menutup jendela browser.")

    st.subheader("2. Unggah Daftar Kontak (CSV / Excel)")
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

    st.subheader("3. Template Pesan")
    message_template = st.text_area(
        "Tulis Pesan (Variabel: {nama}, {no_hp})",
        height=150,
        placeholder="Halo {nama},\n\nTerima kasih telah menghubungi kami..."
    )

with col2:
    st.subheader("4. Pratinjau Pesan (Preview)")
    if df is not None and message_template and not df.empty:
        sample_row = df.iloc[0].to_dict()
        try:
            preview_text = message_template.format(**sample_row)
            st.info("Contoh tampilan pesan ke kontak pertama:")
            st.text_area("Pratinjau Teks", value=preview_text, height=150, disabled=True)
        except KeyError as e:
            st.warning(f"Variabel {{{e.args[0]}}} di template tidak ditemukan pada kolom file!")
    else:
        st.write("Unggah file dan tulis template pesan untuk melihat pratinjau.")

# Helper Format HP
def format_phone(phone):
    phone = str(phone).strip().replace("+", "").replace("-", "").replace(" ", "")
    if phone.startswith("0"):
        phone = "62" + phone[1:]
    if phone.endswith(".0"):
        phone = phone[:-2]
    return phone

# Section Eksekusi
st.markdown("---")
st.subheader("5. Eksekusi Broadcast")

if st.button("🚀 Mulai Blast via WhatsApp Web", type="primary"):
    if df is None or df.empty:
        st.error("Harap unggah file kontak terlebih dahulu!")
    elif not message_template:
        st.error("Harap isi template pesan!")
    else:
        st.info("Memulai pengiriman pesan massal...")
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_area = st.container()
        
        driver = None
        try:
            driver = init_driver(headless=headless_mode)
            driver.get("https://web.whatsapp.com")
            
            # Tunggu elemen utama WA Web dimuat (max 45 detik)
            status_text.text("Menunggu WhatsApp Web dimuat...")
            WebDriverWait(driver, 45).until(
                EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"] | //canvas'))
            )
            
            total_contacts = len(df)
            success_count = 0
            failed_count = 0

            for idx, row in df.iterrows():
                try:
                    formatted_message = message_template.format(**row.to_dict())
                except Exception:
                    formatted_message = message_template

                phone_number = format_phone(row.get('no_hp', row.get('telepon', row.get('phone', ''))))
                status_text.text(f"Mengirim pesan ke {phone_number} ({idx+1}/{total_contacts})...")
                
                # Buka direct chat WhatsApp Web
                send_url = f"https://web.whatsapp.com/send?phone={phone_number}&text={requests.utils.quote(formatted_message)}"
                driver.get(send_url)
                
                try:
                    # Tunggu tombol Send / Input Chat muncul
                    send_btn = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.XPATH, '//span[@data-icon="send"] | //button[@aria-label="Send"]'))
                    )
                    time.sleep(1)
                    send_btn.click() # Klik kirim
                    
                    success_count += 1
                    log_area.caption(f"✅ [{idx+1}] Berhasil kirim ke: {phone_number}")
                except Exception as ex:
                    failed_count += 1
                    log_area.error(f"❌ [{idx+1}] Gagal kirim ke: {phone_number} (Nomor tidak terdaftar / timeout)")

                progress_bar.progress((idx + 1) / total_contacts)
                time.sleep(delay_time)

            st.success(f"🎉 Selesai! Berhasil: {success_count} | Gagal: {failed_count}")
            
        except Exception as e:
            st.error(f"Terjadi kesalahan pada Selenium/Chrome: {e}")
        finally:
            if driver:
                driver.quit()
