import streamlit as st
import os
import subprocess
import json
import requests
import re

# ==========================================
# KONFIGURASI
# ==========================================
st.set_page_config(page_title="Auto Shorts - RapidAPI", page_icon="🚀", layout="wide")

TEMP_DIR = "temp"
OUT_DIR = "output"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# RapidAPI Configuration
RAPIDAPI_KEY = "75101489acmshbc6c10ab7c834eep1cf630jsn7d5a199afa41"
RAPIDAPI_HOST = "youtube-media-downloader.p.rapidapi.com"
RAPIDAPI_URL = f"https://{RAPIDAPI_HOST}/v2/video/details"

# ==========================================
# CHECK DEPENDENCIES
# ==========================================
def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False

# ==========================================
# EXTRACT VIDEO ID FROM URL
# ==========================================
def extract_video_id(url):
    """
    Extract video ID from various YouTube URL formats
    """
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

# ==========================================
# RAPIDAPI DOWNLOAD FUNCTION
# ==========================================
def download_with_rapidapi(youtube_url, quality="720"):
    """
    Download video menggunakan RapidAPI YouTube Media Downloader
    """
    output_path = f"{TEMP_DIR}/source.mp4"
    if os.path.exists(output_path):
        os.remove(output_path)
    
    try:
        # Extract video ID
        video_id = extract_video_id(youtube_url)
        
        if not video_id:
            st.error("❌ Invalid YouTube URL! Cannot extract video ID")
            return False
        
        st.info(f"🎯 Video ID: `{video_id}`")
        
        # Step 1: Get video details & download links
        st.info("📡 Fetching video details from RapidAPI...")
        
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST
        }
        
        # Quality mapping
        quality_map = {
            "360": "360p",
            "480": "480p",
            "720": "720p",
            "1080": "1080p"
        }
        
        target_quality = quality_map.get(quality, "720p")
        
        params = {
            "videoId": video_id,
            "urlAccess": "normal",
            "videos": "auto",
            "audios": "auto"
        }
        
        response = requests.get(RAPIDAPI_URL, headers=headers, params=params, timeout=30)
        
        if response.status_code != 200:
            st.error(f"❌ API Error: Status {response.status_code}")
            st.error(f"Response: {response.text[:500]}")
            return False
        
        data = response.json()
        
        # Debug: Show API response structure
        with st.expander("🔍 Debug: API Response"):
            st.json(data)
        
        # Parse response untuk dapat download link
        download_url = None
        selected_quality = None
        
        # Check if videos array exists
        if 'videos' in data and data['videos']:
            videos = data['videos']
            
            st.info(f"📹 Found {len(videos)} video formats")
            
            # Try to find exact quality match
            for video in videos:
                if video.get('quality') == target_quality and video.get('url'):
                    download_url = video['url']
                    selected_quality = video['quality']
                    break
            
            # If no exact match, get closest quality
            if not download_url:
                # Sort by quality (descending)
                quality_order = ["1080p", "720p", "480p", "360p", "240p", "144p"]
                
                for q in quality_order:
                    if q <= target_quality or not download_url:
                        for video in videos:
                            if video.get('quality') == q and video.get('url'):
                                download_url = video['url']
                                selected_quality = video['quality']
                                break
                        if download_url:
                            break
            
            # Last resort: take first available
            if not download_url and videos:
                for video in videos:
                    if video.get('url'):
                        download_url = video['url']
                        selected_quality = video.get('quality', 'unknown')
                        break
        
        elif 'url' in data:
            # Direct URL in response
            download_url = data['url']
            selected_quality = data.get('quality', 'auto')
        
        if not download_url:
            st.error("❌ Tidak dapat menemukan download URL dalam response")
            st.info("💡 Cek struktur response di Debug section di atas")
            return False
        
        st.success(f"✅ Found video: **{selected_quality}**")
        
        # Step 2: Download video dari URL
        st.info(f"📥 Downloading video...")
        
        with requests.get(download_url, stream=True, timeout=600) as r:
            r.raise_for_status()
            
            total_size = int(r.headers.get('content-length', 0))
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = downloaded / total_size
                            progress_bar.progress(min(progress, 1.0))
                            status_text.text(
                                f"📥 {downloaded/(1024*1024):.1f} MB / "
                                f"{total_size/(1024*1024):.1f} MB "
                                f"({progress*100:.1f}%)"
                            )
                        else:
                            status_text.text(f"📥 {downloaded/(1024*1024):.1f} MB downloaded...")
        
        progress_bar.progress(1.0)
        status_text.empty()
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            st.success(f"✅ Download berhasil! ({file_size:.1f} MB)")
            return True
        else:
            st.error("❌ File tidak ditemukan atau kosong setelah download")
            return False
            
    except requests.exceptions.Timeout:
        st.error("❌ Request timeout! Video mungkin terlalu besar atau koneksi lambat.")
        return False
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Network error: {str(e)[:200]}")
        return False
    except Exception as e:
        st.error(f"❌ Error: {str(e)[:200]}")
        import traceback
        with st.expander("🔍 Error Details"):
            st.code(traceback.format_exc())
        return False

