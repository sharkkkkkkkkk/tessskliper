import streamlit as st
import os
import numpy as np

# Import dengan error handling untuk debugging
try:
    import whisper
except ImportError as e:
    st.error(f"Whisper import error: {e}")
    st.stop()

try:
    import torch
except ImportError as e:
    st.error(f"Torch import error: {e}")
    st.stop()

try:
    from pytubefix import YouTube
except ImportError as e:
    st.error(f"Pytubefix import error: {e}")
    st.stop()

try:
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
except ImportError as e:
    st.error(f"""
    MoviePy import error: {e}
    
    Pastikan file berikut ada di repository:
    - requirements.txt
    - packages.txt (dengan ffmpeg, imagemagick)
    """)
    st.stop()

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    st.error(f"Pillow import error: {e}")
    st.stop()

# ==========================================
# KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="Auto Shorts (Pytubefix)", page_icon="🔧", layout="wide")

TEMP_DIR = "temp"
OUT_DIR = "output"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# ==========================================
# FUNGSI TEXT ENGINE (PILLOW)
# ==========================================
def create_text_image(text, video_width, video_height, font_size=80, color='yellow', stroke_width=4):
    img = Image.new('RGBA', (video_width, video_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    font = None
    try: font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except: 
        try: font = ImageFont.load_default()
        except: return None

    try:
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        text_w = bbox[2] - bbox[0]
    except AttributeError:
        text_w = draw.textlength(text, font=font)
    
    x_pos = (video_width - text_w) // 2
    y_pos = int(video_height * 0.70)

    draw.text((x_pos, y_pos), text, font=font, fill=color, 
              stroke_width=stroke_width, stroke_fill='black')
    
    return np.array(img)

# ==========================================
# FUNGSI HELPER UNTUK POTOKEN
# ==========================================
def get_manual_potoken():
    """
    Meminta user memasukkan PoToken manual jika diperlukan
    """
    st.warning("⚠️ **Bot Detection!** Diperlukan PoToken untuk akses.")
    
    with st.expander("📘 Cara Mendapatkan PoToken (5 menit)", expanded=True):
        st.markdown("""
        **Langkah-langkah:**
        1. Buka browser (Chrome/Firefox) dalam **mode Incognito/Private**
        2. Kunjungi: `https://www.youtube.com/embed/jNQXAC9IVRw`
        3. Tekan **F12** untuk buka Developer Tools
        4. Pilih tab **Network**, lalu filter dengan: `player`
        5. **Klik tombol Play** pada video
        6. Klik request `player` yang muncul, lalu pilih tab **Payload**
        7. **Copy nilai** dari:
           - `visitorData` (contoh: CgtqUXZhN...)
           - `poToken` (string panjang, contoh: MmVST...)
        8. Paste ke form di bawah
        
        **Catatan:** PoToken akan expired dalam 4-6 jam. Cache di Streamlit bertahan selama session.
        """)
    
    col1, col2 = st.columns(2)
    with col1:
        visitor_data = st.text_input("🔑 Visitor Data:", key="vdata", 
                                     placeholder="CgtqUXZhN...")
    with col2:
        po_token = st.text_input("🔐 PoToken:", key="potoken", 
                                 placeholder="MmVST...", type="password")
    
    if visitor_data and po_token:
        return (visitor_data.strip(), po_token.strip())
    return None

# ==========================================
# FUNGSI DOWNLOADER UNTUK STREAMLIT CLOUD
# ==========================================
def download_via_pytubefix(url, use_manual_token=False, manual_tokens=None):
    """
    Download video dengan support untuk Streamlit Cloud
    
    Strategi:
    1. Coba ANDROID client (paling stabil)
    2. Jika gagal dengan bot detection, gunakan PoToken manual
    """
    output_path = f"{TEMP_DIR}/source.mp4"
    if os.path.exists(output_path): 
        os.remove(output_path)
    
    try:
        # METODE 1: Client ANDROID (Default, tanpa PoToken)
        if not use_manual_token:
            st.write("🔄 Mencoba download dengan Client ANDROID...")
            
            try:
                yt = YouTube(url, client='ANDROID')
                st.info(f"📹 **{yt.title}**")
                st.info(f"⏱️ Durasi: {yt.length // 60}:{yt.length % 60:02d}")
                
                # Prioritas: Progressive stream (video+audio sudah gabung)
                stream = yt.streams.filter(
                    progressive=True, 
                    file_extension='mp4'
                ).order_by('resolution').desc().first()
                
                if not stream:
                    st.warning("Progressive tidak ada, coba alternatif...")
                    stream = yt.streams.get_highest_resolution()
                
                if not stream:
                    raise Exception("Tidak ada stream yang tersedia")
                
                st.write(f"⬇️ Resolusi: **{stream.resolution}** ({stream.filesize_mb:.1f} MB)")
                
                with st.spinner("Mendownload..."):
                    stream.download(output_path=TEMP_DIR, filename="source.mp4")
                
                st.success("✅ Download berhasil!")
                return True
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Deteksi Bot Error
                if 'bot' in error_str or '403' in error_str:
                    st.error("🤖 Terdeteksi sebagai bot oleh YouTube")
                    return False
                else:
                    raise e
        
        # METODE 2: Gunakan PoToken Manual
        else:
            if not manual_tokens:
                st.error("❌ PoToken tidak valid")
                return False
            
            visitor_data, po_token = manual_tokens
            st.write("🔄 Download dengan PoToken manual...")
            
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
            
            stream = yt.streams.filter(
                progressive=True,
                file_extension='mp4'
            ).order_by('resolution').desc().first()
            
            if not stream:
                stream = yt.streams.get_highest_resolution()
            
            if not stream:
                raise Exception("Tidak ada stream yang tersedia")
            
            st.write(f"⬇️ Resolusi: **{stream.resolution}** ({stream.filesize_mb:.1f} MB)")
            
            with st.spinner("Mendownload..."):
                stream.download(output_path=TEMP_DIR, filename="source.mp4")
            
            st.success("✅ Download dengan PoToken berhasil!")
            return True

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        return False

# ==========================================
# FUNGSI PROCESSSING
# ==========================================

@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base", device="cpu")

def generate_intervals(duration, num_clips, clip_len):
    intervals = []
    start_safe = duration * 0.05
    end_safe = duration * 0.95
    playable = end_safe - start_safe
    
    if playable < clip_len:
        return [{"start": start_safe, "end": start_safe + clip_len, "title": "Full_Clip"}]

    step = playable / (num_clips + 1)
    for i in range(1, num_clips + 1):
        mid = start_safe + (step * i)
        intervals.append({
            "start": mid - (clip_len / 2),
            "end": mid + (clip_len / 2),
            "title": f"Part_{i}"
        })
    return intervals

def process_video_clip(source, start, end, name, all_words, enable_subs):
    full_clip = VideoFileClip(source)
    if end > full_clip.duration: end = full_clip.duration
    clip = full_clip.subclip(start, end)
    
    # Center Crop Logic
    w, h = clip.size
    target_ratio = 9/16
    
    if w / h > target_ratio:
        new_w = h * target_ratio
        x1 = (w - new_w) // 2
        crop_clip = clip.crop(x1=x1, y1=0, width=new_w, height=h)
    else:
        crop_clip = clip

    final_clip = crop_clip.resize(height=1280) 
    
    subs = []
    if enable_subs:
        valid_words = [w for w in all_words if w['start'] >= start and w['end'] <= end]
        for w in valid_words:
            text = w.get('word', w.get('text', '')).strip().upper()
            if not text: continue
            color = 'white' if len(text) <= 3 else '#FFD700'
            
            img_array = create_text_image(text, final_clip.w, final_clip.h, font_size=70, color=color, stroke_width=4)
            if img_array is not None:
                txt_clip = (ImageClip(img_array)
                            .set_start(w['start'] - start)
                            .set_end(w['end'] - start)
                            .set_duration(w['end'] - w['start'])
                            .set_position('center'))
                subs.append(txt_clip)
            
    final = CompositeVideoClip([final_clip] + subs)
    out_path = f"{OUT_DIR}/{name}.mp4"
    final.write_videofile(out_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', logger=None)
    full_clip.close()
    final.close()
    return out_path

# ==========================================
# UI FRONTEND
# ==========================================

st.title("🎬 Auto Shorts - Streamlit Cloud Ready")
st.caption("✨ Optimized untuk Streamlit Cloud dengan PoToken Support")

# Alert untuk Streamlit Cloud Users
st.info("""
💡 **Untuk Streamlit Cloud:** Jika download gagal (bot detection), gunakan **PoToken Manual** di sidebar.
PoToken valid 4-6 jam dan akan di-cache selama session aktif.
""")

with st.sidebar:
    st.header("⚙️ Sumber Video")
    
    # Pilihan Input: Link atau Upload
    input_type = st.radio("Metode Input:", ["Link YouTube", "Upload Video Manual"])
    
    url = None
    uploaded_file = None
    use_potoken = False
    potoken_data = None
    
    if input_type == "Link YouTube":
        url = st.text_input("🔗 URL YouTube")
        
        st.divider()
        st.subheader("🔐 Opsi PoToken")
        use_potoken = st.checkbox(
            "Gunakan PoToken Manual",
            help="Aktifkan jika download gagal dengan error 'bot detection'"
        )
        
        if use_potoken:
            potoken_data = get_manual_potoken()
            if potoken_data:
                st.success("✅ PoToken siap digunakan")
        else:
            st.info("Client ANDROID akan digunakan (tanpa PoToken)")
    else:
        uploaded_file = st.file_uploader("📤 Upload file MP4", type=["mp4"])
        
    st.divider()
    st.subheader("⚙️ Pengaturan Klip")
    num_clips = st.slider("Jumlah Klip", 1, 3, 1)
    duration = st.slider("Durasi (detik)", 15, 60, 30)
    use_subtitle = st.checkbox("Subtitle Otomatis", value=True)
    
    btn_process = st.button("🚀 Mulai Proses", type="primary", use_container_width=True)

# Expander untuk troubleshooting
with st.expander("🆘 Troubleshooting"):
    st.markdown("""
    **Problem: Error 403 / Bot Detection**
    - ✅ Aktifkan "Gunakan PoToken Manual" di sidebar
    - ✅ Ikuti panduan untuk get PoToken dari browser
    - ✅ Atau gunakan "Upload Video Manual"
    
    **Problem: Download lambat**
    - Streamlit Cloud memiliki bandwidth terbatas
    - Video >100MB bisa timeout
    - Gunakan video pendek atau upload manual
    
    **Problem: PoToken Expired**
    - PoToken valid 4-6 jam
    - Generate ulang jika sudah expired
    - Cache akan di-reset saat restart app
    
    **Alternatif:**
    - Download video di lokal
    - Upload ke app menggunakan "Upload Video Manual"
    """)

if btn_process:
    processing_ok = False
    source_file = f"{TEMP_DIR}/source.mp4"
    
    # 1. TAHAP INPUT (DOWNLOAD / UPLOAD)
    if input_type == "Link YouTube":
        if url:
            # Validasi PoToken jika diaktifkan
            if use_potoken and not potoken_data:
                st.error("⚠️ Silakan masukkan Visitor Data dan PoToken terlebih dahulu")
            else:
                if download_via_pytubefix(url, use_potoken, potoken_data):
                    processing_ok = True
                else:
                    if not use_potoken:
                        st.warning("💡 **Tip:** Coba aktifkan 'Gunakan PoToken Manual' di sidebar")
        else:
            st.error("⚠️ Masukkan URL YouTube!")
            
    else: # Upload Manual
        if uploaded_file:
            with st.spinner("📤 Mengupload file..."):
                with open(source_file, "wb") as f:
                    f.write(uploaded_file.getbuffer())
            st.success("✅ File berhasil diupload!")
            processing_ok = True
        else:
            st.error("⚠️ Silakan upload file video terlebih dahulu.")

    # 2. TAHAP PROSES
    if processing_ok:
        ph = st.empty()
        bar = st.progress(0)
        
        all_words = []
        if use_subtitle:
            ph.info("🎤 Transkripsi Audio dengan Whisper...")
            try:
                model = load_whisper_model()
                temp_audio = f"{TEMP_DIR}/audio.wav"
                vc = VideoFileClip(source_file)
                vc.audio.write_audiofile(temp_audio, logger=None)
                vc.close()
                
                result = model.transcribe(temp_audio, word_timestamps=True, fp16=False)
                all_words = [w for s in result['segments'] for w in s['words']]
                st.success(f"✅ Transkripsi selesai ({len(all_words)} kata)")
            except Exception as e:
                st.warning(f"⚠️ Gagal Transkripsi: {e}")
                use_subtitle = False
        
        bar.progress(50)
        
        clip_temp = VideoFileClip(source_file)
        intervals = generate_intervals(clip_temp.duration, num_clips, duration)
        clip_temp.close()
        
        st.divider()
        st.subheader("🎬 Hasil Klip Video")
        cols = st.columns(len(intervals))
        
        for i, data in enumerate(intervals):
            ph.info(f"🎬 Rendering Klip {i+1}/{len(intervals)}...")
            try:
                out_file = process_video_clip(
                    source_file, 
                    data['start'], 
                    data['end'], 
                    f"Short_{i+1}", 
                    all_words, 
                    use_subtitle
                )
                with cols[i]:
                    st.success(f"✅ Klip {i+1}")
                    st.video(out_file)
                    with open(out_file, "rb") as f:
                        st.download_button(
                            f"⬇️ Download Klip {i+1}", 
                            f, 
                            file_name=f"Short_{i+1}.mp4",
                            mime="video/mp4",
                            use_container_width=True
                        )
            except Exception as e:
                with cols[i]:
                    st.error(f"❌ Error klip {i+1}: {e}")
        
        bar.progress(100)
        ph.success("🎉 Semua Klip Selesai Diproses!")
        st.balloons()
