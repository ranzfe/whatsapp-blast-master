import os
import time
import subprocess
import pandas as pd
import requests
import streamlit as st

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

st.set_page_config(page_title="WA Blast - Local Automation", page_icon="📲", layout="wide")

st.title("📲 WhatsApp Web Auto Blast (Versi Lokal)")
st.caption("Aplikasi automasi WhatsApp Web Lokal (Support Teks, Gambar & Anti-Crash)")

# Lokasi folder sesi & temporary image
SESSION_DIR = os.path.join(os.getcwd(), "selenium_wa_session")
TEMP_IMG_DIR = os.path.join(os.getcwd(), "temp_upload")
os.makedirs(SESSION_DIR, exist_ok=True)
os.makedirs(TEMP_IMG_DIR, exist_ok=True)

if "is_running" not in st.session_state:
    st.session_state.is_running = False

# Sidebar Configuration
st.sidebar.header("⚙️ Pengaturan Automasi")
delay_time = st.sidebar.slider("Jeda Antar Pesan (detik)", min_value=5, max_value=30, value=10)

# Fungsi untuk membersihkan proses Chrome yang menggantung
def kill_zombie_chrome():
    try:
        subprocess.run("taskkill /f /im chromedriver.exe /t", shell=True, capture_output=True)
    except Exception:
        pass

def init_driver():
    chrome_options = Options()
    chrome_options.add_argument(f"--user-data-dir={SESSION_DIR}")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-allow-origins=*")
    
    # Mencegah deteksi bot
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

# Layout App
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Status Login WhatsApp Web")
    st.caption("⚠️ Tutup jendela Chrome WhatsApp Web sebelum menekan 'Mulai Blast'")
    
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🔑 Buka & Scan QR WhatsApp Web", use_container_width=True):
            kill_zombie_chrome()
            try:
                driver = init_driver()
                driver.get("https://web.whatsapp.com")
                st.info("Browser Chrome terbuka. Silakan scan QR jika belum login. Setelah masuk WhatsApp Web, TUTUP BROWSER CHROME TERSEBUT terlebih dahulu.")
            except Exception as e:
                st.error(f"Gagal membuka browser: {e}")
    with col_btn2:
        if st.button("🧹 Bersihkan Chrome Gantung", use_container_width=True):
            kill_zombie_chrome()
            st.success("Proses Chrome berhasil dibersihkan!")

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

    st.subheader("3. Lampiran Gambar (Opsional)")
    uploaded_image = st.file_uploader("Upload Gambar Promo (JPG/PNG)", type=["jpg", "jpeg", "png"])
    saved_img_path = None
    if uploaded_image is not None:
        saved_img_path = os.path.abspath(os.path.join(TEMP_IMG_DIR, uploaded_image.name))
        with open(saved_img_path, "wb") as f:
            f.write(uploaded_image.getbuffer())
        st.image(uploaded_image, caption="Gambar Siap Dikirim", width=250)

    st.subheader("4. Template Pesan / Caption")
    message_template = st.text_area(
        "Tulis Pesan (Variabel: {nama}, {no_hp})",
        height=150,
        placeholder="Halo {nama},\n\nTerima kasih telah menghubungi kami..."
    )

with col2:
    st.subheader("5. Pratinjau Pesan (Preview)")
    if df is not None and message_template and not df.empty:
        sample_row = df.iloc[0].to_dict()
        try:
            preview_text = message_template.format(**sample_row)
            st.info("Contoh tampilan pesan ke kontak pertama:")
            if uploaded_image is not None:
                st.image(uploaded_image, width=200)
            st.text_area("Pratinjau Teks", value=preview_text, height=150, disabled=True)
        except KeyError as e:
            st.warning(f"Variabel {{{e.args[0]}}} di template tidak ditemukan pada kolom file!")
    else:
        st.write("Unggah file dan tulis template pesan untuk melihat pratinjau.")

def format_phone(phone):
    phone = str(phone).strip().replace("+", "").replace("-", "").replace(" ", "")
    if phone.startswith("0"):
        phone = "62" + phone[1:]
    if phone.endswith(".0"):
        phone = phone[:-2]
    return phone

st.markdown("---")
st.subheader("6. Eksekusi Broadcast")

btn_col1, btn_col2 = st.columns([1, 1])
with btn_col1:
    start_btn = st.button("🚀 Mulai Blast via WhatsApp Web", type="primary", use_container_width=True)
with btn_col2:
    stop_btn = st.button("🛑 Stop / Cancel Pengiriman", type="secondary", use_container_width=True)

if stop_btn:
    st.session_state.is_running = False

if start_btn:
    if df is None or df.empty:
        st.error("Harap unggah file kontak terlebih dahulu!")
    elif not message_template:
        st.error("Harap isi template pesan!")
    else:
        kill_zombie_chrome()
        st.session_state.is_running = True
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_area = st.container()
        
        driver = None
        try:
            status_text.text("Menyiapkan Chrome Driver...")
            driver = init_driver()
            driver.get("https://web.whatsapp.com")
            
            status_text.text("Membuka WhatsApp Web, memuat sesi...")
            time.sleep(10)
            
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
                
                # Buka Direct Link Chat
                send_url = f"https://web.whatsapp.com/send?phone={phone_number}"
                driver.get(send_url)
                time.sleep(6)

                try:
                    # Skenario 1: Kirim Gambar + Pesan
                    if saved_img_path and os.path.exists(saved_img_path):
                        # Kirim file langsung ke input type='file' tanpa klik tombol attach
                        file_input = WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.XPATH, '//input[@type="file"]'))
                        )
                        file_input.send_keys(saved_img_path)
                        time.sleep(2)

                        # Masukkan Caption
                        caption_box_xpath = '//div[@aria-label="Add a caption"] | //div[@aria-label="Tambah keterangan"] | //footer//div[@contenteditable="true"]'
                        caption_box = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, caption_box_xpath))
                        )
                        
                        for line in formatted_message.split('\n'):
                            caption_box.send_keys(line)
                            caption_box.send_keys(Keys.SHIFT + Keys.ENTER)
                            
                        caption_box.send_keys(Keys.ENTER)

                    # Skenario 2: Kirim Pesan Teks Saja
                    else:
                        input_box_xpath = '//div[@contenteditable="true"][@data-tab="10"] | //footer//div[@contenteditable="true"]'
                        msg_box = WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.XPATH, input_box_xpath))
                        )
                        
                        for line in formatted_message.split('\n'):
                            msg_box.send_keys(line)
                            msg_box.send_keys(Keys.SHIFT + Keys.ENTER)
                            
                        msg_box.send_keys(Keys.ENTER)

                    success_count += 1
                    log_area.caption(f"✅ [{idx+1}] Berhasil kirim ke: {phone_number}")
                except Exception as ex:
                    failed_count += 1
                    log_area.error(f"❌ [{idx+1}] Gagal kirim ke: {phone_number} | Keterangan: {ex}")

                progress_bar.progress((idx + 1) / total_contacts)
                time.sleep(delay_time)

            if st.session_state.is_running:
                st.success(f"🎉 Selesai! Berhasil: {success_count} | Gagal: {failed_count}")
            st.session_state.is_running = False

        except Exception as e:
            st.error(f"Terjadi kesalahan pada Selenium/Chrome: {e}")
        finally:
            if driver:
                driver.quit()
