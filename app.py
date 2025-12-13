import streamlit as st
import os
import subprocess
import json
import http.client
import urllib.request
import re
import random

# ==========================================
# KONFIGURASI
# ==========================================
st.set_page_config(page_title="Auto Shorts Generator", page_icon="✂️", layout="centered")

# Folder Temp & Output
TEMP_DIR = "temp_video"
OUT_DIR = "output_shorts"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# API Config
RAPIDAPI_KEY = "75101489acmshbc6c10ab7c834eep1cf630jsn7d5a199afa41"
RAPIDAPI_HOST = "youtube-media-downloader.p.rapidapi.com"

# ==========================================
# 1. CEK DEPENDENCIES (FFMPEG)
# ==========================================
def check_ffmpeg():
    """Memastikan FFmpeg terinstall"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except:
        return False

# ==========================================
# 2. LOGIKA DOWNLOAD (RAPIDAPI)
# ==========================================
def extract_video_id(url):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'^([0-9A-Za-z_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def download_video(video_id):
    """Download Video menggunakan RapidAPI (Logic Fixed)"""
    output_path = os.path.join(TEMP_DIR, "source.mp4")
    
    # Hapus file lama jika ada
    if os.path.exists(output_path):
        os.remove(output_path)

    try:
        # A. Request API
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
        headers = {
            'x-rapidapi-key': RAPIDAPI_KEY,
            'x-rapidapi-host': RAPIDAPI_HOST
        }
        conn.request("GET", f"/v2/video/details?videoId={video_id}", headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        conn.close()

        # B. Parsing JSON (Sesuai perbaikan PHP sebelumnya)
        download_url = None
        
        # Cek struktur ['videos']['items']
        if 'videos' in data and 'items' in data['videos']:
            items = data['videos']['items']
            
            # Prioritas 1: Cari 720p dengan Audio
            for vid in items:
                if vid.get('quality') == '720p' and vid.get('hasAudio'):
                    download_url = vid.get('url')
                    break
            
            # Prioritas 2: Cari 360p/480p dengan Audio jika 720p tak ada
            if not download_url:
                for vid in items:
                    if vid.get('hasAudio'):
                        download_url = vid.get('url')
                        break
                        
            # Prioritas 3: Ambil apa saja yang ada URL-nya
            if not download_url and items:
                download_url = items[0].get('url')

        if not download_url:
            return False, "Tidak menemukan link download dari API."

        # C. Download File Streaming
        with st.status("📥 Sedang mendownload video...", expanded=True) as status:
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
            urllib.request.install_opener(opener)
            
            urllib.request.urlretrieve(download_url, output_path)
            status.update(label="✅ Download Selesai!", state="complete", expanded=False)
            
        return True, output_path

    except Exception as e:
        return False, str(e)

# ==========================================
# 3. LOGIKA AUTO CLIPPING (FFMPEG)
# ==========================================
def get_video_duration(input_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout)

def process_clips(input_path, num_clips, clip_duration):
    """Memotong video dan mengubahnya menjadi Vertical (9:16)"""
    
    total_duration = get_video_duration(input_path)
    generated_files = []
    
    # Hitung titik potong (Hindari 10% awal dan akhir intro/outro)
    start_buffer = total_duration * 0.1
    end_buffer = total_duration * 0.9
    playable_area = end_buffer - start_buffer
    
    if playable_area < clip_duration:
        st.warning("Video terlalu pendek untuk dipotong banyak!")
        start_points = [start_buffer]
    else:
        # Generate titik potong secara merata
        step = playable_area / num_clips
        start_points = [start_buffer + (i * step) for i in range(num_clips)]

    progress_bar = st.progress(0)
    
    for i, start_time in enumerate(start_points):
        output_name = f"Short_Clip_{i+1}.mp4"
        output_file = os.path.join(OUT_DIR, output_name)
        
        # FILTER FFMPEG: 
        # 1. Potong waktu (-ss, -t)
        # 2. Crop bagian TENGAH video menjadi rasio 9:16 (Vertical)
        # 3. Scale ke 1080x1920
        
        # Rumus Crop Tengah: crop=h*(9/16):h:(w-ow)/2:0
        filter_complex = "crop=ih*(9/16):ih:(iw-ow)/2:0,scale=1080:1920"
        
        cmd = [
            'ffmpeg', '-y', 
            '-ss', str(start_time),
            '-t', str(clip_duration),
            '-i', input_path,
            '-vf', filter_complex,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            output_file
        ]
        
        subprocess.run(cmd, capture_output=True)
        generated_files.append(output_file)
        progress_bar.progress((i + 1) / len(start_points))
        
    return generated_files

# ==========================================
# UI STREAMLIT
# ==========================================
st.title("✂️ Auto Shorts Generator")
st.markdown("Masukkan URL YouTube, otomatis jadi video vertikal (9:16) siap upload!")

# Cek FFmpeg dulu
if not check_ffmpeg():
    st.error("❌ FFmpeg belum terinstall di server/komputer ini. Aplikasi tidak bisa memotong video.")
    st.stop()

# Input Section
with st.container():
    url_input = st.text_input("🔗 URL YouTube", placeholder="https://youtube.com/watch?v=...")
    
    col1, col2 = st.columns(2)
    with col1:
        num_clips = st.slider("Jumlah Klip", 1, 5, 2)
    with col2:
        duration = st.slider("Durasi per Klip (detik)", 15, 60, 30)
        
    btn_process = st.button("🚀 PROSES & POTONG", type="primary", use_container_width=True)

# Main Process
if btn_process and url_input:
    video_id = extract_video_id(url_input)
    
    if not video_id:
        st.error("URL YouTube tidak valid!")
    else:
        # 1. Download
        success, result = download_video(video_id)
        
        if success:
            source_path = result
            st.success("✅ Download berhasil, memulai proses clipping...")
            
            # 2. Clipping
            with st.spinner("⚙️ Sedang memotong dan convert ke Vertical..."):
                clips = process_clips(source_path, num_clips, duration)
            
            st.divider()
            st.subheader("🎉 Hasil Clipping")
            
            # 3. Tampilkan Hasil
            cols = st.columns(len(clips))
            for idx, clip_path in enumerate(clips):
                with cols[idx % 3]: # Agar layout rapi jika banyak klip
                    st.video(clip_path)
                    
                    with open(clip_path, "rb") as file:
                        btn = st.download_button(
                            label=f"⬇️ Download Klip {idx+1}",
                            data=file,
                            file_name=os.path.basename(clip_path),
                            mime="video/mp4"
                        )
            
            # Bersihkan file temp source (opsional)
            # os.remove(source_path)
            
        else:
            st.error(f"Gagal Download: {result}")

st.caption("Powered by RapidAPI & FFmpeg")
