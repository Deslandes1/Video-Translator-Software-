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

# 2. Premium Design Framing Ingestion
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

# 3. Async Wrapper for Premium Male Voice Generation
async def generate_male_voice(text, output_path, voice_name):
    communicate = edge_tts.Communicate(text, voice_name)
    await communicate.save(output_path)

# 4. Sidebar Branding Architecture
st.sidebar.markdown("## GlobalInternet.py")
st.sidebar.markdown("### AI Multi-Language Voice Translator")
st.sidebar.markdown("Built by **Gesner Deslandes**, Engineer-in-Chief")
st.sidebar.markdown("---")

# Premium Male AI Voices Matrix (Free Edge Neural Engine)
voice_options = {
    "Male (English - Christopher)": "en-US-ChristopherNeural",
    "Male (English - Eric)": "en-US-EricNeural",
    "Male (Français - Henri)": "fr-FR-HenriNeural",
    "Male (Español - Alvaro)": "es-ES-AlvaroNeural"
}
selected_voice_label = st.sidebar.selectbox("Select Male AI Voice Layer", list(voice_options.keys()))
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
            except Exception: st.info("Link armed for background sync execution.")
    else:
        uploaded_file = st.file_uploader("Choose a video file:", type=["mp4", "mov", "mkv"])
        if uploaded_file is not None:
            st.video(uploaded_file)
            video_ready = True
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("<h4>Neural Pipeline Controls</h4>", unsafe_allow_html=True)
    
    process_btn = st.button("Execute Video & Voice Sync Overdub")
    
    if process_btn:
        if not video_ready:
            st.error("Error: Input video missing.")
        elif "GROQ_API_KEY" not in st.secrets:
            st.error("Missing Integration Token: Place your 'GROQ_API_KEY' inside the Secrets drawer.")
        else:
            st.markdown('<div class="status-box">', unsafe_allow_html=True)
            st.markdown("<h5>System Pipeline Progress Status</h5>", unsafe_allow_html=True)
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            try:
                # Flush the clean build workspace
                for f_tmp in ["video.mp4", "extracted_audio.mp3", "translated_voice.mp3", "final_output.mp4"]:
                    if os.path.exists(f_tmp): os.remove(f_tmp)
                
                # STEP 1: Fetch Target Asset
                if is_link:
                    status_text.text("Streaming original raw video files from storage network...")
                    progress_bar.progress(20)
                    response = requests.get(download_url, stream=True)
                    response.raise_for_status()
                    with open("video.mp4", "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
                else:
                    status_text.text("Ingesting original local file configurations...")
                    progress_bar.progress(20)
                    with open("video.mp4", "wb") as f: f.write(uploaded_file.getbuffer())
                
                # STEP 2: Separate Audio Tracking Layer
                status_text.text("Isolating video sound maps for AI compilation...")
                subprocess.run([
                    "ffmpeg", "-i", "video.mp4", "-vn", 
                    "-acodec", "libmp3lame", "-q:a", "2", "extracted_audio.mp3", "-y"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # STEP 3: Groq Cloud Whisper Audio Processing Layer
                status_text.text("Connecting to Cloud Whisper AI Transcription Array...")
                progress_bar.progress(50)
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                with open("extracted_audio.mp3", "rb") as audio_file:
                    translation_data = client.audio.translations.create(
                        file=("extracted_audio.mp3", audio_file.read()),
                        model="whisper-large-v3",
                        response_format="text"
                    )
                
                detected_text = str(translation_data).strip()
                st.info(f"AI Transcription Result: \"{detected_text}\"")
                
                # STEP 4: Generate Premium Male AI Voice
                status_text.text("Synthesizing voice tracks using Premium Male AI Vocal Node...")
                progress_bar.progress(75)
                
                output_audio = "translated_voice.mp3"
                # Call Microsoft Edge Engine inside async loop
                asyncio.run(generate_male_voice(detected_text, output_audio, voice_code))
                
                # STEP 5: Stitch New Audio Over Original Video Frame Pipeline Matrix
                status_text.text("Merging the new male AI translation over the video layout frame...")
                progress_bar.progress(90)
                
                final_video_output = "final_output.mp4"
                subprocess.run([
                    "ffmpeg", "-i", "video.mp4", "-i", "translated_voice.mp3",
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                    "-shortest", final_video_output, "-y"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Clean workspace temporary variables
                for f_cleanup in ["video.mp4", "extracted_audio.mp3", "translated_voice.mp3"]:
                    if os.path.exists(f_cleanup): os.remove(f_cleanup)
                
                progress_bar.progress(100)
                status_text.text("All Operations Complete! Final Build Rendered Successfully.")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.success("Successfully Compiled Synchronized AI Video Translation Engine Output:")
                st.markdown("#### Translated Synchronized Output Media Player")
                
                # Render the final combined video track file directly on screen
                with open(final_video_output, "rb") as f:
                    st.video(f.read(), format="video/mp4")
                    
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f"Pipeline Interrupted: {str(e)}")
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
