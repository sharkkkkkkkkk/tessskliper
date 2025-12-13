import streamlit as st
import os
import subprocess
import json

# ==========================================
# KONFIGURASI
# ==========================================
st.set_page_config(page_title="Auto Shorts - yt-dlp", page_icon="🎬", layout="wide")

TEMP_DIR = "temp"
OUT_DIR = "output"
COOKIES_DIR = "cookies"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(COOKIES_DIR, exist_ok=True)

# ==========================================
# CHECK DEPENDENCIES
# ==========================================
def check_ytdlp():
    """Check if yt-dlp is available"""
    try:
        result = subprocess.run(['yt-dlp', '--version'], 
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def check_ffmpeg():
    """Check if ffmpeg is available"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False

# ==========================================
# COOKIES HANDLER
# ==========================================
def save_cookies_file(uploaded_file):
    """Save uploaded cookies file"""
    cookies_path = f"{COOKIES_DIR}/cookies.txt"
    
    try:
        with open(cookies_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        
        # Verify cookies format
        with open(cookies_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
            
            if lines:
                st.success(f"✅ Cookies loaded: {len(lines)} entries")
                return cookies_path
            else:
                st.error("❌ Cookies file kosong atau invalid")
                return None
    except Exception as e:
        st.error(f"❌ Error loading cookies: {e}")
        return None

# ==========================================
# DOWNLOAD WITH YT-DLP
# ==========================================
def download_with_ytdlp(url, cookies_path=None, quality="720"):
    """
    Download dengan yt-dlp (support cookies dengan sempurna)
    """
    output_path = f"{TEMP_DIR}/source.mp4"
    if os.path.exists(output_path):
        os.remove(output_path)
    
    try:
        st.write("🔄 Downloading dengan yt-dlp...")
        
        # Build yt-dlp command
        cmd = [
            'yt-dlp',
            '-f', f'best[height<={quality}]/best',  # Max quality
            '-o', output_path,
            '--no-playlist',
            '--no-warnings',
            '--newline',  # Progress per line
        ]
        
        # Add cookies if provided
        if cookies_path and os.path.exists(cookies_path):
            cmd.extend(['--cookies', cookies_path])
            st.info("🍪 Using cookies for authentication...")
        
        # Add URL
        cmd.append(url)
        
        st.caption(f"Command: `{' '.join(cmd[:5])}...`")
        
        # Execute with progress tracking
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for line in process.stdout:
            line = line.strip()
            
            # Parse download progress
            if '[download]' in line and '%' in line:
                try:
                    # Extract percentage
                    if 'ETA' in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if '%' in part:
                                percent_str = part.replace('%', '')
                                percent = float(percent_str)
                                progress_bar.progress(min(percent / 100, 1.0))
                                
                                # Extract size info
                                if 'of' in line:
                                    size_info = ' '.join(parts[parts.index('of'):parts.index('of')+2])
                                    status_text.text(f"📥 {percent:.1f}% {size_info}")
                                else:
                                    status_text.text(f"📥 {percent:.1f}%")
                                break
                except:
                    pass
            
            # Show other important info
            elif 'Destination' in line or 'Merging' in line:
                st.caption(line)
        
        process.wait()
        
        if process.returncode == 0 and os.path.exists(output_path):
            progress_bar.progress(1.0)
            status_text.empty()
            
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            st.success(f"✅ Download berhasil! ({file_size:.1f} MB)")
            return True
        else:
            st.error("❌ yt-dlp download failed")
            return False
            
    except Exception as e:
        st.error(f"❌ Error: {e}")
        return False

# ==========================================
# VIDEO PROCESSING
# ==========================================
def get_video_info(video_path):
    """Get video info using ffprobe"""
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
        
        return {'duration': duration, 'width': width, 'height': height}
    except Exception as e:
        st.error(f"Error: {e}")
        return None

def generate_intervals(duration, num_clips, clip_len):
    """Generate clip intervals"""
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
        intervals.append({"start": start, "duration": clip_len})
    return intervals

def create_shorts_clip(input_video, output_path, start_time, duration):
    """Create shorts clip with FFmpeg"""
    try:
        cmd = [
            'ffmpeg', '-y',
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
        return process.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# ==========================================
# UI
# ==========================================
st.title("🎬 Auto Shorts - yt-dlp Edition")
st.caption("✨ Ultimate solution dengan yt-dlp + cookies support")

# Info banner
st.success("""
🔥 **Why yt-dlp?**
- ✅ Cookies bekerja 100% sempurna
- ✅ Support semua jenis video (login-required, age-restricted, dll)
- ✅ Lebih stabil dari pytubefix
- ✅ Regular updates untuk bypass bot detection
- ✅ Industry standard untuk video downloading
""")

# Check dependencies
col1, col2 = st.columns(2)

with col1:
    if check_ytdlp():
        st.success("✅ yt-dlp tersedia")
    else:
        st.error("""
        ❌ **yt-dlp tidak ditemukan!**
        
        Tambahkan ke `packages.txt`:
        ```
        yt-dlp
        ```
        
        Atau install manual:
        ```bash
        pip install yt-dlp
        ```
        """)
        st.stop()

with col2:
    if check_ffmpeg():
        st.success("✅ FFmpeg tersedia")
    else:
        st.error("❌ FFmpeg tidak tersedia")
        st.stop()

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ Input")
    
    input_type = st.radio("Method:", ["YouTube URL", "Upload Manual"])
    
    url = None
    uploaded_file = None
    cookies_path = None
    use_cookies = False
    quality = "720"
    
    if input_type == "YouTube URL":
        url = st.text_input("🔗 URL YouTube", placeholder="https://youtube.com/watch?v=...")
        
        st.divider()
        st.subheader("🍪 Authentication")
        
        use_cookies = st.checkbox(
            "Use Cookies",
            value=True,
            help="Recommended untuk video yang butuh login"
        )
        
        if use_cookies:
            cookies_file = st.file_uploader(
                "Upload cookies.txt",
                type=['txt'],
                help="Netscape format dari browser"
            )
            
            if cookies_file:
                cookies_path = save_cookies_file(cookies_file)
        
        st.divider()
        st.subheader("🎥 Quality")
        
        quality = st.selectbox(
            "Max Resolution:",
            ["360", "480", "720", "1080"],
            index=2,
            help="Higher quality = larger file size"
        )
    
    else:
        uploaded_file = st.file_uploader("📤 Upload MP4", type=['mp4', 'mov', 'avi'])
    
    st.divider()
    st.subheader("⚙️ Clip Settings")
    num_clips = st.slider("Jumlah Klip", 1, 5, 2)
    clip_duration = st.slider("Durasi (detik)", 15, 60, 30)
    
    st.divider()
    btn_start = st.button("🚀 Process", type="primary", use_container_width=True)

# ==========================================
# INFO SECTIONS
# ==========================================
with st.expander("🍪 Cara Export Cookies"):
    st.markdown("""
    ### Method 1: Browser Extension ⭐
    
    **Chrome/Edge:**
    1. Install: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/cclelndahbckbenkjhflpdbgdldlbecc)
    2. Login ke YouTube
    3. Klik extension → Export
    4. Upload file ke app
    
    **Firefox:**
    1. Install: [cookies.txt](https://addons.mozilla.org/firefox/addon/cookies-txt/)
    2. Login ke YouTube
    3. Export cookies
    4. Upload ke app
    
    ---
    
    ### Method 2: yt-dlp Command
    
    ```bash
    # Extract cookies dari browser
    yt-dlp --cookies-from-browser chrome --cookies cookies.txt --skip-download [URL]
    ```
    
    Lalu upload `cookies.txt` yang dihasilkan.
    
    ---
    
    ### ⚠️ Important:
    - Cookies **wajib** untuk video login-required
    - Cookies expired dalam beberapa minggu
    - Jangan share cookies (berisi data login)
    """)

with st.expander("📦 Setup yt-dlp di Streamlit Cloud"):
    st.markdown("""
    ### File: `packages.txt`
    
    ```txt
    ffmpeg
    yt-dlp
    ```
    
    ### File: `requirements.txt`
    
    ```txt
    streamlit>=1.28.0
    numpy
    ```
    
    ### Deploy Steps:
    
    1. Buat/Update `packages.txt` dengan content di atas
    2. Commit & push ke GitHub
    3. Reboot app di Streamlit Cloud
    4. Tunggu 5-10 menit (install dependencies)
    5. Done! ✅
    
    ---
    
    ### Verify Installation:
    
    ```bash
    # Check yt-dlp version
    yt-dlp --version
    ```
    """)

with st.expander("🆘 Troubleshooting"):
    st.markdown("""
    ### Error: "yt-dlp tidak ditemukan"
    
    **Solusi:**
    1. Pastikan `packages.txt` berisi `yt-dlp`
    2. Reboot app di Streamlit Cloud
    3. Check logs untuk error
    
    ---
    
    ### Error: "HTTP Error 403"
    
    **Penyebab:**
    - Cookies tidak diupload
    - Cookies expired
    - Cookies format salah
    
    **Solusi:**
    1. Upload cookies.txt yang fresh
    2. Re-export dari browser
    3. Pastikan format Netscape
    
    ---
    
    ### Error: "Video unavailable"
    
    **Penyebab:**
    - Video private/deleted
    - Region locked
    - Age restricted
    
    **Solusi:**
    - Gunakan cookies dari browser yang sudah login
    - Gunakan VPN untuk region lock
    
    ---
    
    ### Best Practices:
    
    ✅ Selalu gunakan cookies (even untuk video public)
    ✅ Max quality 720p untuk balance speed/quality
    ✅ Video <15 menit untuk avoid timeout
    ✅ Re-export cookies setiap 1-2 minggu
    """)

# ==========================================
# MAIN PROCESS
# ==========================================
if btn_start:
    source_video = f"{TEMP_DIR}/source.mp4"
    success = False
    
    # Step 1: Acquire video
    st.divider()
    st.subheader("📥 Step 1: Download Video")
    
    if input_type == "YouTube URL":
        if not url:
            st.error("⚠️ Masukkan URL!")
            st.stop()
        
        if use_cookies and not cookies_path:
            st.warning("""
            ⚠️ **Cookies diaktifkan tapi file belum diupload!**
            
            Untuk video login-required, cookies wajib diupload.
            Untuk video public, cookies optional tapi recommended.
            """)
        
        success = download_with_ytdlp(url, cookies_path, quality)
    
    else:  # Upload manual
        if not uploaded_file:
            st.error("⚠️ Upload file!")
            st.stop()
        
        file_size = uploaded_file.size / (1024 * 1024)
        with st.spinner(f"📤 Uploading {file_size:.1f} MB..."):
            with open(source_video, 'wb') as f:
                f.write(uploaded_file.getbuffer())
        
        st.success(f"✅ Upload berhasil! ({file_size:.1f} MB)")
        success = True
    
    if not success:
        st.error("❌ Download gagal!")
        
        st.info("""
        💡 **Alternatif Solusi:**
        
        1. **Upload cookies.txt** jika belum
        2. **Download manual di lokal** lalu upload:
           ```bash
           yt-dlp --cookies cookies.txt -f "best[height<=720]" -o video.mp4 [URL]
           ```
        3. **Gunakan VPN** jika region-locked
        4. **Check video status** - pastikan tidak private/deleted
        """)
        st.stop()
    
    # Cleanup cookies
    if cookies_path and os.path.exists(cookies_path):
        try:
            os.remove(cookies_path)
            st.caption("🗑️ Cookies cleaned for security")
        except:
            pass
    
    # Step 2: Analyze video
    st.divider()
    st.subheader("📊 Step 2: Analyze Video")
    
    info = get_video_info(source_video)
    if not info:
        st.error("❌ Failed to read video")
        st.stop()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Duration", f"{int(info['duration'])}s")
    col2.metric("Resolution", f"{info['width']}x{info['height']}")
    col3.metric("Aspect", f"{info['width']/info['height']:.2f}:1")
    col4.metric("Size", f"{os.path.getsize(source_video)/(1024*1024):.1f} MB")
    
    # Check aspect ratio
    is_portrait = info['height'] > info['width']
    if is_portrait:
        st.success("✅ Portrait video - Perfect untuk Shorts!")
    else:
        st.info("ℹ️ Landscape video - Akan di-crop ke 9:16")
    
    # Step 3: Generate clips
    st.divider()
    st.subheader("🎬 Step 3: Generate Clips")
    
    intervals = generate_intervals(info['duration'], num_clips, clip_duration)
    st.write(f"Generating **{len(intervals)} clips** @ **{clip_duration}s** each")
    
    progress_bar = st.progress(0)
    clip_results = []
    
    for i, interval in enumerate(intervals):
        clip_name = f"Short_{i+1}.mp4"
        final_clip = f"{OUT_DIR}/{clip_name}"
        
        with st.spinner(f"Processing clip {i+1}/{len(intervals)}..."):
            if create_shorts_clip(source_video, final_clip, interval['start'], interval['duration']):
                clip_results.append(final_clip)
                st.success(f"✅ Clip {i+1} done")
            else:
                st.error(f"❌ Clip {i+1} failed")
        
        progress_bar.progress((i + 1) / len(intervals))
    
    # Step 4: Results
    st.divider()
    st.subheader("✅ Step 4: Download Results")
    
    if clip_results:
        total_size = sum(os.path.getsize(c) for c in clip_results) / (1024 * 1024)
        st.info(f"📦 **{len(clip_results)} clips** created | **{total_size:.1f} MB** total")
        
        # Display in grid
        for i in range(0, len(clip_results), 3):
            cols = st.columns(3)
            for j, clip_path in enumerate(clip_results[i:i+3]):
                with cols[j]:
                    clip_size = os.path.getsize(clip_path) / (1024 * 1024)
                    st.video(clip_path)
                    st.caption(f"📊 {clip_size:.1f} MB | 🎬 1080x1920")
                    
                    with open(clip_path, 'rb') as f:
                        st.download_button(
                            "⬇️ Download",
                            f,
                            file_name=os.path.basename(clip_path),
                            mime="video/mp4",
                            use_container_width=True,
                            key=f"dl_{i}_{j}"
                        )
        
        st.success(f"🎉 {len(clip_results)} clips berhasil!")
        st.balloons()
        
        # Platform tips
        with st.expander("📱 Tips Upload ke Platform"):
            st.markdown("""
            ### TikTok
            - Max: 10 menit
            - Ratio: 9:16 ✅
            - Size: <287 MB
            
            ### Instagram Reels
            - Max: 90 detik
            - Ratio: 9:16 ✅
            - Size: <100 MB
            
            ### YouTube Shorts
            - Max: 60 detik
            - Ratio: 9:16 ✅
            - Size: <256 MB
            
            ### Tips:
            - Upload saat peak hours (18:00-22:00)
            - Gunakan trending audio
            - Tambahkan hashtag relevant
            - Engaging thumbnail untuk YouTube
            """)
    else:
        st.error("❌ No clips created")
    
    # Cleanup
    try:
        if os.path.exists(source_video):
            os.remove(source_video)
            st.caption("🗑️ Temp files cleaned")
    except:
        pass
