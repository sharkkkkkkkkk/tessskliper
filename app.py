import streamlit as st
import os
import subprocess
import json
from pathlib import Path
from pytubefix import YouTube

# ==========================================
# KONFIGURASI
# ==========================================
st.set_page_config(page_title="Auto Shorts", page_icon="🎬", layout="wide")

TEMP_DIR = "temp"
OUT_DIR = "output"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# ==========================================
# FUNGSI HELPER
# ==========================================
def check_ffmpeg():
    """Cek apakah ffmpeg tersedia"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def get_video_info(video_path):
    """Dapatkan info video menggunakan ffprobe"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(result.stdout)
        
        duration = float(data['format']['duration'])
        
        video_stream = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
        width = int(video_stream['width'])
        height = int(video_stream['height'])
        
        return {
            'duration': duration,
            'width': width,
            'height': height
        }
    except Exception as e:
        st.error(f"Error getting video info: {e}")
        return None

# ==========================================
# POTOKEN HELPER
# ==========================================
def get_manual_potoken():
    """UI untuk input PoToken manual"""
    st.warning("⚠️ **Bot Detection!** Diperlukan PoToken untuk bypass.")
    
    with st.expander("📘 Cara Mendapatkan PoToken (5 menit)", expanded=True):
        st.markdown("""
        **Langkah-langkah:**
        
        1. Buka browser **Chrome/Firefox** dalam mode **Incognito/Private**
        
        2. Kunjungi URL ini:
           ```
           https://www.youtube.com/embed/jNQXAC9IVRw
           ```
        
        3. Tekan **F12** untuk membuka Developer Tools
        
        4. Pilih tab **Network**
        
        5. Di kolom filter, ketik: `player`
        
        6. **Klik tombol Play** pada video
        
        7. Akan muncul request bernama `player` → Klik request tersebut
        
        8. Pilih tab **Payload** (atau **Request**)
        
        9. Scroll ke bawah, cari dan **copy nilai**:
           - `visitorData` → contoh: `CgtqUXZhN2xMZE5rOCi9n...`
           - `poToken` → contoh: `MmVSTnNtN1RMUzBz...` (string panjang)
        
        10. Paste kedua nilai ke form di bawah
        
        **💡 Tips:**
        - PoToken valid 4-6 jam
        - Gunakan mode Incognito untuk hasil terbaik
        - Jika expired, ulangi proses ini
        """)
    
    col1, col2 = st.columns(2)
    with col1:
        visitor_data = st.text_input(
            "🔑 Visitor Data:", 
            key="vdata",
            placeholder="CgtqUXZhN..."
        )
    with col2:
        po_token = st.text_input(
            "🔐 PoToken:", 
            key="potoken",
            placeholder="MmVSTnNt...",
            type="password"
        )
    
    if visitor_data and po_token:
        return (visitor_data.strip(), po_token.strip())
    return None

# ==========================================
# DOWNLOAD DENGAN PYTUBEFIX
# ==========================================
def download_with_pytubefix(url, use_potoken=False, potoken_data=None):
    """
    Download menggunakan Pytubefix dengan support PoToken
    """
    output_path = f"{TEMP_DIR}/source.mp4"
    if os.path.exists(output_path):
        os.remove(output_path)
    
    try:
        # METODE 1: ANDROID Client (tanpa PoToken)
        if not use_potoken:
            st.write("🔄 Download dengan Client ANDROID...")
            
            try:
                yt = YouTube(url, client='ANDROID')
                
                st.info(f"📹 **{yt.title}**")
                st.info(f"⏱️ Durasi: {yt.length // 60}:{yt.length % 60:02d}")
                st.info(f"👁️ Views: {yt.views:,}")
                
                # Cari progressive stream (video+audio)
                stream = yt.streams.filter(
                    progressive=True,
                    file_extension='mp4'
                ).order_by('resolution').desc().first()
                
                if not stream:
                    stream = yt.streams.get_highest_resolution()
                
                if not stream:
                    raise Exception("Tidak ada stream tersedia")
                
                st.write(f"⬇️ Resolusi: **{stream.resolution}** | Size: **{stream.filesize_mb:.1f} MB**")
                
                with st.spinner("Mendownload..."):
                    stream.download(output_path=TEMP_DIR, filename="source.mp4")
                
                st.success("✅ Download berhasil!")
                return True
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Deteksi bot error
                if 'bot' in error_msg or '403' in error_msg or 'forbidden' in error_msg:
                    st.error("🤖 YouTube mendeteksi request sebagai bot (Error 403)")
                    st.warning("💡 Aktifkan **'Gunakan PoToken Manual'** di sidebar untuk bypass")
                    return False
                else:
                    raise e
        
        # METODE 2: WEB Client dengan PoToken
        else:
            if not potoken_data:
                st.error("❌ PoToken belum diisi!")
                return False
            
            visitor_data, po_token = potoken_data
            
            st.write("🔄 Download dengan PoToken Manual...")
            
            # Custom verifier untuk PoToken
            def po_token_verifier():
                return (visitor_data, po_token)
            
            yt = YouTube(
                url,
                client='WEB',
                use_po_token=True,
                po_token_verifier=po_token_verifier,
                allow_oauth_cache=True
            )
            
            st.info(f"📹 **{yt.title}**")
            st.info(f"⏱️ Durasi: {yt.length // 60}:{yt.length % 60:02d}")
            
            # Cari stream terbaik
            stream = yt.streams.filter(
                progressive=True,
                file_extension='mp4'
            ).order_by('resolution').desc().first()
            
            if not stream:
                stream = yt.streams.get_highest_resolution()
            
            if not stream:
                raise Exception("Tidak ada stream tersedia")
            
            st.write(f"⬇️ Resolusi: **{stream.resolution}** | Size: **{stream.filesize_mb:.1f} MB**")
            
            with st.spinner("Mendownload dengan PoToken..."):
                stream.download(output_path=TEMP_DIR, filename="source.mp4")
            
            st.success("✅ Download dengan PoToken berhasil!")
            return True
    
    except Exception as e:
        st.error(f"❌ Pytubefix Error: {str(e)}")
        return False

