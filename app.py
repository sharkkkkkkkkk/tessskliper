import streamlit as st
import os
import subprocess
import yt_dlp
import shutil
import time

# ==========================================
# KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="Auto Shorts (Final Fix)", page_icon="✂️", layout="centered")

TEMP_DIR = "temp_video"
OUT_DIR = "output_shorts"
COOKIE_FILE = "cookies.txt"

# Bersihkan folder saat restart untuk hemat storage
if os.path.exists(TEMP_DIR): shutil.rmtree(TEMP_DIR)
if os.path.exists(OUT_DIR): shutil.rmtree(OUT_DIR)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# ==========================================
# 1. CEK FFMPEG (WAJIB ADA packages.txt)
# ==========================================
def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except:
        return False

# ==========================================
# 2. DOWNLOADER (LOGIKA BARU)
# ==========================================
def download_video_final(url, cookie_path=None):
    output_filename = "source.mp4"
    output_path = os.path.join(TEMP_DIR, output_filename)
    
    # Hapus file lama
    if os.path.exists(output_path):
        os.remove(output_path)

    # KONFIGURASI YT-DLP (Disesuaikan untuk Cloud Gratisan)
    ydl_opts = {
        # PENTING: Jangan 'bestvideo+bestaudio'. Itu butuh merge & RAM besar.
        # Pilih 'best[ext=mp4]' untuk ambil file jadi (biasanya 720p/360p) yang ringan.
        'format': 'best[ext=mp4]/best',
        
        'outtmpl': output_path,
        'quiet': False, 
        'no_warnings': False,
        'geo_bypass': True,
        
        # MENYAMAR JADI BROWSER (Agar tidak diblokir jadi 0 bytes)
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
        'nocheckcertificate': True,
    }

    # Jika user upload cookies
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

    try:
        with st.status("📥 Sedang mendownload (Mode Stabil)...", expanded=True) as status:
            if cookie_path:
                st.write("🍪 Menggunakan Cookies...")
            else:
                st.write("🕵️ Menggunakan User Agent Samaran...")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # VERIFIKASI FILE
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                if file_size > 1024: # Lebih dari 1KB
                    status.update(label=f"✅ Selesai! Ukuran: {file_size/1024/1024:.2f} MB", state="complete", expanded=False)
                    return True, output_path
                else:
                    return False, "File kosong (0 bytes). Terblokir YouTube."
            else:
                return False, "File tidak ditemukan setelah download."

    except Exception as e:
        return False, str(e)

# ==========================================
# 3. PROCESSING (FFMPEG - ULTRAFAST)
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
    
    # Ambil tengah-tengah video (Safe Zone)
    start_buffer = total_duration * 0.15 # Skip 15% awal
    end_buffer = total_duration * 0.85   # Skip 15% akhir
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
        
        # Filter: Crop Tengah + Scale 720p (Lebih Ringan dari 1080p)
        # Scale 720:1280 sudah cukup bagus untuk HP dan jauh lebih cepat di Cloud
        filter_complex = "crop=ih*(9/16):ih:(iw-ow)/2:0,scale=720:1280"
        
        cmd = [
            'ffmpeg', '-y', 
            '-ss', str(start_time), '-t', str(clip_duration),
            '-i', input_path, '-vf', filter_complex,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30', # Settingan Tercepat
            '-c:a', 'aac', '-b:a', '64k', output_file
        ]
        
        subprocess.run(cmd, capture_output=True)
        generated_files.append(output_file)
        progress_bar.progress((i + 1) / len(start_points))
        
    return generated_files

# ==========================================
# UI APLIKASI
# ==========================================
st.title("✂️ Auto Shorts (Versi Stabil)")
st.caption("Solusi 'File Empty' & 'Timeout' di Streamlit Cloud")

# Cek Sistem
if not check_ffmpeg():
    st.error("❌ FFmpeg Tidak Ditemukan!")
    st.warning("⚠️ Wajib buat file `packages.txt` isi `ffmpeg` di GitHub.")
    st.stop()

# 1. Upload Cookies
with st.expander("🍪 Upload Cookies (Disarankan)", expanded=True):
    st.info("Upload `cookies.txt` jika download gagal terus.")
    uploaded_cookie = st.file_uploader("Pilih file cookies.txt", type=["txt"])
    cookie_path = None
    
    if uploaded_cookie:
        with open(COOKIE_FILE, "wb") as f:
            f.write(uploaded_cookie.getbuffer())
        cookie_path = COOKIE_FILE
        st.success("✅ Cookies terpasang!")

# 2. Input
st.divider()
url_input = st.text_input("🔗 URL YouTube", placeholder="https://youtube.com/watch?v=...")

col1, col2 = st.columns(2)
with col1: num_clips = st.slider("Jumlah Klip", 1, 3, 1) # Default 1 agar cepat
with col2: duration = st.slider("Durasi (detik)", 15, 60, 20)

# 3. Eksekusi
if st.button("🚀 PROSES VIDEO", type="primary", use_container_width=True):
    if url_input:
        success, result = download_video_final(url_input, cookie_path)
        
        if success:
            source_path = result
            st.success("✅ Download Berhasil! Memulai pemotongan...")
            
            with st.spinner("⚙️ Memotong (Tunggu 1-2 menit)..."):
                clips = process_clips(source_path, num_clips, duration)
            
            if clips:
                st.divider()
                st.subheader("🎉 Hasil Video")
                cols = st.columns(len(clips))
                for idx, clip_path in enumerate(clips):
                    with cols[idx % 3]: 
                        st.video(clip_path)
                        with open(clip_path, "rb") as file:
                            st.download_button(f"⬇️ Unduh Klip {idx+1}", file, os.path.basename(clip_path), "video/mp4")
            else:
                st.error("Gagal membuat klip.")
        else:
            st.error(f"Gagal: {result}")
            st.warning("Tips: Coba update `cookies.txt` baru dari Mode Incognito.")
    else:
        st.warning("Masukkan Link YouTube dulu.")
