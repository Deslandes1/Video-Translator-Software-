import streamlit as st
import os
import subprocess
import requests
import asyncio
import re
from groq import Groq
import edge_tts

# yt-dlp (optional)
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    st.warning("yt-dlp not installed. For YouTube/Vimeo, install it: pip install yt-dlp")

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
    words = text.split()
    if not words:
        words = ["Processing..."]
    chunk_size = 6
    chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
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

def clean_repetitions(text):
    words = text.split()
    if len(words) > 400 and words[-10:] and len(set(words[-10:])) < 2:
        unique = []
        for w in words:
            if w not in unique or len(unique) > 100:
                break
            unique.append(w)
        return " ".join(unique)
    return text

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

# ================== Download functions (unchanged) ==================
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

def check_cookies_format(cookie_path):
    if not cookie_path or not os.path.exists(cookie_path):
        return False, "No cookie file"
    try:
        with open(cookie_path, 'r') as f:
            first_line = f.readline().strip()
            if not first_line.startswith('# Netscape HTTP Cookie File'):
                return False, f"Invalid format: first line is '{first_line[:50]}' (should start with '# Netscape HTTP Cookie File')"
            content = f.read()
            if not re.search(r'^[^#].*\t.*\t.*\t.*\t.*\t.*$', content, re.MULTILINE):
                return False, "No valid cookie entries found"
            return True, "OK"
    except Exception as e:
        return False, str(e)

