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
    st.warning("yt-dlp not installed. For YouTube/Dropbox links, install it: pip install yt-dlp")

# ================== Page Config ==================
st.set_page_config(
    page_title="Hospital Management System AI Voiceover | GlobalInternet.py",
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

# ================== Function to generate chime sound ==================
def generate_chime(output_path, duration=0.8, frequency=880):
    """Generate a short chime sound using ffmpeg (sine wave with fade out)."""
    cmd = [
        "ffmpeg", "-f", "lavfi", "-i", f"sine=f={frequency}:d={duration}",
        "-af", f"afade=t=out:st={duration-0.3}:d=0.3,volume=0.5",
        "-ac", "2", "-ar", "44100", "-c:a", "aac", "-b:a", "128k",
        output_path, "-y"
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return os.path.exists(output_path)

def append_sound_to_audio(original_audio, chime_audio, output_audio, silence_gap=0.2):
    """Append a chime after a short silence to the original audio."""
    # Create a temporary silence file
    silence_file = "temp_silence.mp3"
    cmd_silence = [
        "ffmpeg", "-f", "lavfi", "-i", f"aevalsrc=0:d={silence_gap}",
        "-ac", "2", "-ar", "44100", "-c:a", "aac", "-b:a", "128k",
        silence_file, "-y"
    ]
    subprocess.run(cmd_silence, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Create concat list: original + silence + chime
    concat_list = "concat_list.txt"
    with open(concat_list, "w") as f:
        f.write(f"file '{original_audio}'\n")
        f.write(f"file '{silence_file}'\n")
        f.write(f"file '{chime_audio}'\n")
    
    cmd_concat = [
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c", "copy", output_audio, "-y"
    ]
    subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Cleanup
    for f in [silence_file, concat_list]:
        if os.path.exists(f):
            os.remove(f)
    return os.path.exists(output_audio)

# ================== TRANSLATION FUNCTION (Groq) ==================
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

# ================== Sidebar with Female Voices (3 languages) ==================
st.sidebar.markdown("## GlobalInternet.py")
st.sidebar.markdown("### AI Voiceover for Hospital Management System")
st.sidebar.markdown("Built by **Gesner Deslandes**, Engineer-in-Chief")
st.sidebar.markdown("---")

voice_options = {
    "English (US Female - Jenny)": {"code": "en-US-JennyNeural", "language": "English"},
    "Français (French Female - Denise)": {"code": "fr-FR-DeniseNeural", "language": "French"},
    "Español (Spanish Female - Elvira)": {"code": "es-ES-ElviraNeural", "language": "Spanish"},
}
selected_voice_label = st.sidebar.selectbox("Select Female Voice for Narration", list(voice_options.keys()))
voice_code = voice_options[selected_voice_label]["code"]
target_language = voice_options[selected_voice_label]["language"]

st.sidebar.markdown("---")
st.sidebar.markdown("### How it works")
st.sidebar.markdown("1. The app downloads your silent demo video from Dropbox.")
st.sidebar.markdown("2. Your English script is **automatically translated** into the selected language.")
st.sidebar.markdown("3. A pure native female AI voice reads the translated script.")
st.sidebar.markdown("4. A pleasant **success chime** is added at the end.")
st.sidebar.markdown("5. The final video includes the voiceover, chime, and subtitles – ready to share!")

# ================== Main Interface ==================
st.title("🏥 Add a Native Female Voiceover + Ending Chime to Your HMS Demo")
st.markdown("### Your English script will be translated and spoken by a real native female voice – with a satisfying chime at the end.")

col_left, col_right = st.columns([2, 1.8])

with col_left:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("#### Source Video (mute)")
    default_video_url = "https://www.dropbox.com/scl/fi/cg1edllnn2jbh1c25acrm/Hospi.mp4?rlkey=uumdod6ku8mng50d02lgatz6d&st=1hdwqlc3&dl=0"
    video_url = st.text_input("Video URL (Dropbox, YouTube, or direct MP4):", value=default_video_url)
    st.markdown("---")
    
    st.markdown("#### Narration Script (English)")
    default_script = """🎬 Introduction to our Hospital Management System. Watch this short video introduction – then click where it says 'Watch the full video on YouTube' for a complete walkthrough.

In this demo, we will click through the main modules: Dashboard Overview, Patient Management, Billing & Revenue, Pharmacy, Laboratory, Radiology, Inventory, and Reports – all showcasing real-time operations and integrated EMR.

This software is multi-specialty, built to streamline your healthcare operations. It includes powerful reporting and analytics to help you make data-driven decisions.

If you want to see the full, detailed demonstration, please visit our YouTube channel and click on the 'Watch the full video' link.

This Hospital Management System was built by Gesner Deslandes, Engineer‑in‑Chief at GlobalInternet.py. To get in touch with us, call (509) 4738 5663 or email deslandes78@gmail.com. We are the best software company ever."""
    
    english_script = st.text_area("English script (must include credit and contact):", height=350, value=default_script)
    
    if "Gesner Deslandes" not in english_script or "GlobalInternet.py" not in english_script:
        st.warning("⚠️ Your script must include the credit: 'Built by Gesner Deslandes, Engineer‑in‑Chief at GlobalInternet.py.'")
    if "(509) 4738 5663" not in english_script or "deslandes78@gmail.com" not in english_script:
        st.warning("⚠️ Please include the contact phone number and email in the script.")
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("#### Generate Narrated Video")
    st.markdown(f"**Selected voice:** {selected_voice_label}")
    st.markdown(f"**Target language for voice:** {target_language}")
    generate_btn = st.button("🎤 Create Voiceover Video (with chime)", use_container_width=True)
    
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
                final_english = "This Hospital Management System was built by Gesner Deslandes, Engineer‑in‑Chief at GlobalInternet.py. " + final_english
                st.info("Added missing credit line to script.")
            if "(509) 4738 5663" not in final_english:
                final_english = final_english + " Contact us at (509) 4738 5663 or deslandes78@gmail.com. We are the best software company ever."
                st.info("Added contact information.")
            
            st.markdown('<div class="status-box">', unsafe_allow_html=True)
            status = st.empty()
            progress_bar = st.progress(0)
            
            try:
                for f in ["video.mp4", "translated_voice.mp3", "subtitles.srt", "final_output.mp4", "extended_video.mp4", "chime.mp3", "voice_with_chime.mp3"]:
                    if os.path.exists(f):
                        os.remove(f)
                
                status.text("📥 Downloading video...")
                progress_bar.progress(10)
                if not download_video(video_url, "video.mp4"):
                    raise Exception("Failed to download video. Please check the link.")
                video_duration = get_duration("video.mp4")
                if video_duration <= 0:
                    video_duration = 90.0
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
                
                status.text("🗣️ Generating pure native female voiceover...")
                progress_bar.progress(40)
                output_audio = "translated_voice.mp3"
                fallback_voice = "en-US-JennyNeural"
                tts_success = asyncio.run(generate_tts(final_script, output_audio, voice_code, fallback_voice))
                if not tts_success:
                    raise Exception("TTS generation failed.")
                audio_duration = get_duration(output_audio)
                status.text(f"Voiceover duration: {audio_duration:.1f} seconds")
                
                # Generate chime and append to voiceover
                status.text("🔔 Adding ending chime...")
                progress_bar.progress(55)
                generate_chime("chime.mp3", duration=0.8, frequency=880)
                if not append_sound_to_audio(output_audio, "chime.mp3", "voice_with_chime.mp3", silence_gap=0.2):
                    st.warning("Failed to append chime, using original voiceover only.")
                    final_audio = output_audio
                else:
                    final_audio = "voice_with_chime.mp3"
                    audio_duration = get_duration(final_audio)
                    status.text(f"Audio with chime duration: {audio_duration:.1f} seconds")
                
                status.text("🔄 Synchronizing video and audio...")
                progress_bar.progress(70)
                if audio_duration > video_duration:
                    st.warning(f"Audio is longer ({audio_duration:.1f}s) than video ({video_duration:.1f}s). Extending video.")
                    working_video = extend_video_with_last_frame("video.mp4", "extended_video.mp4", audio_duration)
                    final_duration = audio_duration
                else:
                    working_video = "video.mp4"
                    final_duration = video_duration
                
                generate_srt_file(final_script, final_duration, "subtitles.srt")
                
                status.text("🎬 Mixing audio and burning subtitles...")
                final_output = "final_output.mp4"
                cmd = [
                    "ffmpeg", "-i", working_video, "-i", final_audio,
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
                
                for tmp in ["video.mp4", "translated_voice.mp3", "subtitles.srt", "extended_video.mp4", "chime.mp3", "voice_with_chime.mp3"]:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                
                progress_bar.progress(100)
                status.text("✅ Narration complete with ending chime!")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.success("Your narrated video is ready! The ending chime makes the finish satisfying.")
                st.video(final_output, format="video/mp4")
                with open(final_output, "rb") as f:
                    st.download_button("⬇️ Download Narrated Video (MP4)", f, file_name="hms_narrated_with_chime.mp4", mime="video/mp4", use_container_width=True)
                
            except Exception as e:
                progress_bar.empty()
                status.empty()
                st.error(f"Error: {str(e)}")
                st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="footer-white-right">
        Built by Gesner Deslandes, Engineer-in-Chief at GlobalInternet.py | Pure Native AI Voice Narration + Ending Chime.
    </div>
    """,
    unsafe_allow_html=True
)
