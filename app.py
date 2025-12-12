import streamlit as st
import os
import numpy as np
import whisper
import yt_dlp
import torch
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# KONFIGURASI
# ==========================================
st.set_page_config(page_title="Auto Shorts Cloud", page_icon="⚡", layout="wide")

TEMP_DIR = "temp"
OUT_DIR = "output"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# ==========================================
# FUNGSI TEXT ENGINE (PILLOW - CLOUD SAFE)
# ==========================================
def create_text_image(text, video_width, video_height, font_size=80, color='yellow', stroke_width=4):
    # Buat kanvas transparan
    img = Image.new('RGBA', (video_width, video_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Load Font Default (Aman untuk Server Linux/Cloud)
    try:
        # Coba font default sistem linux
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except:
        # Fallback ke default PIL jika font tidak ketemu
        try:
             font = ImageFont.load_default()
        except:
             # Fallback terakhir
             return None

    # Hitung posisi tengah
    try:
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        text_w = bbox[2] - bbox[0]
    exceptAttributeError:
        # Fallback untuk versi Pillow lama
        text_w = draw.textlength(text, font=font)
    
    x_pos = (video_width - text_w) // 2
    y_pos = int(video_height * 0.70) # Posisi subtitle agak bawah

    # Gambar teks dengan outline
    draw.text((x_pos, y_pos), text, font=font, fill=color, 
              stroke_width=stroke_width, stroke_fill='black')
    
    return np.array(img)

# ==========================================
# FUNGSI BACKEND
# ==========================================

@st.cache_resource
def load_whisper_model():
    # Gunakan CPU di Streamlit Cloud (Kecuali jika Anda punya GPU instance)
    device = "cpu"
    return whisper.load_model("base", device=device)

def download_video(url):
    output_path = f"{TEMP_DIR}/source.mp4"
    if os.path.exists(output_path): os.remove(output_path)
    
    ydl_opts = {
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
        'outtmpl': f"{TEMP_DIR}/raw_video",
        'merge_output_format': 'mp4',
        'quiet': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            temp_file = ydl.prepare_filename(info)
            if os.path.exists(f"{TEMP_DIR}/raw_video.mp4"):
                os.replace(f"{TEMP_DIR}/raw_video.mp4", output_path)
            elif os.path.exists(temp_file):
                os.replace(temp_file, output_path)
            else:
                import glob
                files = glob.glob(f"{TEMP_DIR}/*.mp4")
                if files: os.replace(files[0], output_path)
        return True
    except Exception as e:
        st.error(f"Error Download: {e}")
        return False

def generate_intervals(duration, num_clips, clip_len):
    intervals = []
    start_safe = duration * 0.10
    end_safe = duration * 0.90
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
    
    # --- CENTER CROP LOGIC (PENGGANTI FACE TRACKING) ---
    # Kita potong tengah frame menjadi rasio 9:16
    w, h = clip.size
    target_ratio = 9/16
    
    # Jika video landscape (w > h)
    if w / h > target_ratio:
        new_w = h * target_ratio
        x1 = (w - new_w) // 2
        crop_clip = clip.crop(x1=x1, y1=0, width=new_w, height=h)
    else:
        crop_clip = clip

    # Resize ke HD Vertikal
    final_clip = crop_clip.resize(height=1280) 
    
    # --- SUBTITLES ---
    subs = []
    if enable_subs:
        valid_words = [w for w in all_words if w['start'] >= start and w['end'] <= end]
        
        for w in valid_words:
            text = w.get('word', w.get('text', '')).strip().upper()
            if not text: continue

            color = 'white' if len(text) <= 3 else '#FFD700'
            
            img_array = create_text_image(
                text, 
                final_clip.w, 
                final_clip.h, 
                font_size=70, 
                color=color, 
                stroke_width=4
            )
            
            if img_array is not None:
                txt_clip = (ImageClip(img_array)
                            .set_start(w['start'] - start)
                            .set_end(w['end'] - start)
                            .set_duration(w['end'] - w['start'])
                            .set_position('center'))
                
                subs.append(txt_clip)
            
    # Render
    final = CompositeVideoClip([final_clip] + subs)
    out_path = f"{OUT_DIR}/{name}.mp4"
    
    # Gunakan preset ultrafast agar tidak timeout di Streamlit Cloud
    final.write_videofile(out_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', logger=None)
    
    full_clip.close()
    final.close()
    return out_path

# ==========================================
# UI FRONTEND
# ==========================================

st.title("⚡ Auto Shorts (Cloud Edition)")
st.caption("Versi Ringan: Tanpa MediaPipe, Tanpa ImageMagick, Support Python 3.13.")

with st.sidebar:
    st.header("⚙️ Konfigurasi")
    url = st.text_input("URL YouTube")
    num_clips = st.slider("Jumlah Klip", 1, 3, 1) # Limit 3 agar tidak overload memory
    duration = st.slider("Durasi (detik)", 15, 60, 30)
    use_subtitle = st.checkbox("Subtitle", value=True)
    
    if st.button("🚀 Proses"):
        if url:
            st.session_state['processing'] = True
        else:
            st.error("Masukkan URL!")

if st.session_state.get('processing'):
    ph = st.empty()
    bar = st.progress(0)
    
    ph.info("📥 Mendownload video...")
    if download_video(url):
        bar.progress(20)
        source_file = f"{TEMP_DIR}/source.mp4"
        
        all_words = []
        if use_subtitle:
            ph.info("🎤 Transkripsi Audio (Whisper CPU)... ini mungkin agak lama.")
            try:
                model = load_whisper_model()
                # Ekstrak audio
                temp_audio = f"{TEMP_DIR}/audio.wav"
                vc = VideoFileClip(source_file)
                vc.audio.write_audiofile(temp_audio, logger=None)
                vc.close()
                
                result = model.transcribe(temp_audio, word_timestamps=True, fp16=False)
                all_words = [w for s in result['segments'] for w in s['words']]
            except Exception as e:
                st.warning(f"Gagal Transkripsi (Skip Subtitle): {e}")
                use_subtitle = False
        
        bar.progress(50)
        
        # Proses Klip
        source_clip = VideoFileClip(source_file)
        intervals = generate_intervals(source_clip.duration, num_clips, duration)
        source_clip.close()
        
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
                st.error(f"Gagal Klip {i+1}: {e}")
        
        bar.progress(100)
        ph.success("✅ Selesai!")
        st.session_state['processing'] = False