# ==========================================
# VIDEO PROCESSING
# ==========================================
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
        st.error(f"Error getting video info: {e}")
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
        st.error(f"Error creating clip: {e}")
        return False

# ==========================================
# UI
# ==========================================
st.title("🚀 Auto Shorts - YouTube Media Downloader")
st.caption("✨ Fast YouTube downloader dengan RapidAPI - Generate shorts otomatis!")

# Banner
st.success("""
🔥 **Features:**
- ✅ RapidAPI YouTube Media Downloader
- ✅ Multi-quality support (360p - 1080p)
- ✅ Auto video ID extraction
- ✅ Fast & reliable download
- ✅ Auto shorts generation (9:16)
- ✅ No proxy needed!
""")

# Check dependencies
if check_ffmpeg():
    st.success("✅ FFmpeg OK")
else:
    st.error("❌ FFmpeg missing - Install dulu!")
    st.code("# Ubuntu/Debian\nsudo apt install ffmpeg\n\n# MacOS\nbrew install ffmpeg", language="bash")
    st.stop()

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ Input")
    
    input_type = st.radio("Method:", ["YouTube URL", "Upload Manual"])
    
    url = None
    uploaded_file = None
    quality = "720"
    
    if input_type == "YouTube URL":
        url = st.text_input(
            "🔗 YouTube URL / Video ID", 
            placeholder="https://youtube.com/watch?v=... atau G33j5Qi4rE8",
            help="Paste full YouTube URL atau video ID saja"
        )
        
        st.caption("**Supported formats:**")
        st.caption("• `https://youtube.com/watch?v=...`")
        st.caption("• `https://youtu.be/...`")
        st.caption("• `G33j5Qi4rE8` (video ID only)")
        
        st.divider()
        st.subheader("🎥 Settings")
        
        quality = st.selectbox(
            "Quality:", 
            ["360", "480", "720", "1080"], 
            index=2,
            help="Target video quality (akan pilih closest jika tidak tersedia)"
        )
    
    else:
        uploaded_file = st.file_uploader("📤 Upload MP4", type=['mp4'])
    
    st.divider()
    st.subheader("⚙️ Clip Settings")
    num_clips = st.slider("Jumlah Klip", 1, 5, 2, help="Berapa banyak shorts yang akan dibuat")
    clip_duration = st.slider("Durasi (detik)", 15, 60, 30, help="Durasi setiap shorts clip")
    
    st.divider()
    btn_start = st.button("🚀 Process", type="primary", use_container_width=True)

# ==========================================
# INFO
# ==========================================
with st.expander("📚 Cara Pakai"):
    st.markdown("""
    ### Quick Start:
    
    **Method 1: YouTube URL**
    1. Copy YouTube video URL
    2. Paste di input box
    3. Pilih quality (360p - 1080p)
    4. Set jumlah clips & durasi
    5. Klik **Process**!
    
    **Method 2: Video ID Only**
    - Bisa paste video ID langsung
    - Contoh: `G33j5Qi4rE8`
    - Lebih cepat & simple!
    
    **Method 3: Upload Manual**
    - Upload MP4 dari device Anda
    - Skip download step
    - Langsung generate shorts
    
    ---
    
    ### Supported URL Formats:
    
    ✅ `https://www.youtube.com/watch?v=G33j5Qi4rE8`
    ✅ `https://youtu.be/G33j5Qi4rE8`
    ✅ `https://youtube.com/embed/G33j5Qi4rE8`
    ✅ `G33j5Qi4rE8` (Video ID only)
    
    ---
    
    ### Output:
    
    - Format: MP4 (9:16 vertical)
    - Resolution: 1080x1920 (optimized untuk shorts)
    - Codec: H.264 + AAC
    - Ready untuk upload ke TikTok/Reels/Shorts!
    """)

with st.expander("🚀 Tentang API"):
    st.markdown("""
    ### YouTube Media Downloader API
    
    **Endpoint:** `/v2/video/details`
    
    **Parameters:**
    - `videoId`: YouTube video ID
    - `urlAccess`: normal (public videos)
    - `videos`: auto (all video formats)
    - `audios`: auto (all audio formats)
    
    **Response:**
    ```json
    {
      "videos": [
        {
          "quality": "720p",
          "url": "https://...",
          "format": "mp4"
        }
      ]
    }
    ```
    
    ---
    
    ### Keuntungan:
    
    ✅ **Fast & Reliable**
    - Server-side processing
    - High-speed CDN
    - 99.9% uptime
    
    ✅ **Multi-Quality**
    - Support 144p - 1080p
    - Auto fallback ke closest quality
    - Flexible format selection
    
    ✅ **No Blocking**
    - API key authentication
    - No IP restrictions
    - No CAPTCHA
    
    ---
    
    ### API Key:
    
    Currently using hardcoded key.
    
    Get your own key at: https://rapidapi.com
    """)

