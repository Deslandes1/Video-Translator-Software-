import streamlit as st
import os
import subprocess
import requests
import asyncio
import re
import edge_tts
from groq import Groq

# yt-dlp (optional)
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    st.warning("yt-dlp not installed. For YouTube/Vimeo, install it: pip install yt-dlp")

# ================== Page Config ==================
st.set_page_config(
    page_title="BonardEnterprise AI Voiceover | GlobalInternet.py",
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

# ================== TRANSLATION FUNCTION (Groq) ==================
def translate_text(text, target_language_name, groq_client):
    """Translate English text into the target language using Groq LLM."""
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
        return text  # fallback to original English

# ================== Download functions ==================
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

# ================== Sidebar with Female Voices ==================
st.sidebar.markdown("## GlobalInternet.py")
st.sidebar.markdown("### AI Voiceover for BonardEnterprise Demo")
st.sidebar.markdown("Built by **Gesner Deslandes**, Engineer-in-Chief")
st.sidebar.markdown("---")

# Female voice options with language names for translation
voice_options = {
    "English (US Female - Jenny)": {"code": "en-US-JennyNeural", "language": "English"},
    "English (UK Female - Sonia)": {"code": "en-GB-SoniaNeural", "language": "English"},
    "Français (French Female - Denise)": {"code": "fr-FR-DeniseNeural", "language": "French"},
    "Español (Spanish Female - Elvira)": {"code": "es-ES-ElviraNeural", "language": "Spanish"},
    "中文 (Chinese Female - Xiaoxiao)": {"code": "zh-CN-XiaoxiaoNeural", "language": "Mandarin Chinese"},
    "العربية (Arabic Female - Amina)": {"code": "ar-SA-AminaNeural", "language": "Arabic"},
    "Português (Portuguese Female - Francisca)": {"code": "pt-BR-FranciscaNeural", "language": "Portuguese"},
}
selected_voice_label = st.sidebar.selectbox("Select Female Voice for Narration", list(voice_options.keys()))
voice_code = voice_options[selected_voice_label]["code"]
target_language = voice_options[selected_voice_label]["language"]

st.sidebar.markdown("---")
st.sidebar.markdown("### How it works")
st.sidebar.markdown("1. The app downloads your mute demo video from Dropbox.")
st.sidebar.markdown("2. Your English script is **automatically translated** into the selected language.")
st.sidebar.markdown("3. A pure native female AI voice reads the translated script.")
st.sidebar.markdown("4. The final video includes the voiceover and subtitles – ready to share!")

# ================== Main Interface ==================
st.title("🏢 Add a Native Female Voiceover to Your BonardEnterprise Demo")
st.markdown("### Your English script will be translated and spoken by a real native female voice – no mixed accents.")

col_left, col_right = st.columns([2, 1.8])

with col_left:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("#### Source Video (mute)")
    # The user's BonardEnterprise video link
    default_video_url = "https://www.dropbox.com/scl/fi/c2p07a5kwrwadrmhxt8wv/Boad.mp4?rlkey=v4lgbtr4oyanmsfk21n9ujv2a&st=zmnluey5&dl=0"
    video_url = st.text_input("Video URL (Dropbox, YouTube, or direct MP4):", value=default_video_url)
    st.markdown("---")
    
    st.markdown("#### Narration Script (English)")
    st.markdown("Write your script in English. It will be automatically translated into the selected language.")
    
    # Pre-filled script as per your detailed instructions
    default_script = """Welcome to the official website of BonardEnterprise, built by Gesner Deslandes, Engineer-in-Chief at GlobalInternet.py.

In this video, we will give you a quick tour of the website's key features. First, you'll see the beautifully designed main page. As I scroll up and down, you can get a feel for the modern and professional layout. The main page showcases the latest products from BonardEnterprise.

Now, let's take a look at a product detail page. Here, you will find a detailed description of the product, along with its pricing. This is where visitors can learn everything about the product. I'm now clicking on the 'Comment Section'. This interactive area allows visitors to leave their feedback, ask questions, or share their experience directly under the product. This fosters a great community around the brand.

Next, I will click on the toggle sidebar on the left. As you can see, a menu slides out. Here, visitors can select their preferred language from three options: English, French, and Spanish. This feature makes the website accessible to a wider, international audience.

This website was built by Gesner Deslandes, Engineer-in-Chief at GlobalInternet.py. If you need a professional, modern, and fully functional website for your business, please get in touch with our company, GlobalInternet.py. We are the best at what we do! We deliver top-quality web solutions.

To connect with us, simply visit the BonardEnterprise website. You will find all our contact information, including our email address and office phone number, right there. Thank you for watching."""
    
    english_script = st.text_area("English script (must include credit):", height=400, value=default_script)
    
    # Ensure credit line is present
    if "Gesner Deslandes" not in english_script or "GlobalInternet.py" not in english_script:
        st.warning("⚠️ Your script must include the credit: 'Built by Gesner Deslandes, Engineer‑in‑Chief at GlobalInternet.py.'")
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
            # Ensure credit is present
            final_english = english_script.strip()
            if "Gesner Deslandes" not in final_english or "GlobalInternet.py" not in final_english:
                final_english = "This website was built by Gesner Deslandes, Engineer‑in‑Chief at GlobalInternet.py. " + final_english
                st.info("Added missing credit line to script.")
            
            st.markdown('<div class="status-box">', unsafe_allow_html=True)
            status = st.empty()
            progress_bar = st.progress(0)
            
            try:
                # Cleanup old files
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
                
                # Translate script if target language is not English
                if target_language.lower() != "english":
                    status.text(f"🔄 Translating script from English to {target_language}...")
                    progress_bar.progress(25)
                    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                    translated_script = translate_text(final_english, target_language, groq_client)
                    st.info(f"Translated script (preview): {translated_script[:200]}...")
                    final_script = translated_script
                else:
                    final_script = final_english
                
                status.text("🗣️ Generating pure native female voiceover...")
                progress_bar.progress(50)
                output_audio = "translated_voice.mp3"
                fallback_voice = "en-US-JennyNeural"
                tts_success = asyncio.run(generate_tts(final_script, output_audio, voice_code, fallback_voice))
                if not tts_success:
                    raise Exception("TTS generation failed. Check network or voice code.")
                audio_duration = get_duration(output_audio)
                status.text(f"Voiceover duration: {audio_duration:.1f} seconds")
                
                status.text("🔄 Synchronizing video and audio...")
                progress_bar.progress(75)
                if audio_duration > video_duration:
                    st.warning(f"Voiceover is longer ({audio_duration:.1f}s) than video ({video_duration:.1f}s). Extending video with last frame.")
                    working_video = extend_video_with_last_frame("video.mp4", "extended_video.mp4", audio_duration)
                    final_duration = audio_duration
                else:
                    working_video = "video.mp4"
                    final_duration = video_duration
                
                generate_srt_file(final_script, final_duration, "subtitles.srt")
                
                status.text("🎬 Mixing audio and burning subtitles...")
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
                
                # Cleanup temp files
                for tmp in ["video.mp4", "translated_voice.mp3", "subtitles.srt", "extended_video.mp4"]:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                
                progress_bar.progress(100)
                status.text("✅ Narration complete!")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.success("Your narrated video is ready. The voice speaks pure native language – no English mixed in!")
                st.video(final_output, format="video/mp4")
                with open(final_output, "rb") as f:
                    st.download_button("⬇️ Download Narrated Video (MP4)", f, file_name="bonard_demo_narrated.mp4", mime="video/mp4", use_container_width=True)
                
            except Exception as e:
                progress_bar.empty()
                status.empty()
                st.error(f"Error: {str(e)}")
                st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="footer-white-right">
        Built by Gesner Deslandes, Engineer-in-Chief at GlobalInternet.py | Pure Native AI Voice Narration.
    </div>
    """,
    unsafe_allow_html=True
)
