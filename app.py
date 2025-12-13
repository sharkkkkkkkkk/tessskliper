import streamlit as st
import http.client
import json
import re

# ==========================================
# KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="YouTube Downloader (Python)", page_icon="YX", layout="centered")

# CSS Agar tampilan mirip Apps
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    .download-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border: 1px solid #ddd;
    }
    .badge-video { background-color: #007bff; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-right: 5px; }
    .badge-audio { background-color: #6c757d; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-right: 5px; }
    </style>
""", unsafe_allow_html=True)

# API CONFIG
RAPIDAPI_KEY = "75101489acmshbc6c10ab7c834eep1cf630jsn7d5a199afa41"
RAPIDAPI_HOST = "youtube-media-downloader.p.rapidapi.com"

# ==========================================
# FUNGSI UTAMA
# ==========================================

def extract_video_id(url):
    """Mengambil ID Video dari URL YouTube"""
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

def fetch_video_data(video_id):
    """Request ke RapidAPI"""
    try:
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
        
        headers = {
            'x-rapidapi-key': RAPIDAPI_KEY,
            'x-rapidapi-host': RAPIDAPI_HOST
        }
        
        # Endpoint persis seperti di PHP
        query = f"/v2/video/details?videoId={video_id}"
        
        conn.request("GET", query, headers=headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()
        
        if res.status != 200:
            return {"error": f"API Error: {res.status}"}
            
        return json.loads(data.decode("utf-8"))
        
    except Exception as e:
        return {"error": str(e)}

# ==========================================
# UI (TAMPILAN)
# ==========================================

st.title("📺 Python YouTube Downloader")
st.caption("Versi bersih: Mengambil data JSON dan menampilkan Link Download langsung.")

# Input URL
url_input = st.text_input("Paste Link YouTube:", placeholder="https://www.youtube.com/watch?v=...")
btn_search = st.button("🔍 CARI VIDEO", type="primary")

if btn_search and url_input:
    # 1. Ekstrak ID
    video_id = extract_video_id(url_input)
    
    if not video_id:
        st.error("❌ Link YouTube tidak valid!")
    else:
        with st.spinner("⏳ Sedang mengambil data dari API..."):
            # 2. Ambil Data API
            data = fetch_video_data(video_id)
            
            # Debugging (Opsional: Matikan jika sudah live)
            with st.expander("🛠 Lihat Data Mentah JSON (Debug)"):
                st.json(data)

            # 3. Parsing Data
            if "error" in data:
                st.error(data['error'])
            
            elif data.get('errorId') == 'Success':
                # --- TAMPILKAN JUDUL & THUMBNAIL ---
                st.divider()
                
                # Ambil thumbnail resolusi tertinggi
                thumb_url = data['thumbnails'][-1]['url'] if data.get('thumbnails') else None
                
                col_img, col_info = st.columns([1, 2])
                with col_img:
                    if thumb_url:
                        st.image(thumb_url, use_container_width=True)
                with col_info:
                    st.subheader(data.get('title', 'No Title'))
                    st.text(f"Duration: {data.get('lengthSeconds', 0)} detik")
                    st.text(f"Views: {data.get('viewCount', 0)}")

                st.info("👇 Silakan pilih format di bawah ini:")

                # --- LOOPING VIDEOS ---
                # Menggunakan logika ['videos']['items'] sesuai temuan di PHP
                st.markdown("### 🎬 Video")
                
                videos = data.get('videos', {}).get('items', [])
                
                if videos:
                    for vid in videos:
                        if vid.get('url'):
                            quality = vid.get('quality', 'Unknown')
                            ext = vid.get('extension', 'mp4')
                            size = vid.get('sizeText', '-')
                            has_audio = "🔊 Ada Suara" if vid.get('hasAudio') else "🔇 Tanpa Suara"
                            link = vid.get('url')

                            # Tampilan Card
                            st.markdown(f"""
                            <div class="download-card">
                                <b>{quality}</b> ({ext}) - {size}<br>
                                <small>{has_audio}</small>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Tombol Link (Streamlit Link Button)
                            st.link_button(f"⬇️ Download {quality}", link)
                else:
                    st.warning("Tidak ada data video ditemukan.")

                # --- LOOPING AUDIOS ---
                st.markdown("### 🎵 Audio Only")
                audios = data.get('audios', {}).get('items', [])
                
                if audios:
                    for aud in audios:
                        if aud.get('url'):
                            ext = aud.get('extension', 'mp3')
                            size = aud.get('sizeText', '-')
                            link = aud.get('url')
                            
                            st.markdown(f"""
                            <div class="download-card">
                                <b>Audio</b> ({ext}) - {size}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            st.link_button(f"⬇️ Download Audio ({ext})", link)
                else:
                    st.write("Tidak ada data audio.")
                
                st.success("✅ Selesai! Jika tombol tidak otomatis download, Klik Kanan tombol -> 'Save Link As'.")

            else:
                st.error("API Gagal mengambil data (Video mungkin diproteksi/panjang).")