with st.expander("🆘 Troubleshooting"):
    st.markdown("""
    ### Problem: Cannot extract video ID
    
    **Solusi:**
    - Pastikan URL valid
    - Coba paste video ID saja
    - Check URL format di guide
    
    ---
    
    ### Problem: API Error 401
    
    **Penyebab:** Invalid API key
    
    **Solusi:**
    - Check API key di RapidAPI dashboard
    - Update key di kode
    
    ---
    
    ### Problem: API Error 429
    
    **Penyebab:** Rate limit exceeded
    
    **Solusi:**
    - Wait beberapa menit
    - Upgrade API plan
    - Use different API key
    
    ---
    
    ### Problem: No download URL found
    
    **Penyebab:**
    - Video private/age-restricted
    - Region-locked content
    - API structure changed
    
    **Solusi:**
    1. Try different video
    2. Check debug section
    3. Use Upload Manual instead
    
    ---
    
    ### Problem: Download stuck/timeout
    
    **Solusi:**
    - Check internet connection
    - Try lower quality (360p/480p)
    - Refresh page & retry
    
    ---
    
    ### Best Practices:
    
    ✅ Test dengan video pendek dulu
    ✅ Start dengan 720p quality
    ✅ Monitor API quota
    ✅ Keep Upload Manual as backup
    """)

# ==========================================
# MAIN PROCESS
# ==========================================
if btn_start:
    source_video = f"{TEMP_DIR}/source.mp4"
    success = False
    
    st.divider()
    st.subheader("📥 Step 1: Download")
    
    if input_type == "YouTube URL":
        if not url:
            st.error("⚠️ Masukkan YouTube URL atau Video ID!")
            st.stop()
        
        success = download_with_rapidapi(url, quality)
    
    else:
        if not uploaded_file:
            st.error("⚠️ Upload file dulu!")
            st.stop()
        
        with st.spinner("📤 Uploading..."):
            with open(source_video, 'wb') as f:
                f.write(uploaded_file.getbuffer())
        
        file_size = os.path.getsize(source_video) / (1024 * 1024)
        st.success(f"✅ Upload OK! ({file_size:.1f} MB)")
        success = True
    
    if not success:
        st.error("❌ Download failed!")
        st.info("""
        💡 **Try:**
        1. Check debug section untuk API response
        2. Verify video ID / URL valid
        3. Try different video
        4. Use Upload Manual as alternative
        """)
        st.stop()
    
    # Step 2: Analyze
    st.divider()
    st.subheader("📊 Step 2: Analyze")
    
    info = get_video_info(source_video)
    if not info:
        st.error("❌ Failed to analyze video")
        st.stop()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Duration", f"{int(info['duration'])}s")
    col2.metric("Resolution", f"{info['width']}x{info['height']}")
    col3.metric("Size", f"{os.path.getsize(source_video)/(1024*1024):.1f} MB")
    
    # Step 3: Generate clips
    st.divider()
    st.subheader("🎬 Step 3: Generate Shorts Clips")
    
    intervals = generate_intervals(info['duration'], num_clips, clip_duration)
    
    progress_bar = st.progress(0)
    clip_results = []
    
    for i, interval in enumerate(intervals):
        clip_name = f"Short_{i+1}.mp4"
        final_clip = f"{OUT_DIR}/{clip_name}"
        
        with st.spinner(f"⚙️ Creating clip {i+1}/{len(intervals)}..."):
            if create_shorts_clip(source_video, final_clip, interval['start'], interval['duration']):
                clip_results.append(final_clip)
                st.success(f"✅ Clip {i+1} done! (Start: {int(interval['start'])}s)")
        
        progress_bar.progress((i + 1) / len(intervals))
    
    # Step 4: Results
    st.divider()
    st.subheader("✅ Step 4: Download Clips")
    
    if clip_results:
        st.success(f"🎉 **{len(clip_results)} shorts clips** berhasil dibuat!")
        
        for i in range(0, len(clip_results), 3):
            cols = st.columns(3)
            for j, clip_path in enumerate(clip_results[i:i+3]):
                with cols[j]:
                    st.video(clip_path)
                    
                    file_size = os.path.getsize(clip_path) / (1024 * 1024)
                    st.caption(f"📦 Size: {file_size:.1f} MB")
                    st.caption(f"📐 Format: 1080x1920 (9:16)")
                    
                    with open(clip_path, 'rb') as f:
                        st.download_button(
                            f"⬇️ Download Clip {i+j+1}",
                            f,
                            file_name=os.path.basename(clip_path),
                            mime="video/mp4",
                            use_container_width=True,
                            key=f"dl_{i}_{j}"
                        )
        
        st.balloons()
    else:
        st.warning("⚠️ No clips were generated")
    
    # Cleanup source video
    try:
        if os.path.exists(source_video):
            os.remove(source_video)
            st.caption("🧹 Temporary files cleaned")
    except:
        pass

# ==========================================
# FOOTER
# ==========================================
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("🚀 Auto Shorts Generator")
with col2:
    st.caption("💡 Powered by RapidAPI")
with col3:
    st.caption("❤️ Made with Streamlit")
