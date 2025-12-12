import streamlit as st
import os
import numpy as np
import whisper
import torch
from pytubefix import YouTube
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont

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
# FUNGSI DOWNLOADER (PYTUBEFIX)
# ==========================================
def download_via_pytubefix(url):
    """
    Download video menggunakan Pytubefix dengan Client Android
    """
    output_path = f"{TEMP_DIR}/source.mp4"
    if os.path.exists(output_path): os.remove(output_path)
    
    try:
        st.write("🔄 Menghubungi YouTube (Client Android)...")
        
        # PENTING: client='ANDROID' adalah kunci anti-403 saat ini
        yt = YouTube(url, client='ANDROID')
        
        st.info(f"Judul: **{yt.title}**")
        
        # Cari stream MP4 Progressive (Video+Audio gabung) resolusi tertinggi (Max 720p)
        # Kita pakai get_highest_resolution() yang biasanya aman
        stream = yt.streams.get_highest_resolution()
        
        if not stream:
            st.error("Tidak ditemukan stream yang cocok.")
            return False
            
        st.write(f"⬇️ Mendownload resolusi: {stream.resolution}...")
        
        # Download ke folder temp dengan nama 'source.mp4'
        stream.download(output_path=TEMP_DIR, filename="source.mp4")
        
        return True

    except Exception as e:
        # Menangkap error spesifik pytubefix
        st.error(f"Pytubefix Gagal: {e}")
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

st.title("🔧 Auto Shorts (Pytubefix)")
st.caption("Solusi Download YouTube menggunakan Pytubefix (Client Android).")

with st.sidebar:
    st.header("⚙️ Sumber Video")
    
    # Pilihan Input: Link atau Upload
    input_type = st.radio("Metode Input:", ["Link YouTube", "Upload Video Manual"])
    
    url = None
    uploaded_file = None
    
    if input_type == "Link YouTube":
        url = st.text_input("Masukkan URL")
    else:
        uploaded_file = st.file_uploader("Upload file MP4", type=["mp4"])
        
    st.divider()
    num_clips = st.slider("Jumlah Klip", 1, 3, 1)
    duration = st.slider("Durasi (detik)", 15, 60, 30)
    use_subtitle = st.checkbox("Subtitle", value=True)
    
    btn_process = st.button("🚀 Mulai Proses", type="primary")

if btn_process:
    processing_ok = False
    source_file = f"{TEMP_DIR}/source.mp4"
    
    # 1. TAHAP INPUT (DOWNLOAD / UPLOAD)
    if input_type == "Link YouTube":
        if url:
            if download_via_pytubefix(url):
                processing_ok = True
            else:
                st.error("Gagal mendownload. Cobalah opsi 'Upload Video Manual'.")
        else:
            st.error("Masukkan URL!")
            
    else: # Upload Manual
        if uploaded_file:
            with open(source_file, "wb") as f:
                f.write(uploaded_file.getbuffer())
            processing_ok = True
        else:
            st.error("Silakan upload file video terlebih dahulu.")

    # 2. TAHAP PROSES
    if processing_ok:
        ph = st.empty()
        bar = st.progress(0)
        
        all_words = []
        if use_subtitle:
            ph.info("🎤 Transkripsi Audio (Whisper)...")
            try:
                model = load_whisper_model()
                temp_audio = f"{TEMP_DIR}/audio.wav"
                vc = VideoFileClip(source_file)
                vc.audio.write_audiofile(temp_audio, logger=None)
                vc.close()
                
                result = model.transcribe(temp_audio, word_timestamps=True, fp16=False)
                all_words = [w for s in result['segments'] for w in s['words']]
            except Exception as e:
                st.warning(f"Gagal Transkripsi: {e}")
                use_subtitle = False
        
        bar.progress(50)
        
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