def download_video_with_ytdlp_subprocess(url, output_path, cookie_file):
    cmd = [
        "yt-dlp",
        "--cookies", cookie_file,
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--output", output_path,
        "--quiet", "--no-warnings",
        "--concurrent-fragments", "8",
        "--retries", "10",
        "--sleep-interval", "5",
        "--max-sleep-interval", "10",
        "--no-check-certificates",
        url
    ]
    try:
        st.info("Running yt-dlp command line with cookies...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            st.error(f"yt-dlp subprocess error: {result.stderr}")
            return False
        return True
    except Exception as e:
        st.error(f"yt-dlp subprocess exception: {e}")
        return False

def download_video(url, output_path, cookie_file=None):
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
            if cookie_file and os.path.exists(cookie_file):
                if download_video_with_ytdlp_subprocess(url, output_path, cookie_file):
                    if is_valid_video(output_path):
                        st.success("Downloaded with yt-dlp command line.")
                        return True

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

# ================== Sidebar with Female Voices ==================
st.sidebar.markdown("## GlobalInternet.py")
st.sidebar.markdown("### AI Multi-Language Voice Translator")
st.sidebar.markdown("Built by **Gesner Deslandes**, Engineer-in-Chief")
st.sidebar.markdown("---")

st.sidebar.markdown("### YouTube Authentication (optional)")
st.sidebar.markdown("Upload a `cookies.txt` file (Netscape format) from your browser while logged into YouTube.")
cookies_file = st.sidebar.file_uploader("Upload cookies.txt", type=["txt"])
cookies_path = None
if cookies_file is not None:
    cookies_path = "cookies.txt"
    with open(cookies_path, "wb") as f:
        f.write(cookies_file.getbuffer())
    valid, msg = check_cookies_format(cookies_path)
    if valid:
        st.sidebar.success("Cookies file looks valid. YouTube downloads should work.")
    else:
        st.sidebar.error(f"Invalid cookies file: {msg}")
        st.sidebar.info("Please export cookies again using the 'Get cookies.txt LOCALLY' extension in Edge/Chrome.")
        cookies_path = None
else:
    st.sidebar.info("No cookies provided. YouTube links may fail. For best results, export cookies from a logged‑in YouTube session.")

with st.sidebar.expander("📖 How to get cookies.txt (Edge)"):
    st.markdown("""
    1. Install **"Get cookies.txt LOCALLY"** from [Edge Add-ons](https://microsoftedge.microsoft.com/addons/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc).
    2. Log into YouTube in Edge.
    3. Click the extension icon → **Export** → **Export All Cookies**.
    4. Upload the downloaded file here.
    """)

st.sidebar.markdown("---")

# Updated voice options with FEMALE voices
voice_options = {
    "English (US Female - Jenny)": "en-US-JennyNeural",
    "English (UK Female - Sonia)": "en-GB-SoniaNeural",
    "Français (French Female - Denise)": "fr-FR-DeniseNeural",
    "Español (Spanish Female - Elvira)": "es-ES-ElviraNeural",
    "中文 (Chinese Female - Xiaoxiao)": "zh-CN-XiaoxiaoNeural",
    "العربية (Arabic Female - Amina)": "ar-SA-AminaNeural",
    "Português (Portuguese Female - Francisca)": "pt-BR-FranciscaNeural",
    "Jamaican Patois (English Female)": "en-US-JennyNeural"   # fallback
}
selected_voice_label = st.sidebar.selectbox("Select Female Voice Overdub", list(voice_options.keys()))
voice_code = voice_options[selected_voice_label]

st.title("🎨 AI Voiceover for Your Color Game Demo")
st.markdown("### Turn your mute gameplay video into a narrated tutorial with a natural female voice.")
st.markdown("---")

col_left, col_right = st.columns([2, 1.8])

with col_left:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("<h4>Source Video</h4>", unsafe_allow_html=True)
    
    # Pre‑fill the Dropbox link (mute demo video)
    default_url = "https://www.dropbox.com/scl/fi/yzg1adtnbldj5l6zoo54j/Color-game.mp4?rlkey=4eetqcb4xcqf6nlqi8eijcsbs&st=sz2ryrro&dl=0"
    video_url = st.text_input("Paste your mute video link (Dropbox, YouTube, direct MP4):", value=default_url)
    
    st.markdown("---")
    st.markdown("<h4>Voiceover Script</h4>", unsafe_allow_html=True)
    script_option = st.radio("Script source:", ["AI Auto-generate description of the color game", "Write my own script"])
    
    if script_option == "Write my own script":
        custom_script = st.text_area("Enter your voiceover text (in the language of the selected female voice):", height=200,
            placeholder="Example: Welcome to the Color Match Game...")
    else:
        # Use a pre‑written script that describes the game exactly as shown in the video
        auto_script = """Welcome to the Color Match Game, created by Gesner Deslandes, Engineer‑in‑Chief at GlobalInternet.py.

In this fun educational game, you see a row of colorful swatches at the top. Each swatch has no label. Below, you see the names of the colors. Your task is to drag each color name and drop it onto the matching color square.

When you make a correct match, you hear a cheerful bingo sound and the swatch gets a golden checkmark. If you drop the wrong name, you hear an error sound – but don't worry, you can try again.

Watch as I match all eight colors: red, orange, yellow, green, blue, purple, pink, and brown. After the last correct match, balloons fly across the screen and a victory fanfare plays. The game also includes a reset button to shuffle the colors and play again.

On the left sidebar, you'll find my contact information, the website, and competitive pricing to get the full source code delivered by email.

This game is perfect for kids learning colors. Try it yourself and enjoy the celebration!"""
        st.info("AI will use the script below (you can edit it if needed):")
        custom_script = st.text_area("Edit the auto-generated script:", value=auto_script, height=250)
    
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("<h4>Generate Narrated Video</h4>", unsafe_allow_html=True)
    
    process_btn = st.button("🎤 Generate Female Voiceover Video", use_container_width=True)
    
    if process_btn:
        if not video_url:
            st.error("Please provide a video link.")
        elif not custom_script.strip():
            st.error("Please provide a script or use auto-generation.")
        elif "GROQ_API_KEY" not in st.secrets:
            st.error("Missing Groq API key. Add GROQ_API_KEY to your Streamlit secrets.")
        else:
            st.markdown('<div class="status-box">', unsafe_allow_html=True)
            st.markdown("<h5>Pipeline Progress</h5>", unsafe_allow_html=True)
            status = st.empty()
            progress_bar = st.progress(0)
            
            try:
                # Clean previous files
                for f in ["video.mp4", "extracted_audio.mp3", "translated_voice.mp3", "subtitles.srt", "final_output.mp4", "extended_video.mp4"]:
                    if os.path.exists(f):
                        os.remove(f)
                
                status.text("Downloading video...")
                progress_bar.progress(10)
                if not download_video(video_url, "video.mp4", cookie_file=cookies_path):
                    raise Exception("Failed to download video. Check the link and cookies if needed.")
                
                video_duration = get_duration("video.mp4")
                if video_duration <= 0:
                    video_duration = 30.0
                
                status.text("Generating voiceover with female AI voice...")
                progress_bar.progress(40)
                
                # Use the custom script directly (no extra AI call needed)
                localized_text = custom_script.strip()
                # Ensure credit line is present
                if "Gesner Deslandes" not in localized_text or "GlobalInternet.py" not in localized_text:
                    localized_text = "This game was created by Gesner Deslandes, Engineer‑in‑Chief at GlobalInternet.py. " + localized_text
                
                status.text("Synthesizing speech...")
                progress_bar.progress(60)
                output_audio = "translated_voice.mp3"
                # Define fallback voice (same as selected if female, else Jenny)
                fallback = "en-US-JennyNeural"
                tts_success = asyncio.run(generate_tts(localized_text, output_audio, voice_code, fallback))
                if not tts_success:
                    raise Exception("TTS generation failed.")
                audio_duration = get_duration(output_audio)
                
                status.text("Synchronizing video and audio...")
                progress_bar.progress(80)
                if audio_duration > video_duration:
                    st.warning(f"Voiceover longer ({audio_duration:.1f}s) than video ({video_duration:.1f}s). Extending video.")
                    working_video = extend_video_with_last_frame("video.mp4", "extended_video.mp4", audio_duration)
                    final_duration = audio_duration
                else:
                    working_video = "video.mp4"
                    final_duration = video_duration
                
                generate_srt_file(localized_text, final_duration, "subtitles.srt")
                
                status.text("Mixing audio and burning subtitles...")
                final_output = "final_output.mp4"
                cmd = [
                    "ffmpeg", "-i", working_video, "-i", output_audio,
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-vf", "subtitles=subtitles.srt",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k",
                    final_output, "-y"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    st.error(f"FFmpeg error: {result.stderr}")
                    raise Exception("Mixing failed.")
                
                for tmp in ["video.mp4", "extracted_audio.mp3", "translated_voice.mp3", "subtitles.srt", "extended_video.mp4"]:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                if cookies_path and os.path.exists(cookies_path):
                    os.remove(cookies_path)
                
                progress_bar.progress(100)
                status.text("Narration complete!")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.success("Your narrated video is ready. Download it below:")
                st.video(final_output, format="video/mp4")
                
                # Provide download button
                with open(final_output, "rb") as f:
                    st.download_button("📥 Download Narrated Video", f, file_name="color_game_narrated.mp4", mime="video/mp4")
                
            except Exception as e:
                progress_bar.empty()
                status.empty()
                st.error(f"Pipeline error: {str(e)}")
                st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="footer-white-right">
        Built by Gesner Deslandes, Engineer-in-Chief at GlobalInternet.py | AI-Powered Voice Narration.
    </div>
    """,
    unsafe_allow_html=True
)
