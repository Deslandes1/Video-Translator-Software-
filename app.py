import streamlit as st
import os
import subprocess
import requests
import asyncio
from groq import Groq
import edge_tts

# 1. Page Configuration
st.set_page_config(
    page_title="GlobalInternet.py AI Video Voice Translator",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Premium Styling Ingestion
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

# 3. Async Helper for True Native Male Voices (now includes Haitian Creole)
async def generate_male_voice(text, output_path, voice_name):
    communicate = edge_tts.Communicate(text, voice_name)
    await communicate.save(output_path)

# Helper to break flat text down into artificial SRT timelines to span across video length
def generate_srt_file(text, duration_sec, output_srt_path):
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
            
            def format_srt_time(seconds):
                hrs = int(seconds // 3600)
                mins = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                mils = int((seconds % 1) * 1000)
                return f"{hrs:02d}:{mins:02d}:{secs:02d},{mils:03d}"
            
            srt_start = format_srt_time(start_time)
            srt_end = format_srt_time(end_time)
            caption_text = " ".join(chunk)
            
            f.write(f"{idx + 1}\n")
            f.write(f"{srt_start} --> {srt_end}\n")
            f.write(f"{caption_text}\n\n")

# 4. Sidebar Branding Architecture
st.sidebar.markdown("## GlobalInternet.py")
st.sidebar.markdown("### AI Multi-Language Voice Translator")
st.sidebar.markdown("Built by **Gesner Deslandes**, Engineer-in-Chief")
st.sidebar.markdown("---")

# Strict Premium True-Native Voice Matrix Map (UPDATED: added Haitian Creole)
voice_options = {
    "Français (Native French Male - Henri)": "fr-FR-HenriNeural",
    "Español (Native Spanish Male - Alvaro)": "es-ES-AlvaroNeural",
    "English (Native US Male - Christopher)": "en-US-ChristopherNeural",
    "Kreyòl Ayisyen (Haitian Creole Native - Michelle)": "ht-HT-MichelleNeural"   # Added Haitian Creole voice
}
selected_voice_label = st.sidebar.selectbox("Select Native Overdub Language Layer", list(voice_options.keys()))
voice_code = voice_options[selected_voice_label]

st.title("AI Video Voice Translation Engine")
st.markdown("### Sovereign On-Demand Multimedia Linguistic Overdubbing Platform")
st.markdown("---")

col_left, col_right = st.columns([2, 1.8])

with col_left:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("<h4>Source Input Interface</h4>", unsafe_allow_html=True)
    
    input_method = st.radio(
        "Select Input Source Layer:",
        ["Upload Video from this Computer (.MP4)", "Paste Video Link (Dropbox, Google Drive)"]
    )
    
    video_ready = False
    is_link = False
    download_url = ""
    uploaded_file = None
    
    if input_method == "Paste Video Link (Dropbox, Google Drive)":
        is_link = True
        raw_url = st.text_input("Paste Video Link Here:").strip()
        
        if raw_url:
            download_url = raw_url
            video_ready = True
            
            if "dropbox.com" in raw_url:
                if "dl=0" in raw_url: download_url = raw_url.replace("dl=0", "raw=1")
                elif "dl=1" in raw_url: download_url = raw_url.replace("dl=1", "raw=1")
                elif "raw=1" not in raw_url:
                    download_url = f"{raw_url}&raw=1" if "?" in raw_url else f"{raw_url}?raw=1"
            
            elif "drive.google.com" in raw_url:
                file_id = ""
                if "/file/d/" in raw_url: file_id = raw_url.split("/file/d/")[1].split("/")[0]
                elif "id=" in raw_url: file_id = raw_url.split("id=")[1].split("&")[0]
                if file_id: download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            
            try: st.video(raw_url)
            except Exception: st.info("Link armed for mixed-audio background operations.")
    else:
        uploaded_file = st.file_uploader("Choose a video file:", type=["mp4", "mov", "mkv"])
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
            st.error("Error: Input file target path missing.")
        elif "GROQ_API_KEY" not in st.secrets:
            st.error("Missing Integration Token: Place your 'GROQ_API_KEY' inside the Secrets drawer.")
        else:
            st.markdown('<div class="status-box">', unsafe_allow_html=True)
            st.markdown("<h5>System Pipeline Progress Status</h5>", unsafe_allow_html=True)
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            try:
                # Flush workspace files
                for f_tmp in ["video.mp4", "extracted_audio.mp3", "translated_voice.mp3", "subtitles.srt", "final_output.mp4"]:
                    if os.path.exists(f_tmp): os.remove(f_tmp)
                
                # STEP 1: Download / Stream Video Content
                if is_link:
                    status_text.text("Streaming original file bytes matrix from cloud path...")
                    progress_bar.progress(15)
                    response = requests.get(download_url, stream=True)
                    response.raise_for_status()
                    with open("video.mp4", "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
                else:
                    status_text.text("Ingesting video data layers...")
                    progress_bar.progress(15)
                    with open("video.mp4", "wb") as f: f.write(uploaded_file.getbuffer())
                
                # STEP 2: Read Total Video Duration Parameter using ffprobe
                duration_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", "video.mp4"]
                duration_result = subprocess.run(duration_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                try:
                    video_duration = float(duration_result.stdout.decode('utf-8').strip())
                except:
                    video_duration = 30.0
                
                # STEP 3: Separate Sound Layer
                status_text.text("Extracting original sound parameters...")
                progress_bar.progress(30)
                subprocess.run([
                    "ffmpeg", "-i", "video.mp4", "-vn", 
                    "-acodec", "libmp3lame", "-q:a", "2", "extracted_audio.mp3", "-y"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # STEP 4: Groq Cloud Whisper API Translation Routing
                status_text.text("AI Engine reading language tracks...")
                progress_bar.progress(50)
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                
                with open("extracted_audio.mp3", "rb") as audio_file:
                    raw_translation = client.audio.translations.create(
                        file=("extracted_audio.mp3", audio_file.read()),
                        model="whisper-large-v3",
                        response_format="text"
                    )
                
                base_text = str(raw_translation).strip()
                
                # STEP 4b: Cognitive Native Localization Engine Layer (UPDATED for Haitian Creole)
                status_text.text("Refining text into true, natural native speaker phrasing...")
                
                # Determine target language instruction based on selected voice
                if "fr-FR" in voice_code:
                    target_lang_instruction = "natural, idiomatic, flowing French as spoken by a native Parisian male speaker"
                elif "es-ES" in voice_code:
                    target_lang_instruction = "natural, idiomatic, flowing Spanish as spoken by a native male speaker"
                elif "ht-HT" in voice_code:   # Haitian Creole
                    target_lang_instruction = "natural, idiomatic, flowing Haitian Creole (Kreyòl Ayisyen) as spoken by a native speaker"
                else:  # English
                    target_lang_instruction = "natural, idiomatic conversational US English"

                system_prompt = f"""
                You are an expert voiceover localizer. Your job is to take raw, literal text translations and rewrite them into fluid, high-impact verbal prose.
                Target Style: Rewrite the text into {target_lang_instruction}.
                Rules:
                - Maintain the exact original core meaning.
                - Eliminate stiff textbook grammar, literal translations, and awkward structures.
                - Optimize for spoken vocal delivery (make it sound smooth when read aloud).
                - Return ONLY the final polished text. Do not include introductions, explanations, or quotes.
                """
                
                localization_response = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": base_text}
                    ],
                    temperature=0.3
                )
                
                detected_text = localization_response.choices[0].message.content.strip()
                st.info(f"Polished Native Expression Map: \"{detected_text}\"")
                
                # STEP 5: Generate True Native Speech Output (Haitian voice included)
                status_text.text("Synthesizing true native voice frequencies...")
                progress_bar.progress(70)
                output_audio = "translated_voice.mp3"
                asyncio.run(generate_male_voice(detected_text, output_audio, voice_code))
                
                # STEP 6: Write Synchronized Captions Track
                status_text.text("Compiling text caption tracks to match video pacing...")
                generate_srt_file(detected_text, video_duration, "subtitles.srt")
                
                # STEP 7: Multiplex Sound Overlays and Burn Captions via Advanced FFmpeg Audio Graph Filters
                status_text.text("Mixing audio layers (Background + AI Overdub) and burning captions...")
                progress_bar.progress(85)
                
                final_video_output = "final_output.mp4"
                
                subprocess.run([
                    "ffmpeg", "-i", "video.mp4", "-i", "translated_voice.mp3",
                    "-filter_complex", "[0:a]volume=0.15[bg];[1:a]volume=1.8[ai];[bg][ai]amix=inputs=2:duration=first",
                    "-vf", "subtitles=subtitles.srt", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", final_video_output, "-y"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Cleanup workspace nodes safely
                for f_cleanup in ["video.mp4", "extracted_audio.mp3", "translated_voice.mp3", "subtitles.srt"]:
                    if os.path.exists(f_cleanup): os.remove(f_cleanup)
                
                progress_bar.progress(100)
                status_text.text("All Systems Harmonized! Video Production Compiled.")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.success("Successfully Compiled Combined Studio Output Layer:")
                st.markdown("#### Translated Media Output Box")
                
                with open(final_video_output, "rb") as f:
                    st.video(f.read(), format="video/mp4")
                    
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f"Pipeline Interrupted: {str(e)}")
                st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# 5. Architecture Global Footer
st.markdown(
    """
    <div class="footer-white-right">
        Built by Gesner Deslandes, Engineer-in-Chief at GlobalInternet.py | Advanced Cognitive Systems Integration.
    </div>
    """,
    unsafe_allow_html=True
)