# ==========================================
# PROCESS VIDEO DENGAN FFMPEG
# ==========================================
def generate_intervals(duration, num_clips, clip_len):
    """Generate timestamp untuk clips"""
    intervals = []
    start_safe = duration * 0.05
    end_safe = duration * 0.95
    playable = end_safe - start_safe
    
    if playable < clip_len:
        return [{"start": start_safe, "duration": min(clip_len, duration - start_safe)}]
    
    step = playable / (num_clips + 1)
    for i in range(1, num_clips + 1):
        mid = start_safe + (step * i)
        start = mid - (clip_len / 2)
        intervals.append({
            "start": start,
            "duration": clip_len
        })
    return intervals

def create_shorts_clip_ffmpeg(input_video, output_path, start_time, duration, add_subs=False):
    """
    Buat shorts clip dengan FFmpeg:
    - Cut dari start_time dengan duration
    - Crop ke center (9:16 ratio)
    - Resize ke 1080x1920
    """
    try:
        st.write(f"🎬 Processing: {os.path.basename(output_path)}...")
        
        # FFmpeg command
        cmd = [
            'ffmpeg',
            '-y',
            '-ss', str(start_time),
            '-i', input_video,
            '-t', str(duration),
            '-vf', 'crop=ih*9/16:ih,scale=1080:1920',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            output_path
        ]
        
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if process.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            st.success(f"✅ Selesai! ({file_size:.1f} MB)")
            return True
        else:
            st.error(f"❌ FFmpeg error")
            return False
            
    except subprocess.TimeoutExpired:
        st.error("⏱️ Timeout! Video terlalu besar.")
        return False
    except Exception as e:
        st.error(f"❌ Error: {e}")
        return False

# ==========================================
# UI UTAMA
# ==========================================
st.title("🎬 Auto Shorts - Pytubefix + FFmpeg")
st.caption("✨ Download YouTube dengan Pytubefix, Process dengan FFmpeg")

# Info banner
st.info("""
💡 **Untuk Streamlit Cloud:** Jika download gagal (bot detection/403), aktifkan **PoToken Manual** di sidebar.
PoToken valid 4-6 jam dan akan di-cache selama session aktif.
""")

# Check FFmpeg
if not check_ffmpeg():
    st.error("""
    ❌ **FFmpeg tidak ditemukan!**
    
    Pastikan file `packages.txt` berisi:
    ```
    ffmpeg
    ```
    """)
    st.stop()

st.success("✅ FFmpeg tersedia")

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ Input Video")
    
    input_type = st.radio(
        "Pilih metode:",
        ["YouTube URL", "Upload Video Manual"]
    )
    
    url = None
    uploaded_file = None
    use_potoken = False
    potoken_data = None
    
    if input_type == "YouTube URL":
        url = st.text_input("🔗 URL YouTube", placeholder="https://youtube.com/watch?v=...")
        
        st.divider()
        st.subheader("🔐 Opsi Download")
        
        use_potoken = st.checkbox(
            "Gunakan PoToken Manual",
            help="Aktifkan jika download gagal dengan error 403/bot detection"
        )
        
        if use_potoken:
            potoken_data = get_manual_potoken()
            if potoken_data:
                st.success("✅ PoToken siap!")
        else:
            st.info("ℹ️ Client ANDROID akan digunakan (tanpa PoToken)")
    
    else:
        uploaded_file = st.file_uploader("📤 Upload MP4", type=['mp4'])
    
    st.divider()
    st.subheader("⚙️ Pengaturan Klip")
    
    num_clips = st.slider("Jumlah Klip", 1, 5, 2)
    clip_duration = st.slider("Durasi per Klip (detik)", 15, 60, 30)
    
    st.divider()
    btn_start = st.button("🚀 Mulai Proses", type="primary", use_container_width=True)

