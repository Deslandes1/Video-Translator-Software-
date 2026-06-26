import streamlit as st
import os
import subprocess
import requests
import asyncio
import re
import edge_tts
from groq import Groq

try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    st.warning("yt-dlp not installed. For YouTube/Dropbox links, install it: pip install yt-dlp")

# Try to import whisper for transcription
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

st.set_page_config(
    page_title="AI Video Voice Translator | GlobalInternet.py",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# ---------- Helper Functions ----------
def get_duration(file_path):
    if not os.path.exists(file_path):
        return 0.0
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        return float(result.stdout.decode('utf-8').strip())
    except:
        return 0.0

def extend_video_with_last_frame(original_video, output_video, target_duration):
    orig_dur = get_duration(original_video)
    if orig_dur >= target_duration - 0.1:
        subprocess.run([
            "ffmpeg", "-i", original_video, "-c:v", "copy", "-c:a", "copy", output_video, "-y"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_video
    pad_duration = target_duration - orig_dur
    cmd = [
        "ffmpeg", "-i", original_video,
        "-vf", f"tpad=stop_mode=clone:stop_duration={pad_duration}",
        "-af", f"apad=pad_dur={pad_duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        output_video, "-y"
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(output_video) and os.path.getsize(output_video) > 0:
        return output_video
    else:
        raise Exception("Video extension failed")

def generate_srt_file(text, duration_sec, output_srt_path):
    words = text.split()
    chunk_size = 5
    chunks = [words[i:i+chunk_size] for i in range(0, len(words), chunk_size)]
    num_chunks = len(chunks)
    chunk_duration = duration_sec / max(1, num_chunks)

    def fmt(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    with open(output_srt_path, "w", encoding="utf-8") as f:
        for idx, chunk in enumerate(chunks):
            start = idx * chunk_duration
            end = (idx + 1) * chunk_duration
            f.write(f"{idx+1}\n{fmt(start)} --> {fmt(end)}\n{' '.join(chunk)}\n\n")

def split_text_into_chunks(text, max_chars=1000):
    sentences = re.split(r'(?<=[。！？.!?])', text)
    chunks = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) <= max_chars:
            current += sent
        else:
            if current:
                chunks.append(current.strip())
            current = sent
    if current:
        chunks.append(current.strip())
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final_chunks.append(chunk)
        else:
            for i in range(0, len(chunk), max_chars):
                final_chunks.append(chunk[i:i+max_chars])
    return final_chunks

async def generate_tts(text, output_path, voice_name, fallback_voice):
    if len(text) < 1500:
        try:
            comm = edge_tts.Communicate(text, voice_name)
            await comm.save(output_path)
            if os.path.getsize(output_path) > 0:
                return True
        except Exception as e:
            st.warning(f"Direct TTS failed: {e}. Trying fallback.")
            try:
                comm = edge_tts.Communicate(text, fallback_voice)
                await comm.save(output_path)
                return os.path.getsize(output_path) > 0
            except:
                return False
    else:
        st.info(f"Text length {len(text)} chars → splitting into chunks (max 1000 chars).")
        chunks = split_text_into_chunks(text, max_chars=1000)
        temp_files = []
        for i, chunk in enumerate(chunks):
            temp_file = f"temp_tts_{i}.mp3"
            try:
                comm = edge_tts.Communicate(chunk, voice_name)
                await comm.save(temp_file)
                if os.path.getsize(temp_file) == 0:
                    raise Exception("Empty file")
                temp_files.append(temp_file)
            except Exception as e:
                st.warning(f"Chunk {i+1} failed with primary voice: {e}. Trying fallback.")
                try:
                    comm = edge_tts.Communicate(chunk, fallback_voice)
                    await comm.save(temp_file)
                    if os.path.getsize(temp_file) > 0:
                        temp_files.append(temp_file)
                    else:
                        st.error(f"Fallback also failed for chunk {i+1}")
                except Exception as e2:
                    st.error(f"Chunk {i+1} completely failed: {e2}")
        if not temp_files:
            return False
        concat_file = "concat_list.txt"
        with open(concat_file, "w") as f:
            for tf in temp_files:
                f.write(f"file '{tf}'\n")
        cmd = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path, "-y"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for tf in temp_files:
            os.remove(tf)
        os.remove(concat_file)
        return os.path.getsize(output_path) > 0

def translate_text(text, target_language_name, groq_client):
    prompt = f"""You are a professional translator. Translate the following English text into {target_language_name}. 
The translation must be natural, fluent, and culturally appropriate. 
Return ONLY the translated text, nothing else.

English text:
{text}

Translated text ({target_language_name}):"""
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500
        )
        translated = response.choices[0].message.content.strip()
        return translated
    except Exception as e:
        st.error(f"Translation failed: {e}")
        return text

# ---------- Download functions ----------
def is_aria2_available():
    try:
        subprocess.run(["aria2c", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except:
        return False

def is_valid_video(file_path):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return False
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_type", "-of", "default=nokey=1:noprint_wrappers=1", file_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        st.warning(f"ffprobe error: {result.stderr.decode()}")
        return False
    output = result.stdout.decode().strip()
    return output == "video"

def file_info(path):
    if not os.path.exists(path):
        return "does not exist"
    size = os.path.getsize(path)
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=format_name", "-of", "default=noprint_wrappers=1:nokey=1", path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    fmt = result.stdout.decode().strip() if result.returncode == 0 else "unknown"
    return f"exists, size={size} bytes, format={fmt}"

def download_video(url, output_path, cookie_file=None):
    if "dropbox.com" in url and "dl=0" in url:
        url = url.replace("dl=0", "dl=1")
        st.info("Converted Dropbox link to direct download.")
    elif "dropbox.com" in url and "?dl=" not in url:
        url = url + "?dl=1"
        st.info("Added ?dl=1 to Dropbox link.")
    
    if is_aria2_available():
        st.info("Trying aria2c with 16 parallel connections ...")
        cmd = [
            "aria2c", "-x", "16", "-s", "16", "-k", "1M",
            "--console-log-level=error", "-o", output_path, url
        ]
        try:
            subprocess.run(cmd, check=True, timeout=600)
            st.write(f"aria2c result: {file_info(output_path)}")
            if is_valid_video(output_path):
                st.success("Downloaded with aria2c – valid video file.")
                return True
            else:
                st.warning(f"aria2c downloaded file but not a valid video. Info: {file_info(output_path)}")
        except Exception as e:
            st.warning(f"aria2c failed: {e}")

    if YT_DLP_AVAILABLE:
        st.info("Using yt-dlp with parallel fragments...")
        if not output_path.endswith('.mp4'):
            output_path = output_path + '.mp4'
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': False,
            'concurrent_fragment_downloads': 8,
            'retries': 10,
            'fragment_retries': 10,
            'buffersize': 8192 * 16,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'extractor_args': {'youtube': {'skip': ['hls', 'dash']}},
            'sleep_interval': 5,
            'max_sleep_interval': 10,
        }
        if cookie_file and os.path.exists(cookie_file):
            ydl_opts['cookiefile'] = cookie_file
            st.info("Using uploaded cookies.txt for authentication.")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                actual_file = ydl.prepare_filename(info)
                if actual_file and os.path.exists(actual_file):
                    if not actual_file.endswith('.mp4') and os.path.exists(actual_file + '.mp4'):
                        actual_file = actual_file + '.mp4'
                    if actual_file != output_path and os.path.exists(actual_file):
                        os.rename(actual_file, output_path)
            with open(output_path, 'rb') as f:
                head = f.read(500)
                if b'<html' in head.lower() or b'<!doctype' in head.lower():
                    raise Exception("HTML page received")
            st.write(f"yt-dlp result: {file_info(output_path)}")
            if is_valid_video(output_path):
                st.success("Downloaded with yt-dlp – valid video file.")
                return True
            else:
                st.error(f"yt-dlp produced invalid file.")
        except Exception as e:
            st.warning(f"yt-dlp API failed: {e}")

    st.info("Trying direct HTTP download ...")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, stream=True, timeout=60, headers=headers)
        r.raise_for_status()
        content_type = r.headers.get('content-type', '')
        if 'text/html' in content_type:
            st.error("Direct HTTP returned HTML.")
            return False
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192 * 16):
                f.write(chunk)
        if is_valid_video(output_path):
            st.success("Downloaded via direct HTTP.")
            return True
    except Exception as e:
        st.error(f"Direct download failed: {e}")
    return False

# ---------- New transcription function ----------
def transcribe_video(video_path):
    if not WHISPER_AVAILABLE:
        st.error("Whisper is not installed. Please install openai-whisper: pip install openai-whisper")
        return None
    try:
        # Extract audio to a temporary file
        audio_path = "temp_audio.wav"
        cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path, "-y"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            st.error("Failed to extract audio from video. The video may be mute or corrupted.")
            return None
        st.info("Loading Whisper model (small) for transcription...")
        model = whisper.load_model("small")
        result = model.transcribe(audio_path, language="en")
        os.remove(audio_path)
        return result["text"].strip()
    except Exception as e:
        st.error(f"Transcription error: {e}")
        return None

# ---------- Sidebar ----------
st.sidebar.markdown("## GlobalInternet.py")
st.sidebar.markdown("### AI Video Voice Translator")
st.sidebar.markdown("Built by **Gesner Deslandes**, Engineer-in-Chief")
st.sidebar.markdown("---")

voice_options = {
    "English (US Male - Christopher)": {"code": "en-US-ChristopherNeural", "language": "English"},
    "English (US Female - Jenny)": {"code": "en-US-JennyNeural", "language": "English"},
    "English (UK Male - Ryan)": {"code": "en-GB-RyanNeural", "language": "English"},
    "English (UK Female - Sonia)": {"code": "en-GB-SoniaNeural", "language": "English"},
    "Français (French Male - Henri)": {"code": "fr-FR-HenriNeural", "language": "French"},
    "Français (French Female - Denise)": {"code": "fr-FR-DeniseNeural", "language": "French"},
    "Español (Spanish Male - Alvaro)": {"code": "es-ES-AlvaroNeural", "language": "Spanish"},
    "Español (Spanish Female - Elvira)": {"code": "es-ES-ElviraNeural", "language": "Spanish"},
    "中文 (Chinese Male - Yunxi)": {"code": "zh-CN-YunxiNeural", "language": "Mandarin Chinese"},
    "中文 (Chinese Female - Xiaoxiao)": {"code": "zh-CN-XiaoxiaoNeural", "language": "Mandarin Chinese"},
}
selected_voice_label = st.sidebar.selectbox("Select Voice for Narration", list(voice_options.keys()))
voice_code = voice_options[selected_voice_label]["code"]
target_language = voice_options[selected_voice_label]["language"]

st.sidebar.markdown("---")
st.sidebar.markdown("### How it works")
st.sidebar.markdown("1. The app downloads your mute video (Dropbox/YouTube).")
st.sidebar.markdown("2. Your English script is **automatically translated** into the selected language using Groq LLM.")
st.sidebar.markdown("3. A native AI voice reads the translated script.")
st.sidebar.markdown("4. If the voiceover is longer, the video freezes on the last frame until the voice ends.")
st.sidebar.markdown("5. The final video includes the voiceover and subtitles – ready to share!")

# ---------- Main Interface ----------
st.title("🌍 AI Video Voice Translator")
st.markdown("### Turn any mute video into a multilingual narrated video with a realistic AI voice.")

col_left, col_right = st.columns([2, 1.8])

with col_left:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("#### Source Video (mute)")
    video_url = st.text_input("Paste video link (Dropbox, YouTube, direct MP4):", 
                              value="https://www.dropbox.com/scl/fi/example.mp4?dl=0")
    st.markdown("---")
    
    st.markdown("#### Narration Script (English)")
    st.markdown("Write your script in English. It will be automatically translated into the selected language.")
    
    # If we have a generated script in session state, pre‑fill it
    if "generated_script" in st.session_state and st.session_state.generated_script:
        default_script = st.session_state.generated_script
    else:
        default_script = """Welcome to the Top 10 Most In-Demand Software Solutions for 2025, presented by GlobalInternet.py, built by Gesner Deslandes, Engineer-in-Chief.

Let's go through the list. Number one: Website builders like Wix, GoDaddy, and Shopify, starting at three to seventeen dollars per month. Ideal for small businesses and online stores.

Number two: Customer Relationship Management, or CRM, with options like Monday CRM, Pipedrive, and Capsule. Prices start at twelve to twenty-four dollars per user per month.

Number three: Project management tools like Zoho Projects, Jira, and TeamGantt, from four to ten dollars per user per month. Perfect for remote teams and IT projects.

Number four: Accounting and finance software such as QuickBooks Online, Xero, and Wave, ranging from free to eighty dollars per month.

Number five: Email marketing platforms like Brevo, Mailchimp, and GetResponse, starting at nine to nineteen dollars per month.

Number six: E-commerce platforms including Shopify, Wix Core, and Squarespace, from five to thirty-five dollars per month.

Number seven: Inventory management systems like inFlow Inventory and EZOfficeInventory, priced between forty and one hundred twenty-nine dollars per month.

Number eight: Booking and appointment systems such as Spacebring and Domilocus, from about forty-two to one hundred eighty-five dollars per month.

Number nine: Help desk and customer support software like Freshdesk, HappyFox, and InvGate, at seventeen to twenty-nine dollars per agent per month.

Number ten: Social media management tools like Social Champ, Agorapulse, and Sprout Social, from twenty-nine to one hundred ninety-nine dollars per seat per month.

These ten categories cover the most requested software by small and medium businesses. Commerce and front-office tools make up 29 percent of needs, back-office systems account for 23 percent, and CRMs, collaboration platforms, and cybersecurity are top priorities for growing companies.

Now, how can GlobalInternet.py help you? Instead of paying monthly subscriptions for multiple tools, we build custom, unified software tailored exactly to your workflows. Our pricing is competitive: full source code delivery for twenty-nine dollars, source code plus customization for forty-nine dollars, and custom development quoted per project. We deliver the code by email within twenty-four hours after payment.

Contact us today: Phone (509) 4738 5663, email deslandes78@gmail.com. Visit our website at GlobalInternet.py. We are the best at what we do – let us build your next software solution. Thank you for watching."""
    
    english_script = st.text_area("English script (must include credit):", height=400, value=default_script)
    if "Gesner Deslandes" not in english_script or "GlobalInternet.py" not in english_script:
        st.warning("⚠️ Your script must include the credit: 'Built by Gesner Deslandes, Engineer‑in‑Chief at GlobalInternet.py.'")
    
    # Button to extract script from video audio
    st.markdown("---")
    if st.button("🎤 Extract script from video audio (requires Whisper)"):
        if not video_url:
            st.error("Please provide a video URL first.")
        else:
            # Download video if not already present
            if not os.path.exists("video.mp4"):
                with st.spinner("Downloading video..."):
                    if not download_video(video_url, "video.mp4"):
                        st.error("Failed to download video. Please check the link.")
                    else:
                        st.success("Video downloaded.")
            if os.path.exists("video.mp4"):
                with st.spinner("Transcribing audio..."):
                    transcript = transcribe_video("video.mp4")
                    if transcript:
                        st.session_state.generated_script = transcript
                        st.success("Transcript generated! You can now edit it if needed.")
                        st.rerun()
                    else:
                        st.error("Transcription failed. The video might have no audio or Whisper is not installed.")
    
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("#### Generate Narrated Video")
    st.markdown(f"**Selected voice:** {selected_voice_label}")
    st.markdown(f"**Target language for voice:** {target_language}")
    generate_btn = st.button("🎤 Create Voiceover Video", use_container_width=True)
    
    if generate_btn:
        if not video_url:
            st.error("Please provide a video URL.")
        elif not english_script.strip():
            st.error("Please provide a narration script.")
        elif "GROQ_API_KEY" not in st.secrets:
            st.error("Missing Groq API key. Add GROQ_API_KEY to your Streamlit secrets for translation.")
        else:
            final_english = english_script.strip()
            if "Gesner Deslandes" not in final_english or "GlobalInternet.py" not in final_english:
                final_english = "This presentation is brought to you by GlobalInternet.py, built by Gesner Deslandes, Engineer‑in‑Chief. " + final_english
                st.info("Added missing credit line to script.")
            
            st.markdown('<div class="status-box">', unsafe_allow_html=True)
            status = st.empty()
            progress_bar = st.progress(0)
            
            try:
                for f in ["video.mp4", "translated_voice.mp3", "subtitles.srt", "final_output.mp4", "extended_video.mp4"]:
                    if os.path.exists(f):
                        os.remove(f)
                
                status.text("📥 Downloading video...")
                progress_bar.progress(10)
                if not download_video(video_url, "video.mp4"):
                    raise Exception("Failed to download video. Please check the link.")
                video_duration = get_duration("video.mp4")
                if video_duration <= 0:
                    video_duration = 30.0
                status.text(f"Video duration: {video_duration:.1f} seconds")
                
                # Translate script if needed
                if target_language.lower() != "english":
                    status.text(f"🔄 Translating script from English to {target_language}...")
                    progress_bar.progress(25)
                    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                    translated_script = translate_text(final_english, target_language, groq_client)
                    st.info(f"Translated script (preview): {translated_script[:200]}...")
                    final_script = translated_script
                else:
                    final_script = final_english
                
                status.text("🗣️ Generating voiceover...")
                progress_bar.progress(50)
                output_audio = "translated_voice.mp3"
                fallback_voice = "en-US-ChristopherNeural"
                tts_success = asyncio.run(generate_tts(final_script, output_audio, voice_code, fallback_voice))
                if not tts_success:
                    raise Exception("TTS generation failed. Check network or voice code.")
                audio_duration = get_duration(output_audio)
                status.text(f"Voiceover duration: {audio_duration:.1f} seconds")
                
                # Synchronize video and audio (extend video if needed)
                status.text("🔄 Synchronizing video and audio...")
                progress_bar.progress(70)
                if audio_duration > video_duration:
                    st.warning(f"Voiceover is longer ({audio_duration:.1f}s) than video ({video_duration:.1f}s). Extending video with last frame.")
                    working_video = extend_video_with_last_frame("video.mp4", "extended_video.mp4", audio_duration)
                    final_duration = audio_duration
                    status.text(f"Extended video to {final_duration:.1f} seconds (freeze last frame)")
                else:
                    working_video = "video.mp4"
                    final_duration = video_duration
                
                generate_srt_file(final_script, final_duration, "subtitles.srt")
                
                status.text("🎬 Mixing audio and burning subtitles...")
                final_output = "final_output.mp4"
                
                # Subtitle settings: small font (14px), large bottom margin (80px) to keep text low
                if target_language == "Mandarin Chinese":
                    font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
                    if os.path.exists(font_path):
                        vf_filter = f"subtitles=subtitles.srt:fontsdir={os.path.dirname(font_path)}:force_style='FontName=Noto Sans CJK SC,FontSize=14,MarginV=80'"
                    else:
                        vf_filter = "subtitles=subtitles.srt:force_style='FontName=Arial,FontSize=14,MarginV=80'"
                else:
                    vf_filter = "subtitles=subtitles.srt:force_style='FontName=Arial,FontSize=14,MarginV=80'"
                
                cmd = [
                    "ffmpeg", "-i", working_video, "-i", output_audio,
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-vf", vf_filter,
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k",
                    final_output, "-y"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    st.error(f"FFmpeg error: {result.stderr}")
                    raise Exception("Mixing failed.")
                
                # Cleanup
                for tmp in ["video.mp4", "translated_voice.mp3", "subtitles.srt", "extended_video.mp4"]:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                
                progress_bar.progress(100)
                status.text("✅ Narration complete!")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.success("Your narrated video is ready. The voice speaks the selected language natively.")
                st.video(final_output, format="video/mp4")
                with open(final_output, "rb") as f:
                    st.download_button("⬇️ Download Narrated Video (MP4)", f, file_name="narrated_video.mp4", mime="video/mp4", use_container_width=True)
                
            except Exception as e:
                progress_bar.empty()
                status.empty()
                st.error(f"Error: {str(e)}")
                st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="footer-white-right">
        Built by Gesner Deslandes, Engineer-in-Chief at GlobalInternet.py | AI‑Powered Multilingual Voiceover.
    </div>
    """,
    unsafe_allow_html=True
)
