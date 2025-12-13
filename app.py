import streamlit as st
import os
import subprocess
import yt_dlp
import shutil
import random

# ==========================================
# KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="Auto Shorts (Proxy Mode)", page_icon="🛡️", layout="centered")

TEMP_DIR = "temp_video"
OUT_DIR = "output_shorts"

# Bersihkan folder temp saat restart
if os.path.exists(TEMP_DIR): shutil.rmtree(TEMP_DIR)
if os.path.exists(OUT_DIR): shutil.rmtree(OUT_DIR)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# ==========================================
# 1. DAFTAR PROXY GRATIS (Update Berkala)
# ==========================================
# Tips: Ambil list proxy fresh dari: https://spys.one/en/http-proxy-list/
# Format: "http://IP:PORT"
PROXY_LIST = [
    # Proxy Indonesia/Asia (Biasanya lebih cepat)
    "http://202.152.50.229:8080",
    "http://103.152.118.158:80",
    "http://117.54.114.101:80",
    # Proxy US/Europe (Cadangan)
    "http://198.59.191.234:8080",
    "http://104.248.63.15:3128",
    "http://64.225.4.30:3128",
    "http://209.127.191.180:9279",
]

def get_random_proxy():
    return random.choice(PROXY_LIST)

# ==========================================
# 2. CEK FFMPEG
# ==========================================
def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except:
        return False

# ==========================================
# 3. DOWNLOADER DENGAN PROXY
# ==========================================
def download_video_proxy(url):
    output_filename = "source.mp4"
    output_path = os.path.join(TEMP_DIR, output_filename)
    
    # Coba maksimal 3 kali dengan proxy berbeda
    max_retries = 3
    
    for i in range(max_retries):
        current_proxy = get_random_proxy()
        
        # Opsi yt-dlp
        ydl_opts = {
            'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'geo_bypass': True,
            # SETTING PROXY DISINI
            'proxy': current_proxy,
            # Socket timeout biar gak nunggu proxy mati kelamaan
            'socket_timeout': 10,
        }

        try:
            proxy_msg = f"Percobaan {i+1}/{max_retries} menggunakan Proxy: {current_proxy}"
            print(proxy_msg) # Log ke console server
            
            with st.status(f"📥 {proxy_msg}...", expanded=True) as status:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                status.update(label="✅ Download Selesai!", state="complete", expanded=False)
            
            return True, output_path # Jika sukses, langsung return

        except Exception as e:
            st.warning(f"⚠️ Proxy {current_proxy} gagal, mencoba proxy lain...")
            continue # Lanjut ke loop berikutnya (proxy baru)

    # Jika sudah 3x mencoba masih gagal
    return False, "Semua proxy gagal atau diblokir. Coba update daftar PROXY_LIST."

# ==========================================
# 4. PROCESSING (FFMPEG)
# ==========================================
def get_video_duration(input_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout)
    except:
        return 0

def process_clips(input_path, num_clips, clip_duration):
    total_duration = get_video_duration(input_path)
    if total_duration == 0: return []

    generated_files = []
    start_buffer = total_duration * 0.1
    end_buffer = total_duration * 0.9
    playable_area = end_buffer - start_buffer
    
    if playable_area < clip_duration:
        start_points = [(total_duration / 2) - (clip_duration/2)]
    else:
        step = playable_area / num_clips
        start_points = [start_buffer + (i * step) for i in range(num_clips)]

    progress_bar = st.progress(0)
    
    for i, start_time in enumerate(start_points):
        if start_time < 0: start_time = 0
        output_name = f"Short_Clip_{i+1}.mp4"
        output_file = os.path.join(OUT_DIR, output_name)
        
        filter_complex = "crop=ih*(9/16):ih:(iw-ow)/2:0,scale=1080:1920"
        
        cmd = [
            'ffmpeg', '-y', 
            '-ss', str(start_time), '-t', str(clip_duration),
            '-i', input_path, '-vf', filter_complex,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
            '-c:a', 'aac', '-b:a', '128k', output_file
        ]
        
        subprocess.run(cmd, capture_output=True)
        generated_files.append(output_file)
        progress_bar.progress((i + 1) / len(start_points))
        
    return generated_files

# ==========================================
# UI
# ==========================================
st.title("🛡️ Cloud Auto Shorts + Proxy")
st.markdown("Menggunakan **Rotasi Proxy** untuk menembus blokir YouTube di Cloud.")

if not check_ffmpeg():
    st.error("❌ FFmpeg belum terinstall. Cek file packages.txt!")
    st.stop()

url_input = st.text_input("🔗 URL YouTube", placeholder="https://youtube.com/watch?v=...")
col1, col2 = st.columns(2)
with col1: num_clips = st.slider("Jumlah Klip", 1, 5, 2)
with col2: duration = st.slider("Durasi (detik)", 15, 60, 30)

if st.button("🚀 PROSES DENGAN VPN/PROXY", type="primary", use_container_width=True):
    if url_input:
        success, result = download_video_proxy(url_input)
        
        if success:
            source_path = result
            st.success("✅ Video berhasil didownload lewat jalur belakang!")
            
            with st.spinner("⚙️ Memotong video..."):
                clips = process_clips(source_path, num_clips, duration)
            
            if clips:
                st.divider()
                cols = st.columns(len(clips))
                for idx, clip_path in enumerate(clips):
                    with cols[idx % 3]: 
                        st.video(clip_path)
                        with open(clip_path, "rb") as file:
                            st.download_button(f"⬇️ Unduh {idx+1}", file, os.path.basename(clip_path), "video/mp4")
            else:
                st.error("Gagal clipping.")
        else:
            st.error(f"Gagal: {result}")
            st.info("💡 Solusi: Coba refresh halaman dan tekan tombol lagi (agar mencoba proxy acak yang lain).")
    else:
        st.warning("Masukkan URL dulu.")