# ==========================================
# TROUBLESHOOTING
# ==========================================
with st.expander("🆘 Troubleshooting"):
    st.markdown("""
    ### Problem: Error 403 / Bot Detection
    
    **Solusi:**
    1. ✅ Aktifkan "**Gunakan PoToken Manual**" di sidebar
    2. ✅ Ikuti panduan untuk mendapatkan PoToken dari browser
    3. ✅ Paste `visitorData` dan `poToken` ke form
    4. ✅ Klik "Mulai Proses"
    
    **Atau:**
    - Gunakan "Upload Video Manual" sebagai alternatif
    
    ---
    
    ### Problem: PoToken Expired
    
    **Ciri-ciri:**
    - Download gagal meski sudah pakai PoToken
    - Error "invalid token" atau sejenisnya
    
    **Solusi:**
    - Generate PoToken baru (valid 4-6 jam)
    - Gunakan mode Incognito saat generate
    
    ---
    
    ### Problem: Download Lambat/Timeout
    
    **Penyebab:**
    - Streamlit Cloud bandwidth terbatas
    - Video terlalu besar (>100MB)
    
    **Solusi:**
    - Pilih video lebih pendek (<10 menit)
    - Download di lokal, lalu upload manual
    
    ---
    
    ### Problem: FFmpeg Error
    
    **Solusi:**
    - Pastikan `packages.txt` berisi `ffmpeg`
    - Reboot app di Streamlit Cloud
    - Check logs untuk error detail
    """)

# ==========================================
# MAIN PROCESS
# ==========================================
if btn_start:
    source_video = f"{TEMP_DIR}/source.mp4"
    success = False
    
    # === STEP 1: GET VIDEO ===
    st.divider()
    st.subheader("📥 Step 1: Mendapatkan Video")
    
    if input_type == "YouTube URL":
        if not url:
            st.error("⚠️ Masukkan URL YouTube!")
            st.stop()
        
        # Validasi PoToken jika diaktifkan
        if use_potoken and not potoken_data:
            st.error("⚠️ Silakan masukkan Visitor Data dan PoToken terlebih dahulu!")
            st.stop()
        
        success = download_with_pytubefix(url, use_potoken, potoken_data)
        
        if not success and not use_potoken:
            st.info("💡 **Tip:** Coba aktifkan 'Gunakan PoToken Manual' di sidebar untuk bypass bot detection")
    
    else:  # Upload Manual
        if not uploaded_file:
            st.error("⚠️ Upload file video terlebih dahulu!")
            st.stop()
        
        with st.spinner("📤 Mengupload file..."):
            with open(source_video, 'wb') as f:
                f.write(uploaded_file.getbuffer())
        st.success("✅ Upload berhasil!")
        success = True
    
    if not success:
        st.stop()
    
    # === STEP 2: VIDEO INFO ===
    st.divider()
    st.subheader("📊 Step 2: Informasi Video")
    
    info = get_video_info(source_video)
    if not info:
        st.error("❌ Gagal membaca video info")
        st.stop()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Durasi", f"{int(info['duration'])}s")
    col2.metric("Resolusi", f"{info['width']}x{info['height']}")
    col3.metric("Size", f"{os.path.getsize(source_video)/(1024*1024):.1f} MB")
    
    # === STEP 3: GENERATE CLIPS ===
    st.divider()
    st.subheader("🎬 Step 3: Generate Shorts Clips")
    
    intervals = generate_intervals(info['duration'], num_clips, clip_duration)
    
    st.write(f"Akan membuat **{len(intervals)} klip** dengan durasi **{clip_duration}s** per klip")
    
    progress_bar = st.progress(0)
    
    # Create columns for display (max 3 per row)
    num_rows = (len(intervals) + 2) // 3
    
    clip_results = []
    
    for i, interval in enumerate(intervals):
        clip_name = f"Short_{i+1}.mp4"
        final_clip = f"{OUT_DIR}/{clip_name}"
        
        if create_shorts_clip_ffmpeg(
            source_video,
            final_clip,
            interval['start'],
            interval['duration']
        ):
            clip_results.append(final_clip)
        
        progress_bar.progress((i + 1) / len(intervals))
    
    # === STEP 4: DISPLAY RESULTS ===
    st.divider()
    st.subheader("✅ Step 4: Hasil Video")
    
    if clip_results:
        # Display in rows of 3
        for i in range(0, len(clip_results), 3):
            cols = st.columns(3)
            for j, clip_path in enumerate(clip_results[i:i+3]):
                with cols[j]:
                    st.video(clip_path)
                    with open(clip_path, 'rb') as f:
                        st.download_button(
                            f"⬇️ Download Klip {i+j+1}",
                            f,
                            file_name=os.path.basename(clip_path),
                            mime="video/mp4",
                            use_container_width=True
                        )
        
        st.success(f"🎉 **{len(clip_results)} klip** berhasil dibuat!")
        st.balloons()
    else:
        st.error("❌ Tidak ada klip yang berhasil dibuat")
    
    # Clean up temp files
    try:
        if os.path.exists(source_video):
            os.remove(source_video)
    except:
        pass
