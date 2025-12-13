import streamlit as st
import os
import subprocess
import yt_dlp
import shutil

# ==========================================
# KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="Auto Shorts Generator", page_icon="✂️", layout="centered")

# Folder Setup
TEMP_DIR = "temp_video"
OUT_DIR = "output_shorts"

# Bersihkan folder setiap kali app restart agar storage server tidak penuh
if os.path.exists(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)
if os.path.exists(OUT_DIR):
    shutil.rmtree(OUT_DIR)

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# ==========================================
# 1. CEK FFMPEG (SYSTEM LEVEL)
# ==========================================
def check_ffmpeg():
    """Cek apakah FFmpeg terinstall di sistem Streamlit Cloud"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False

# ==========================================
# 2. DOWNLOADER (YT-DLP)
# ==========================================
def download_video_ytdlp(url):
    output_filename = "source.mp4"
    output_path = os.path.join(TEMP_DIR, output_filename)
    
    # Opsi yt-dlp yang ramah server
    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        # Geo-bypass kadang membantu di server cloud
        'geo_bypass': True,
        # User agent palsu agar tidak terdeteksi sebagai bot server
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }

    try:
        with st.status("📥 Sedang mendownload (Server Cloud)...", expanded=True) as status:
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
    if total_duration == 0:
        return []

    generated_files = []
    
    # Logika ambil tengah (hindari intro/outro)
    start_buffer = total_duration * 0.1
    end_buffer = total_duration * 0.9
    playable_area = end_buffer - start_buffer
    
    if playable_area < clip_duration:
        mid_point = total_duration / 2
        start_points = [mid_point - (clip_duration/2)]
    else:
        step = playable_area / num_clips
        start_points = [start_buffer + (i * step) for i in range(num_clips)]

    progress_bar = st.progress(0)
    
    for i, start_time in enumerate(start_points):
        if start_time < 0: start_time = 0
        
        output_name = f"Short_Clip_{i+1}.mp4"
        output_file = os.path.join(OUT_DIR, output_name)
        
        # Filter: Crop 9:16 Center + Scale HD
        filter_complex = "crop=ih*(9/16):ih:(iw-ow)/2:0,scale=1080:1920"
        
        cmd = [
            'ffmpeg', '-y', 
            '-ss', str(start_time),
            '-t', str(clip_duration),
            '-i', input_path,
            '-vf', filter_complex,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
            '-c:a', 'aac', '-b:a', '128k',
            output_file
        ]
        
        subprocess.run(cmd, capture_output=True)
        generated_files.append(output_file)
        progress_bar.progress((i + 1) / len(start_points))
        
    return generated_files

# ==========================================
# UI
# ==========================================
st.title("✂️ Cloud Auto Shorts")
st.caption("Running on Streamlit Cloud • yt-dlp • ffmpeg")

# Cek FFmpeg di environment Cloud
if not check_ffmpeg():
    st.error("❌ FFmpeg TIDAK ditemukan!")
    st.warning("⚠️ Pastikan kamu sudah membuat file 'packages.txt' berisi 'ffmpeg' di repo GitHub kamu.")
    st.stop()

# Input
url_input = st.text_input("🔗 URL YouTube", placeholder="https://youtube.com/watch?v=...")

col1, col2 = st.columns(2)
with col1:
    num_clips = st.slider("Jumlah Klip", 1, 5, 2)
with col2:
    duration = st.slider("Durasi (detik)", 15, 60, 30)
    
btn_process = st.button("🚀 PROSES DI CLOUD", type="primary", use_container_width=True)

if btn_process and url_input:
    success, result = download_video_ytdlp(url_input)
    
    if success:
        source_path = result
        st.success("✅ Video terdownload di server cloud.")
        
        with st.spinner("⚙️ Memotong video (ini memakan CPU server)..."):
            clips = process_clips(source_path, num_clips, duration)
        
        if clips:
            st.divider()
            cols = st.columns(len(clips))
            for idx, clip_path in enumerate(clips):
                col_idx = idx % 3
                with cols[col_idx]: 
                    st.video(clip_path)
                    with open(clip_path, "rb") as file:
                        st.download_button(
                            label=f"⬇️ Unduh Klip {idx+1}",
                            data=file,
                            file_name=os.path.basename(clip_path),
                            mime="video/mp4"
                        )
        else:
            st.error("Gagal memproses video.")
    else:
        st.error(f"Gagal Download: {result}")
        st.info("ℹ️ Jika error 'Sign in' atau '429', berarti IP Streamlit Cloud diblokir YouTube sementara.")
