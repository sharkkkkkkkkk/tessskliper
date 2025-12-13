import streamlit as st
import os
import subprocess
import yt_dlp
import shutil

# ==========================================
# KONFIGURASI
# ==========================================
st.set_page_config(page_title="Auto Shorts (Cookie Mode)", page_icon="🍪", layout="centered")

TEMP_DIR = "temp_video"
OUT_DIR = "output_shorts"
COOKIE_FILE = "cookies.txt"

# Bersihkan folder
if os.path.exists(TEMP_DIR): shutil.rmtree(TEMP_DIR)
if os.path.exists(OUT_DIR): shutil.rmtree(OUT_DIR)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# ==========================================
# 1. CEK FFMPEG
# ==========================================
def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except:
        return False

# ==========================================
# 2. DOWNLOADER DENGAN COOKIES
# ==========================================
def download_video_cookies(url, cookie_path=None):
    output_filename = "source.mp4"
    output_path = os.path.join(TEMP_DIR, output_filename)
    
    # Opsi yt-dlp
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        # User agent agar terlihat seperti browser biasa
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }

    # Jika user upload cookies, gunakan!
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

    try:
        with st.status("📥 Sedang mendownload (Bypass 403)...", expanded=True) as status:
            if cookie_path:
                st.write("🍪 Menggunakan Cookies User...")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            status.update(label="✅ Download Selesai!", state="complete", expanded=False)
            
        return True, output_path

    except Exception as e:
        return False, str(e)

# ==========================================
# 3. PROCESSING (FFMPEG)
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
        
        # Crop 9:16 Center
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
# UI APLIKASI
# ==========================================
st.title("🍪 Auto Shorts (Bypass 403)")
st.caption("Gunakan Cookies untuk melewati blokir YouTube di Cloud.")

if not check_ffmpeg():
    st.error("❌ FFmpeg belum terinstall. Pastikan file 'packages.txt' ada di GitHub.")
    st.stop()

# 1. INPUT COOKIES
with st.expander("🔑 Langkah 1: Upload Cookies (Wajib jika Error 403)", expanded=True):
    st.info("Download ekstensi 'Get cookies.txt LOCALLY' di Chrome, export file, lalu upload di sini.")
    uploaded_cookie = st.file_uploader("Upload file cookies.txt", type=["txt"])
    
    cookie_path = None
    if uploaded_cookie:
        with open(COOKIE_FILE, "wb") as f:
            f.write(uploaded_cookie.getbuffer())
        cookie_path = COOKIE_FILE
        st.success("✅ Cookies siap digunakan!")

# 2. INPUT URL & SETTING
st.divider()
url_input = st.text_input("🔗 URL YouTube", placeholder="https://youtube.com/watch?v=...")
col1, col2 = st.columns(2)
with col1: num_clips = st.slider("Jumlah Klip", 1, 5, 2)
with col2: duration = st.slider("Durasi (detik)", 15, 60, 30)

# 3. TOMBOL PROSES
if st.button("🚀 PROSES VIDEO", type="primary", use_container_width=True):
    if url_input:
        # Panggil fungsi download dengan path cookies
        success, result = download_video_cookies(url_input, cookie_path)
        
        if success:
            source_path = result
            st.success("✅ Video berhasil didownload!")
            
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
            if "403" in str(result) or "Sign in" in str(result):
                st.warning("⚠️ Masih Error 403? Pastikan file cookies.txt yang Anda upload masih baru (Fresh).")
    else:
        st.warning("Masukkan URL dulu.")
