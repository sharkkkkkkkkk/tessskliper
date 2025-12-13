import streamlit as st
import os
import subprocess
import json
import random
import time
from pytubefix import YouTube
from pytubefix.cli import on_progress

# ==========================================
# KONFIGURASI
# ==========================================
st.set_page_config(page_title="Auto Shorts Stealth", page_icon="🥷", layout="wide")

TEMP_DIR = "temp"
OUT_DIR = "output"
COOKIES_DIR = "cookies"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(COOKIES_DIR, exist_ok=True)

# ==========================================
# USER AGENT POOL
# ==========================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def get_browser_headers(user_agent=None):
    if not user_agent:
        user_agent = get_random_user_agent()
    
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,id;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    return headers

# ==========================================
# COOKIES HANDLER
# ==========================================
def parse_cookies_txt(cookies_content):
    """Parse Netscape cookies.txt format"""
    cookies = {}
    
    for line in cookies_content.split('\n'):
        line = line.strip()
        
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue
        
        try:
            # Netscape format: domain, flag, path, secure, expiration, name, value
            parts = line.split('\t')
            if len(parts) >= 7:
                name = parts[5]
                value = parts[6]
                cookies[name] = value
        except:
            continue
    
    return cookies

def save_cookies_file(uploaded_file):
    """Save uploaded cookies file"""
    cookies_path = f"{COOKIES_DIR}/cookies.txt"
    
    try:
        with open(cookies_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        
        # Verify cookies
        with open(cookies_path, 'r', encoding='utf-8') as f:
            content = f.read()
            cookies = parse_cookies_txt(content)
            
            if cookies:
                st.success(f"✅ Cookies loaded: {len(cookies)} entries")
                return cookies_path
            else:
                st.error("❌ Cookies file invalid atau kosong")
                return None
    except Exception as e:
        st.error(f"❌ Error loading cookies: {e}")
        return None

# ==========================================
# DOWNLOAD WITH COOKIES
# ==========================================
def download_with_cookies(url, cookies_path=None, method="auto", max_retries=3):
    """
    Download dengan cookies support untuk video yang butuh login
    """
    output_path = f"{TEMP_DIR}/source.mp4"
    if os.path.exists(output_path):
        os.remove(output_path)
    
    # Methods to try
    methods = []
    if method == "auto":
        methods = [
            ('ANDROID', 'Android Mobile'),
            ('WEB', 'Desktop Browser'),
            ('IOS', 'iOS Safari'),
            ('ANDROID_CREATOR', 'Android Creator Studio'),
            ('WEB_CREATOR', 'Desktop Creator Studio'),
        ]
    else:
        methods = [(method, method)]
    
    last_error = None
    attempt_count = 0
    
    for client_type, client_name in methods:
        for retry in range(max_retries):
            attempt_count += 1
            
            try:
                user_agent = get_random_user_agent()
                retry_text = f" (Retry {retry + 1}/{max_retries})" if retry > 0 else ""
                
                st.write(f"🔄 Attempt #{attempt_count}: **{client_name}**{retry_text}")
                st.caption(f"User-Agent: `{user_agent[:60]}...`")
                
                if retry > 0:
                    delay = min(2 ** retry, 10)
                    with st.spinner(f"Waiting {delay}s..."):
                        time.sleep(delay)
                
                # Create YouTube object dengan cookies
                if cookies_path and os.path.exists(cookies_path):
                    st.info("🍪 Using cookies for authentication...")
                    
                    yt = YouTube(
                        url,
                        client=client_type,
                        use_oauth=False,
                        allow_oauth_cache=True,
                        on_progress_callback=on_progress
                    )
                    
                    # Load cookies into pytubefix
                    try:
                        with open(cookies_path, 'r', encoding='utf-8') as f:
                            cookies_content = f.read()
                            cookies_dict = parse_cookies_txt(cookies_content)
                            
                            # Inject cookies ke session
                            if hasattr(yt, '_session'):
                                for name, value in cookies_dict.items():
                                    yt._session.cookies.set(name, value, domain='.youtube.com')
                            
                            st.caption(f"✅ Loaded {len(cookies_dict)} cookies")
                    except Exception as e:
                        st.warning(f"⚠️ Cookies load error: {e}")
                else:
                    yt = YouTube(
                        url,
                        client=client_type,
                        use_oauth=False,
                        allow_oauth_cache=False,
                        on_progress_callback=on_progress
                    )
                
                # Custom headers
                import requests
                session = requests.Session()
                session.headers.update(get_browser_headers(user_agent))
                
                if hasattr(yt, '_session'):
                    yt._session.headers.update(get_browser_headers(user_agent))
                
                st.info(f"📹 **{yt.title}**")
                st.info(f"⏱️ **{yt.length // 60}:{yt.length % 60:02d}** | 👁️ **{yt.views:,}** views")
                
                # Get stream
                stream = yt.streams.filter(
                    progressive=True,
                    file_extension='mp4'
                ).order_by('resolution').desc().first()
                
                if not stream:
                    st.warning("Progressive not available, trying adaptive...")
                    stream = yt.streams.filter(
                        adaptive=True,
                        file_extension='mp4',
                        type='video'
                    ).order_by('resolution').desc().first()
                
                if not stream:
                    raise Exception("No streams available")
                
                st.write(f"⬇️ Resolution: **{stream.resolution}** | Size: **{stream.filesize_mb:.1f} MB**")
                
                # Progress callback
                progress_placeholder = st.empty()
                progress_bar = st.progress(0)
                
                def progress_callback(stream, chunk, bytes_remaining):
                    total_size = stream.filesize
                    bytes_downloaded = total_size - bytes_remaining
                    percentage = (bytes_downloaded / total_size) * 100
                    
                    progress_bar.progress(min(percentage / 100, 1.0))
                    progress_placeholder.text(f"📥 {percentage:.1f}% ({bytes_downloaded/(1024*1024):.1f}/{total_size/(1024*1024):.1f} MB)")
                
                yt.register_on_progress_callback(progress_callback)
                
                with st.spinner("Downloading..."):
                    stream.download(output_path=TEMP_DIR, filename="source.mp4")
                
                progress_bar.progress(1.0)
                progress_placeholder.empty()
                
                st.success(f"✅ Download successful with **{client_name}** (Attempt #{attempt_count})!")
                return True
                
            except Exception as e:
                error_msg = str(e).lower()
                last_error = str(e)
                
                if 'login' in error_msg or 'sign in' in error_msg:
                    st.warning(f"⚠️ {client_name} {retry_text}: Requires login/cookies")
                elif '403' in error_msg or 'forbidden' in error_msg:
                    st.warning(f"⚠️ {client_name} {retry_text}: Blocked (403)")
                elif '429' in error_msg:
                    st.warning(f"⚠️ {client_name} {retry_text}: Rate limited (429)")
                else:
                    st.warning(f"⚠️ {client_name} {retry_text}: {str(e)[:100]}")
                
                if retry < max_retries - 1:
                    continue
                else:
                    break
    
    st.error(f"❌ All methods failed after {attempt_count} attempts.")
    
    with st.expander("🔍 Error Details"):
        st.code(last_error)
    
    if 'login' in str(last_error).lower() or 'sign in' in str(last_error).lower():
        st.error("""
        🔐 **Video ini membutuhkan login!**
        
        Upload cookies.txt untuk bypass:
        1. Aktifkan "Use Cookies" di sidebar
        2. Upload file cookies.txt dari browser
        """)
    
    return False

# ==========================================
# VIDEO PROCESSING (same as before)
# ==========================================
def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def get_video_info(video_path):
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', 
               '-show_format', '-show_streams', video_path]
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
    try:
        cmd = [
            'ffmpeg', '-y', '-ss', str(start_time), '-i', input_video,
            '-t', str(duration), '-vf', 'crop=ih*9/16:ih,scale=1080:1920',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart',
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
st.title("🥷 Auto Shorts - Stealth Mode + Cookies")
st.caption("✨ Support untuk video yang butuh login dengan cookies.txt")

st.success("""
🔒 **Features:**
- ✅ User-Agent rotation (14+ browsers)
- ✅ Browser-like headers
- ✅ **Cookies support untuk video login-only**
- ✅ Auto retry dengan exponential backoff
- ✅ Multi-client fallback
""")

if not check_ffmpeg():
    st.error("❌ FFmpeg tidak tersedia")
    st.stop()

st.success("✅ FFmpeg tersedia")

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ Input")
    
    input_type = st.radio("Method:", ["YouTube URL (Stealth)", "Upload Manual"])
    
    url = None
    uploaded_file = None
    cookies_path = None
    use_cookies = False
    
    if input_type == "YouTube URL (Stealth)":
        url = st.text_input("🔗 URL YouTube", placeholder="https://youtube.com/watch?v=...")
        
        st.divider()
        st.subheader("🍪 Cookies (Optional)")
        
        use_cookies = st.checkbox(
            "Use Cookies", 
            help="Untuk video yang butuh login/private/restricted"
        )
        
        if use_cookies:
            cookies_file = st.file_uploader(
                "Upload cookies.txt",
                type=['txt'],
                help="Netscape format cookies dari browser"
            )
            
            if cookies_file:
                cookies_path = save_cookies_file(cookies_file)
        
        st.divider()
        st.subheader("🎯 Settings")
        
        download_method = st.selectbox(
            "Client:",
            ["auto", "ANDROID", "WEB", "IOS", "ANDROID_CREATOR", "WEB_CREATOR"]
        )
        
        max_retries = st.slider("Retries per Method", 1, 5, 3)
    else:
        uploaded_file = st.file_uploader("📤 Upload MP4", type=['mp4'])
    
    st.divider()
    st.subheader("⚙️ Clip Settings")
    num_clips = st.slider("Jumlah Klip", 1, 5, 2)
    clip_duration = st.slider("Durasi (detik)", 15, 60, 30)
    
    st.divider()
    btn_start = st.button("🚀 Process", type="primary", use_container_width=True)

# ==========================================
# INFO: CARA MENDAPATKAN COOKIES
# ==========================================
with st.expander("🍪 Cara Mendapatkan cookies.txt"):
    st.markdown("""
    ### Method 1: Browser Extension (Recommended) ⭐
    
    **Chrome/Edge:**
    1. Install extension: **"Get cookies.txt LOCALLY"**
       - https://chrome.google.com/webstore/detail/get-cookiestxt-locally/
    2. Login ke YouTube
    3. Klik extension icon
    4. Download cookies.txt
    5. Upload ke app ini
    
    **Firefox:**
    1. Install addon: **"cookies.txt"**
       - https://addons.mozilla.org/firefox/addon/cookies-txt/
    2. Login ke YouTube
    3. Klik addon icon
    4. Export cookies
    5. Upload ke app ini
    
    ---
    
    ### Method 2: Manual (Developer Tools)
    
    1. Login ke YouTube
    2. Tekan **F12** → Tab **Application/Storage**
    3. Pilih **Cookies** → **https://youtube.com**
    4. Copy semua cookies dalam format Netscape:
       ```
       .youtube.com	TRUE	/	TRUE	0	COOKIE_NAME	COOKIE_VALUE
       ```
    5. Save sebagai `cookies.txt`
    6. Upload ke app
    
    ---
    
    ### Method 3: yt-dlp (untuk technical users)
    
    ```bash
    # Extract cookies dari browser
    yt-dlp --cookies-from-browser chrome --cookies cookies.txt [URL]
    ```
    
    ---
    
    ### ⚠️ Important Notes:
    
    - **Jangan share cookies.txt** - berisi data login Anda
    - Cookies bersifat **temporary** - expired dalam beberapa minggu
    - File cookies akan **dihapus otomatis** setelah proses
    - Hanya digunakan untuk request ke YouTube, tidak disimpan
    
    ---
    
    ### Format cookies.txt (Netscape):
    
    ```
    # Netscape HTTP Cookie File
    .youtube.com	TRUE	/	TRUE	1735689600	CONSENT	YES+
    .youtube.com	TRUE	/	TRUE	1735689600	VISITOR_INFO1_LIVE	xxx
    .youtube.com	TRUE	/	TRUE	1735689600	YSC	xxx
    ```
    """)

with st.expander("🆘 Troubleshooting"):
    st.markdown("""
    ### Error: "Requires login to view"
    
    **Solusi:**
    1. ✅ Aktifkan "Use Cookies"
    2. ✅ Upload cookies.txt dari browser yang sudah login
    3. ✅ Pastikan cookies fresh (baru di-export)
    
    ---
    
    ### Error: "Invalid cookies"
    
    **Penyebab:**
    - Format cookies salah
    - Cookies expired
    - Export dari browser yang salah
    
    **Solusi:**
    - Re-export cookies dengan extension
    - Pastikan format Netscape
    - Login ulang ke YouTube lalu export
    
    ---
    
    ### Error: Tetap 403 meski pakai cookies
    
    **Solusi:**
    - Cookies mungkin expired
    - Re-export cookies baru
    - Coba client method berbeda
    - Gunakan Upload Manual
    """)

# ==========================================
# MAIN PROCESS
# ==========================================
if btn_start:
    source_video = f"{TEMP_DIR}/source.mp4"
    success = False
    
    st.divider()
    st.subheader("📥 Step 1: Acquire Video")
    
    if input_type == "YouTube URL (Stealth)":
        if not url:
            st.error("⚠️ Masukkan URL!")
            st.stop()
        
        if use_cookies and not cookies_path:
            st.warning("⚠️ Cookies enabled tapi file belum diupload")
        
        success = download_with_cookies(
            url, 
            cookies_path if use_cookies else None,
            download_method, 
            max_retries
        )
    else:
        if not uploaded_file:
            st.error("⚠️ Upload file!")
            st.stop()
        
        with st.spinner("📤 Uploading..."):
            with open(source_video, 'wb') as f:
                f.write(uploaded_file.getbuffer())
        st.success("✅ Upload berhasil!")
        success = True
    
    if not success:
        st.stop()
    
    # Cleanup cookies after use
    if cookies_path and os.path.exists(cookies_path):
        try:
            os.remove(cookies_path)
            st.caption("🗑️ Cookies cleaned for security")
        except:
            pass
    
    st.divider()
    st.subheader("📊 Step 2: Analyze Video")
    
    info = get_video_info(source_video)
    if not info:
        st.error("❌ Failed to read video")
        st.stop()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Duration", f"{int(info['duration'])}s")
    col2.metric("Resolution", f"{info['width']}x{info['height']}")
    col3.metric("Size", f"{os.path.getsize(source_video)/(1024*1024):.1f} MB")
    
    st.divider()
    st.subheader("🎬 Step 3: Generate Clips")
    
    intervals = generate_intervals(info['duration'], num_clips, clip_duration)
    
    progress_bar = st.progress(0)
    clip_results = []
    
    for i, interval in enumerate(intervals):
        clip_name = f"Short_{i+1}.mp4"
        final_clip = f"{OUT_DIR}/{clip_name}"
        
        if create_shorts_clip(source_video, final_clip, interval['start'], interval['duration']):
            clip_results.append(final_clip)
            st.success(f"✅ Clip {i+1}")
        
        progress_bar.progress((i + 1) / len(intervals))
    
    st.divider()
    st.subheader("✅ Step 4: Results")
    
    if clip_results:
        for i in range(0, len(clip_results), 3):
            cols = st.columns(3)
            for j, clip_path in enumerate(clip_results[i:i+3]):
                with cols[j]:
                    st.video(clip_path)
                    with open(clip_path, 'rb') as f:
                        st.download_button(
                            "⬇️ Download",
                            f,
                            file_name=os.path.basename(clip_path),
                            mime="video/mp4",
                            use_container_width=True,
                            key=f"dl_{i}_{j}"
                        )
        
        st.success(f"🎉 {len(clip_results)} clips created!")
        st.balloons()
    
    try:
        if os.path.exists(source_video):
            os.remove(source_video)
    except:
        pass
