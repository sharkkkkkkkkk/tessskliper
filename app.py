import streamlit as st
import os
import requests
import numpy as np
import whisper
import torch
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="Auto Shorts (Cobalt Fixed)", page_icon="🚀", layout="wide")

TEMP_DIR = "temp"
OUT_DIR = "output"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# ==========================================
# FUNGSI TEXT ENGINE (PILLOW)
# ==========================================
def create_text_image(text, video_width, video_height, font_size=80, color='yellow', stroke_width=4):
    """Membuat gambar teks transparan dengan Pillow"""
    img = Image.new('RGBA', (video_width, video_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Load Font (Fallback aman untuk Cloud)
    font = None
    try: font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except: 
        try: font = ImageFont.load_default()
        except: return None

    # Hitung posisi tengah text
    try:
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        text_w = bbox[2] - bbox[0]
    except AttributeError:
        text_w = draw.textlength(text, font=font)
    
    x_pos = (video_width - text_w) // 2
    y_pos = int(video_height * 0.70) # Posisi subtitle di 70% tinggi video

    # Gambar teks dengan outline
    draw.text((x_pos, y_pos), text, font=font, fill=color, 
              stroke_width=stroke_width, stroke_fill='black')
    
    return np.array(img)

# ==========================================
# FUNGSI DOWNLOADER (COBALT V10 API)
# ==========================================
def download_via_cobalt(url):
    """
    Download video via Cobalt API v10 dengan Multiple Instances
    """
    output_path = f"{TEMP_DIR}/source.mp4"
    if os.path.exists(output_path): os.remove(output_path)
    
    # Daftar Server Cobalt (Utama & Cadangan)
    instances = [
        "https://api.cobalt.tools",       # Official
        "https://cobalt.api.wuk.sh",      # Reliable Backup
        "https://api.server.cobalt.tools" # Backup 2
    ]
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Payload v10
    payload = {
        "url": url,
        "videoQuality": "720",
        "filenamePattern": "basic",
        "disableMetadata": True
    }

    success = False
    
    for base_url in instances:
        try:
            st.toast(f"Menghubungi server: {base_url}...")
            
            # Request POST ke API
            response = requests.post(
                f"{base_url.rstrip('/')}", 
                json=payload, 
                headers=headers,
                timeout=20
            )
            
            if response.status_code != 200:
                continue # Pindah ke server berikutnya jika error
                
            data = response.json()
            download_link = None
            
            # Cek respon v10 (bisa 'url' langsung atau 'picker')
            if 'url' in data:
                download_link = data['url']
            elif 'picker' in data and len(data['picker']) > 0:
                download_link = data['picker'][0]['url']
            
            if not download_link:
                continue

            # Download File Video
            st.info(f"⬇️ Mendownload dari {base_url}...")
            with requests.get(download_link, stream=True) as r:
                r.raise_for_status()
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            success = True
            break # Stop loop jika berhasil

        except Exception as e:
            print(f"Gagal di {base_url}: {e}")
            continue

    return success

# ==========================================
# FUNGSI PROCESSING
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
    
    # --- CENTER CROP (NO MEDIAPIPE) ---
    w, h = clip.size
    target_ratio = 9/16
    
    if w / h > target_ratio: # Landscape to Portrait
        new_w = h * target_ratio
        x1 = (w - new_w) // 2
        crop_clip = clip.crop(x1=x1, y1=0, width=new_w, height=h)
    else:
        crop_clip = clip

    # Resize ke 720x1280
    final_clip = crop_clip.resize(height=1280) 
    
    # --- SUBTITLES ---
    subs = []
    if enable_subs:
        # Filter kata di range waktu ini
        valid_words = [w for w in all_words if w['start'] >= start and w['end'] <= end]
        
        for w in valid_words:
            # Ambil teks (fallback key 'text' atau 'word')
            text = w.get('word', w.get('text', '')).strip().upper()
            if not text: continue
            
            # Logika Warna
            color = 'white' if len(text) <= 3 else '#FFD700'
            
            # Buat Gambar Teks
            img_array = create_text_image(
                text, final_clip.w, final_clip.h, 
                font_size=70, color=color, stroke_width=4
            )
            
            if img_array is not None:
                txt_clip = (ImageClip(img_array)
                            .set_start(w['start'] - start)
                            .set_end(w['end'] - start)
                            .set_duration(w['end'] - w['start'])
                            .set_position('center'))
                subs.append(txt_clip)
            
    # Render Akhir
    final = CompositeVideoClip([final_clip] + subs)
    out_path = f"{OUT_DIR}/{name}.mp4"
    
    # Preset ultrafast penting untuk Cloud gratisan
    final.write_videofile(out_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', logger=None)
    
    full_clip.close()
    final.close()
    return out_path

# ==========================================
# INTERFACE
# ==========================================

st.title("🚀 Auto Shorts (Cobalt Fixed)")
st.caption("Download YouTube tanpa Error 403 menggunakan Cobalt API v10.")

with st.sidebar:
    st.header("⚙️ Konfigurasi")
    url = st.text_input("URL YouTube")
    num_clips = st.slider("Jumlah Klip", 1, 3, 1)
    duration = st.slider("Durasi (detik)", 15, 60, 30)
    use_subtitle = st.checkbox("Subtitle", value=True)
    
    btn_process = st.button("🚀 Mulai Proses", type="primary")

if btn_process:
    if not url:
        st.error("Masukkan URL!")
    else:
        ph = st.empty()
        bar = st.progress(0)
        
        # 1. DOWNLOAD VIA COBALT
        ph.info("🔄 Menghubungi Server Cobalt...")
        
        if download_via_cobalt(url):
            bar.progress(20)
            source_file = f"{TEMP_DIR}/source.mp4"
            
            all_words = []
            if use_subtitle:
                ph.info("🎤 Transkripsi Audio (Whisper)...")
                try:
                    model = load_whisper_model()
                    temp_audio = f"{TEMP_DIR}/audio.wav"
                    vc = VideoFileClip(source_file)
                    vc.audio.write_audiofile(temp_audio, logger=None)
                    vc.close()
                    
                    # Transkripsi
                    result = model.transcribe(temp_audio, word_timestamps=True, fp16=False)
                    all_words = [w for s in result['segments'] for w in s['words']]
                except Exception as e:
                    st.warning(f"Gagal Transkripsi: {e}")
                    use_subtitle = False
            
            bar.progress(50)
            
            # 2. GENERATE & PROCESS
            clip_temp = VideoFileClip(source_file)
            intervals = generate_intervals(clip_temp.duration, num_clips, duration)
            clip_temp.close()
            
            cols = st.columns(len(intervals))
            for i, data in enumerate(intervals):
                ph.info(f"🎬 Rendering Klip {i+1}...")
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
                        st.video(out_file)
                        with open(out_file, "rb") as f:
                            st.download_button(f"⬇️ Download {i+1}", f, file_name=f"Short_{i+1}.mp4")
                except Exception as e:
                    st.error(f"Error render: {e}")
            
            bar.progress(100)
            ph.success("✅ Selesai!")
        else:
            st.error("❌ Gagal Download via Cobalt. Semua server sibuk atau link tidak valid.")
            st.info("Tips: Coba refresh halaman atau gunakan video YouTube lain.")
