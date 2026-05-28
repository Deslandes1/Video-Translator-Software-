import streamlit as st
import os
import subprocess
import requests
import asyncio
import re
import sys
import importlib

# Ensure yt-dlp is installed (for YouTube/Dropbox/etc.)
try:
    import yt_dlp
except ImportError:
    st.info("Installing yt-dlp for video downloads...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
    import yt_dlp

from groq import Groq
import edge_tts

# ================== Page Config ==================
st.set_page_config(
    page_title="GlobalInternet.py AI Video Voice Translator",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================== Styling ==================
st.markdown(
    """
    <style>
    .stApp, [data-testid="stSidebar"], section[data-testid="stSidebar"] {
        background-color: #0b1329 !important;
        background-image: radial-gradient(at 0% 0%, hsla(224,53%,12%,1) 0, transparent 55%), 
                          radial-gradient(at 100% 0%, hsla(210,70%,15%,1) 0, transparent 55%),
                          radial-gradient(at 50% 100%, hsla(220,60%,10%,1) 0, transparent 50%) !important;
        background-attachment: fixed !important;
    }
    h1, h2, h3, h4, p, span, label, li { color: #ffffff !important; }
    .feature-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px; padding: 25px; margin-bottom: 20px;
    }
    .status-box {
        background: rgba(11, 19, 41, 0.7); padding: 20px;
        border-radius: 8px; border-left: 5px solid #00ebc7; margin-bottom: 20px;
    }
    .footer-white-right {
        text-align: right !important; color: #ffffff !important;
        font-weight: 800 !important; font-size: 0.9rem; margin-top: 60px;
    }
    .stButton>button {
        background-color: #00ebc7 !important; color: #0b1329 !important;
        font-weight: 700 !important; border: none !important; width: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ================== Helper Functions ==================
def get_duration(file_path):
    """Return duration in seconds using ffprobe."""
    if not os.path.exists(file_path):
        return 0.0
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        return float(result.stdout.decode('utf-8').strip())
    except:
        return 0.0

def pad_audio_with_silence(input_audio, output_audio, target_duration):
    """Append silence at the end of audio to exactly reach target_duration."""
    current = get_duration(input_audio)
    if current >= target_duration - 0.1:
        subprocess.run(["ffmpeg", "-i", input_audio, "-c", "copy", output_audio, "-y"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_audio
    pad_duration = target_duration - current
    subprocess.run([
        "ffmpeg", "-i", input_audio,
        "-f", "lavfi", "-i", f"aevalsrc=0:duration={pad_duration}:sample_rate=48000",
        "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1",
        "-c:a", "aac", "-b:a", "128k",
        output_audio, "-y"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_audio

def extend_video_with_last_frame(original_video, output_video, target_duration):
    """Extend video by freezing the last frame; also extends audio with silence."""
    orig_dur = get_duration(original_video)
    if orig_dur >= target_duration - 0.1:
        subprocess.run([
            "ffmpeg", "-i", original_video, "-c:v", "copy", "-c:a", "copy", output_video, "-y"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_video
    pad_duration = target_duration - orig_dur
    subprocess.run([
        "ffmpeg", "-i", original_video,
        "-vf", f"tpad=stop_mode=clone:stop_duration={pad_duration}",
        "-af", f"apad=pad_dur={pad_duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(target_duration),
        output_video, "-y"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_video

def generate_srt_file(text, duration_sec, output_srt_path):
    """Create a simple SRT file that displays the entire text over the video."""
    words = text.split()
    if not words:
        words = ["Processing..."]
    chunk_size = 6
    chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
    num_chunks = len(chunks)
    chunk_duration = duration_sec / max(1, num_chunks)
    
    with open(output_srt_path, "w", encoding="utf-8") as f:
        for idx, chunk in enumerate(chunks):
            start_time = idx * chunk_duration
            end_time = (idx + 1) * chunk_duration
            def fmt(sec):
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s = int(sec % 60)
                ms = int((sec % 1) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
            f.write(f"{idx+1}\n{fmt(start_time)} --> {fmt(end_time)}\n{' '.join(chunk)}\n\n")

def clean_repetitions(text):
    """Remove obvious repetitive loops."""
    words = text.split()
    if len(words) > 400:
        if words[-10:] and len(set(words[-10:])) < 2:
            unique = []
            for w in words:
                if w not in unique or len(unique) > 100:
                    break
                unique.append(w)
            return " ".join(unique)
    return text

# ================== Async TTS (must be called with asyncio.run) ==================
async def generate_tts(text, output_path, voice_name, fallback_voice):
    try:
        communicate = edge_tts.Communicate(text, voice_name)
        await communicate.save(output_path)
        if os.path.getsize(output_path) == 0:
            raise Exception("Empty file")
        return True
    except Exception as e:
        st.warning(f"Primary voice '{voice_name}' failed: {e}. Trying fallback {fallback_voice}.")
        try:
            communicate = edge_tts.Communicate(text, fallback_voice)
            await communicate.save(output_path)
            if os.path.getsize(output_path) == 0:
                raise Exception("Fallback empty")
            return True
        except Exception as e2:
            st.error(f"Fallback also failed: {e2}")
            return False

# ================== Download Video Function ==================
def download_video(url, output_path):
    """Download video using yt-dlp, returns True on success."""
    try:
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        st.warning(f"yt-dlp failed: {e}")
        # Try direct download for raw MP4 links
        try:
            r = requests.get(url, stream=True, timeout=30)
            r.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception as e2:
            st.error(f"Direct download also failed: {e2}")
            return False

# ================== Sidebar ==================
st.sidebar.markdown("## GlobalInternet.py")
st.sidebar.markdown("### AI Multi-Language Voice Translator")
st.sidebar.markdown("Built by **Gesner Deslandes**, Engineer-in-Chief")
st.sidebar.markdown("---")

voice_options = {
    "Français (Native French Male - Henri)": "fr-FR-HenriNeural",
    "Español (Native Spanish Male - Alvaro)": "es-ES-AlvaroNeural",
    "English (Native US Male - Christopher)": "en-US-ChristopherNeural",
    "Kreyòl Ayisyen (Haitian Creole Native - Michelle)": "ht-HT-MichelleNeural",
    "中文 (Chinese Mandarin Male - Yunxi)": "zh-CN-YunxiNeural",
    "العربية (Arabic Male - Hamed)": "ar-SA-HamedNeural",
    "Português (Brazilian Portuguese Male - Antonio)": "pt-BR-AntonioNeural"
}
selected_voice_label = st.sidebar.selectbox("Select Native Overdub Language Layer", list(voice_options.keys()))
voice_code = voice_options[selected_voice_label]

st.title("AI Video Voice Translation Engine")
st.markdown("### On-Demand Multimedia Linguistic Overdubbing Platform")
st.markdown("---")

col_left, col_right = st.columns([2, 1.8])

with col_left:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("<h4>Source Input Interface</h4>", unsafe_allow_html=True)
    input_method = st.radio(
        "Select Input Source Layer:",
        ["Upload Video from this Computer (.MP4)", "Paste Video Link (YouTube, Dropbox, Google Drive, Vimeo, direct MP4)"]
    )
    video_ready = False
    download_url = ""
    uploaded_file = None
    
    if input_method == "Paste Video Link (YouTube, Dropbox, Google Drive, Vimeo, direct MP4)":
        raw_url = st.text_input("Paste Video Link Here:").strip()
        if raw_url:
            if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
                st.error("Please enter a valid URL (starts with http:// or https://)")
            else:
                download_url = raw_url
                video_ready = True
                try:
                    st.video(raw_url)
                except Exception:
                    st.info("Link accepted – will be downloaded during processing.")
    else:
        uploaded_file = st.file_uploader("Choose a video file:", type=["mp4", "mov", "mkv", "avi"])
        if uploaded_file is not None:
            st.video(uploaded_file)
            video_ready = True
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("<h4>Neural Pipeline Controls</h4>", unsafe_allow_html=True)
    process_btn = st.button("Execute Voice Sync Overdub & Captions")
    
    if process_btn:
        if not video_ready:
            st.error("Error: Please provide a video file or a valid link.")
        elif "GROQ_API_KEY" not in st.secrets:
            st.error("Missing Groq API key. Add GROQ_API_KEY to your Streamlit secrets.")
        else:
            st.markdown('<div class="status-box">', unsafe_allow_html=True)
            st.markdown("<h5>System Pipeline Progress Status</h5>", unsafe_allow_html=True)
            status = st.empty()
            progress_bar = st.progress(0)
            
            try:
                # Cleanup old files
                for f in ["video.mp4", "extracted_audio.mp3", "translated_voice.mp3", "subtitles.srt", "final_output.mp4", "padded_audio.mp3", "extended_video.mp4"]:
                    if os.path.exists(f):
                        os.remove(f)
                
                # Step 1: Get video file
                status.text("Downloading / reading video...")
                progress_bar.progress(10)
                if uploaded_file:
                    with open("video.mp4", "wb") as f:
                        f.write(uploaded_file.getbuffer())
                else:
                    if not download_video(download_url, "video.mp4"):
                        raise Exception("Failed to download video. Please check the link or use a direct file upload.")
                
                if not os.path.exists("video.mp4") or os.path.getsize("video.mp4") == 0:
                    raise Exception("Video file is empty or could not be saved.")
                
                # Step 2: Get video duration
                video_duration = get_duration("video.mp4")
                if video_duration <= 0:
                    video_duration = 30.0
                
                # Step 3: Extract original audio for transcription
                status.text("Extracting audio...")
                progress_bar.progress(25)
                subprocess.run([
                    "ffmpeg", "-i", "video.mp4", "-vn",
                    "-acodec", "libmp3lame", "-q:a", "2", "extracted_audio.mp3", "-y"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                if not os.path.exists("extracted_audio.mp3"):
                    raise Exception("Failed to extract audio from video.")
                
                # Step 4: Transcribe with Groq Whisper
                status.text("Transcribing original audio...")
                progress_bar.progress(40)
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                with open("extracted_audio.mp3", "rb") as audio_file:
                    transcription = client.audio.translations.create(
                        file=("extracted_audio.mp3", audio_file.read()),
                        model="whisper-large-v3",
                        response_format="text"
                    )
                base_text = str(transcription).strip()
                
                # Step 5: Localize to target language
                status.text("Localizing text to selected language...")
                progress_bar.progress(55)
                if "zh-CN" in voice_code:
                    lang_instr = "natural, idiomatic Mandarin Chinese (Simplified). Output in Simplified Chinese characters only."
                elif "ar-SA" in voice_code:
                    lang_instr = "natural, idiomatic Modern Standard Arabic. Output in Arabic script only. Keep it concise (max 200 words)."
                elif "pt-BR" in voice_code:
                    lang_instr = "natural, idiomatic Brazilian Portuguese. Output in Portuguese only."
                elif "fr-FR" in voice_code:
                    lang_instr = "natural, idiomatic French (Parisian)."
                elif "es-ES" in voice_code:
                    lang_instr = "natural, idiomatic Spanish (Castilian)."
                elif "ht-HT" in voice_code:
                    lang_instr = "natural, idiomatic Haitian Creole (Kreyòl Ayisyen)."
                else:
                    lang_instr = "natural, idiomatic US English."
                
                system_prompt = f"""You are an expert voiceover localizer. Rewrite the following transcript into fluid, natural spoken prose.
Target language/style: {lang_instr}
Rules:
- Keep the original meaning exactly.
- Remove stiff grammar, literal translations, and repetition.
- Optimize for smooth voiceover delivery.
- Return ONLY the polished text, nothing else."""
                
                response = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": base_text}
                    ],
                    temperature=0.2,
                    max_tokens=800,
                    frequency_penalty=0.5,
                    presence_penalty=0.5
                )
                localized_text = response.choices[0].message.content.strip()
                localized_text = clean_repetitions(localized_text)
                st.info(f"Localized script: \"{localized_text[:300]}...\" (truncated)")
                
                # Step 6: Generate TTS (using asyncio.run)
                status.text("Generating voiceover...")
                progress_bar.progress(70)
                output_audio = "translated_voice.mp3"
                if "fr" in voice_code:
                    fallback = "fr-FR-HenriNeural"
                elif "es" in voice_code:
                    fallback = "es-ES-AlvaroNeural"
                elif "ht" in voice_code:
                    fallback = "fr-FR-HenriNeural"
                else:
                    fallback = "en-US-ChristopherNeural"
                
                tts_success = asyncio.run(generate_tts(localized_text, output_audio, voice_code, fallback))
                if not tts_success:
                    raise Exception("TTS generation failed.")
                if not os.path.exists(output_audio) or os.path.getsize(output_audio) == 0:
                    raise Exception("TTS produced an empty file.")
                audio_duration = get_duration(output_audio)
                
                # Step 7: Synchronize video and audio durations
                status.text("Synchronizing video and audio...")
                progress_bar.progress(85)
                if audio_duration > video_duration:
                    st.warning(f"Voiceover longer ({audio_duration:.1f}s) than video ({video_duration:.1f}s). Extending video.")
                    working_video = extend_video_with_last_frame("video.mp4", "extended_video.mp4", audio_duration)
                    working_audio = output_audio
                    final_duration = audio_duration
                else:
                    st.info(f"Video longer ({video_duration:.1f}s) than voiceover ({audio_duration:.1f}s). Padding audio with silence.")
                    working_audio = pad_audio_with_silence(output_audio, "padded_audio.mp3", video_duration)
                    working_video = "video.mp4"
                    final_duration = video_duration
                
                # Step 8: Generate subtitles for final duration
                generate_srt_file(localized_text, final_duration, "subtitles.srt")
                
                # Step 9: Mix audio and burn subtitles
                status.text("Mixing and burning subtitles...")
                final_output = "final_output.mp4"
                cmd = [
                    "ffmpeg", "-i", working_video, "-i", working_audio,
                    "-filter_complex", "[0:a]volume=0.2[a1];[1:a]volume=1.5[a2];[a1][a2]amix=inputs=2:duration=longest[a]",
                    "-map", "0:v", "-map", "[a]",
                    "-vf", "subtitles=subtitles.srt",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest",
                    final_output, "-y"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    st.error(f"FFmpeg error: {result.stderr}")
                    raise Exception("Mixing failed.")
                
                if not os.path.exists(final_output) or os.path.getsize(final_output) == 0:
                    raise Exception("Final output file is empty.")
                
                # Cleanup temp files
                for tmp in ["video.mp4", "extracted_audio.mp3", "translated_voice.mp3", "subtitles.srt", "extended_video.mp4", "padded_audio.mp3"]:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                
                progress_bar.progress(100)
                status.text("All systems harmonized! Video ready.")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.success("Final video created successfully:")
                with open(final_output, "rb") as f:
                    st.video(f.read(), format="video/mp4")
                    
            except Exception as e:
                progress_bar.empty()
                status.empty()
                st.error(f"Pipeline error: {str(e)}")
                st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="footer-white-right">
        Built by Gesner Deslandes, Engineer-in-Chief at GlobalInternet.py | Advanced Cognitive Systems Integration.
    </div>
    """,
    unsafe_allow_html=True
)
