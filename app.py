import streamlit as st
import os
import cv2
import numpy as np
import mediapipe as mp
import whisper
import yt_dlp
import torch
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont

# ==========================================
# KONFIGURASI SISTEM
# ==========================================
st.set_page_config(page_title="Auto Shorts Clippers", page_icon="⚡", layout="wide")

# Folder Sementara
TEMP_DIR = "temp"
OUT_DIR = "output"
if not os.path.exists(TEMP_DIR): os.makedirs(TEMP_DIR)
if not os.path.exists(OUT_DIR): os.makedirs(OUT_DIR)

# ==========================================
# FUNGSI TEXT ENGINE (PENGGANTI IMAGEMAGICK)
# ==========================================

def create_text_image(text, video_width, video_height, font_size=80, color='yellow', stroke_width=4):
    """
    Membuat gambar teks transparan menggunakan Pillow (Tanpa ImageMagick)
    """
    # 1. Buat Canvas Transparan
    img = Image.new('RGBA', (video_width, video_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 2. Load Font (Coba load Arial, fallback ke default jika gagal)
    try:
        # Untuk Windows: arialbd.ttf (Arial Bold)
        # Untuk Linux/Colab: DejaVuSans-Bold.ttf
        font_name = "dejavu-sans.bold-oblique.ttf" if os.name == 'nt' else "dejavu-sans.bold-oblique.ttf"
        font = ImageFont.truetype(font_name, font_size)
    except:
        font = ImageFont.load_default()

    # 3. Hitung Posisi Tengah
    # bbox = (left, top, right, bottom)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    x_pos = (video_width - text_w) // 2
    y_pos = int(video_height * 0.75) # Posisi 75% ke bawah (Area aman TikTok)

    # 4. Gambar Teks dengan Outline (Stroke)
    draw.text((x_pos, y_pos), text, font=font, fill=color, 
              stroke_width=stroke_width, stroke_fill='black')
    
    # 5. Konversi ke Numpy Array untuk MoviePy
    return np.array(img)

# ==========================================
# FUNGSI BACKEND
# ==========================================

@st.cache_resource
def load_whisper_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
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
    
    temp_sub = f"{TEMP_DIR}/sub_{name}.mp4"
    clip.write_videofile(temp_sub, codec='libx264', audio_codec='aac', logger=None)
    
    # --- FACE TRACKING ---
    mp_face = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.6)
    cap = cv2.VideoCapture(temp_sub)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    centers = []
    
    while True:
        ret, frame = cap.read()
        if not ret: break
        results = mp_face.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        x_c = width // 2
        if results.detections:
            for det in results.detections:
                bbox = det.location_data.relative_bounding_box
                x_c = int((bbox.xmin + bbox.width/2) * width)
                break
        centers.append(x_c)
    cap.release()
    
    if not centers: centers = [width//2]
    window = 15
    if len(centers) > window:
        centers = np.convolve(centers, np.ones(window)/window, mode='same')
        
    def crop_fn(get_frame, t):
        idx = int(t * fps)
        safe_idx = min(idx, len(centers)-1)
        cx = centers[safe_idx]
        img = get_frame(t)
        h, w = img.shape[:2]
        tw = int(h * 9/16)
        x1 = max(0, min(w-tw, int(cx - tw/2)))
        return img[:, x1:x1+tw]
        
    final_clip = clip.fl(crop_fn, apply_to=['mask']).resize(height=1920)
    
    # --- SUBTITLES DENGAN PILLOW (Tanpa ImageMagick) ---
    subs = []
    if enable_subs:
        valid_words = [w for w in all_words if w['start'] >= start and w['end'] <= end]
        
        for w in valid_words:
            text = w.get('word', w.get('text', '')).strip().upper()
            if not text: continue

            # Logika Warna
            color = 'white' if len(text) <= 3 else '#FFD700' # Hex Kuning Emas
            
            # Buat Gambar Teks pakai Pillow
            img_array = create_text_image(
                text, 
                final_clip.w, 
                final_clip.h, 
                font_size=85, 
                color=color, 
                stroke_width=5
            )
            
            # Masukkan ke MoviePy ImageClip
            txt_clip = (ImageClip(img_array)
                        .set_start(w['start'] - start)
                        .set_end(w['end'] - start)
                        .set_duration(w['end'] - w['start'])
                        .set_position('center')) # Posisi sudah diatur di create_text_image
            
            subs.append(txt_clip)
            
    # Render Akhir
    final = CompositeVideoClip([final_clip] + subs)
    out_path = f"{OUT_DIR}/{name}.mp4"
    final.write_videofile(out_path, codec='libx264', audio_codec='aac', fps=24, preset='ultrafast', logger=None)
    
    full_clip.close()
    final.close()
    if os.path.exists(temp_sub): os.remove(temp_sub)
    return out_path

# ==========================================
# INTERFACE
# ==========================================

st.title("⚡ Auto Shorts (No ImageMagick)")
st.caption("Solusi: Mudah dan Cepat")

with st.sidebar:
    st.header("⚙️ Settings")
    url = st.text_input("YouTube URL")
    num_clips = st.slider("Jumlah Klip", 1, 5, 3)
    duration = st.slider("Durasi (detik)", 15, 60, 60)
    use_subtitle = st.checkbox("Subtitle Hormozi Style", value=True)
    btn_start = st.button("🚀 Proses Video", type="primary")

if btn_start and url:
    ph = st.empty()
    bar = st.progress(0)
    
    ph.info("📥 Mendownload video...")
    if download_video(url):
        bar.progress(20)
        source_file = f"{TEMP_DIR}/source.mp4"
        
        all_words = []
        source_clip = VideoFileClip(source_file)
        total_dur = source_clip.duration
        
        # Transkripsi hanya jika subtitle aktif
        if use_subtitle:
            ph.info("🎤 Transkripsi Audio (Whisper)...")
            model = load_whisper_model()
            source_clip.audio.write_audiofile(f"{TEMP_DIR}/audio.wav", logger=None)
            result = model.transcribe(f"{TEMP_DIR}/audio.wav", word_timestamps=True, fp16=False)
            all_words = [w for s in result['segments'] for w in s['words']]
        
        source_clip.close()
        bar.progress(50)
        
        intervals = generate_intervals(total_dur, num_clips, duration)
        st.success(f"Video {total_dur/60:.1f} menit -> {len(intervals)} Klip.")
        
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
                        st.download_button(f"⬇️ Part {i+1}", f, file_name=f"Short_{i+1}.mp4")
            except Exception as e:
                st.error(f"Gagal: {e}")
                
        bar.progress(100)
        ph.success("✅ Selesai!")
    else:
        st.error("Gagal download.")