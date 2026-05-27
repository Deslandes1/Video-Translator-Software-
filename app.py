import streamlit as st
import os
import subprocess
import requests
from gtts import gTTS
from groq import Groq

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

# 3. Sidebar Branding
st.sidebar.markdown("## GlobalInternet.py")
st.sidebar.markdown("### AI Multi-Language Voice Translator")
st.sidebar.markdown("Built by **Gesner Deslandes**, Engineer-in-Chief")
st.sidebar.markdown("---")

lang_options = {"English": "en", "Français": "fr", "Español": "es"}
target_lang_label = st.sidebar.selectbox("Target Audio Language Layer", list(lang_options.keys()))
lang_code = lang_options[target_lang_label]

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
            
            # Dropbox link translation parser
            if "dropbox.com" in raw_url:
                if "dl=0" in raw_url: download_url = raw_url.replace("dl=0", "raw=1")
                elif "dl=1" in raw_url: download_url = raw_url.replace("dl=1", "raw=1")
                elif "raw=1" not in raw_url:
                    download_url = f"{raw_url}&raw=1" if "?" in raw_url else f"{raw_url}?raw=1"
            
            # Google Drive parser
            elif "drive.google.com" in raw_url:
                file_id = ""
                if "/file/d/" in raw_url: file_id = raw_url.split("/file/d/")[1].split("/")[0]
                elif "id=" in raw_url: file_id = raw_url.split("id=")[1].split("&")[0]
                if file_id: download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            
            try: st.video(raw_url)
            except Exception: st.info("Link armed for background file processing paths.")
    else:
        uploaded_file = st.file_uploader("Choose a video file:", type=["mp4", "mov", "mkv"])
        if uploaded_file is not None:
            st.video(uploaded_file)
            video_ready = True
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("<h4>Neural Pipeline Controls</h4>", unsafe_allow_html=True)
    
    process_btn = st.button("Execute Neural Voice Translation")
    
    if process_btn:
        if not video_ready:
            st.error("Error: Input file missing.")
        # Ensure Secrets Token is set up properly
        elif "GROQ_API_KEY" not in st.secrets:
            st.error("Missing Integration Token: Please place your 'GROQ_API_KEY' inside the Streamlit Dashboard Secrets drawer.")
        else:
            st.markdown('<div class="status-box">', unsafe_allow_html=True)
            st.markdown("<h5>System Pipeline Progress Status</h5>", unsafe_allow_html=True)
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            try:
                # Cleanup workspace
                for f_tmp in ["video.mp4", "extracted_audio.mp3", "translated_voice.mp3"]:
                    if os.path.exists(f_tmp): os.remove(f_tmp)
                
                # Fetch target video asset
                if is_link:
                    status_text.text("Streaming raw file data matrix from cloud storage link...")
                    progress_bar.progress(25)
                    response = requests.get(download_url, stream=True)
                    response.raise_for_status()
                    with open("video.mp4", "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
                else:
                    status_text.text("Ingesting video data channel...")
                    progress_bar.progress(25)
                    with open("video.mp4", "wb") as f: f.write(uploaded_file.getbuffer())
                
                # Split Audio Track Using Native Core Engine Systems
                status_text.text("Isolating high-fidelity audio track layers...")
                subprocess.run([
                    "ffmpeg", "-i", "video.mp4", "-vn", 
                    "-acodec", "libmp3lame", "-q:a", "2", "extracted_audio.mp3", "-y"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                if os.path.exists("video.mp4"): os.remove("video.mp4")
                
                # Call Cloud Whisper Engine Array
                status_text.text("Connecting to Cloud Neural AI Speech Recognition...")
                progress_bar.progress(60)
                
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                with open("extracted_audio.mp3", "rb") as audio_file:
                    translation_data = client.audio.translations.create(
                        file=("extracted_audio.mp3", audio_file.read()),
                        model="whisper-large-v3",
                        response_format="text"
                    )
                
                detected_text = str(translation_data).strip()
                st.info(f"Full AI Transcription Result: \"{detected_text}\"")
                
                # Final Audio Synthesizer Output Construction
                status_text.text(f"Compiling translation speech layer ({target_lang_label})...")
                progress_bar.progress(90)
                
                output_audio = "translated_voice.mp3"
                tts = gTTS(text=detected_text, lang=lang_code, slow=False)
                tts.save(output_audio)
                
                progress_bar.progress(100)
                status_text.text("Translation Process Complete!")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.success(f"Successfully compiled AI audio stream for: {target_lang_label}")
                with open(output_audio, "rb") as f:
                    st.audio(f.read(), format="audio/mp3")
                    
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
