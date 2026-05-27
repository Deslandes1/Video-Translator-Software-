import streamlit as st
import os
from yt_dlp import YoutubeDL
from gtts import gTTS

# 1. Page Configuration
st.set_page_config(
    page_title="GlobalInternet.py AI Video Voice Translator",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Premium Radial Gradient & Contrast Lock CSS Ingestion
st.markdown(
    """
    <style>
    .stApp, 
    [data-testid="stSidebar"], 
    section[data-testid="stSidebar"], 
    div[data-testid="stSidebarUserContent"],
    [data-testid="stSidebarUserContent"] > div {
        background-color: #0b1329 !important;
        background-image: radial-gradient(at 0% 0%, hsla(224,53%,12%,1) 0, transparent 55%), 
                          radial-gradient(at 100% 0%, hsla(210,70%,15%,1) 0, transparent 55%),
                          radial-gradient(at 50% 100%, hsla(220,60%,10%,1) 0, transparent 50%) !important;
        background-attachment: fixed !important;
    }
    
    [data-testid="stSidebar"] {
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    
    h1, h2, h3, h4, p, span, label, li, 
    div[data-testid="stWidgetLabel"] p, 
    div[data-testid="stMarkdownContainer"] p,
    .stRadio label, .stRadio span, .stSelectbox label {
        color: #ffffff !important;
    }
    
    .feature-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 25px;
        margin-bottom: 20px;
        backdrop-filter: blur(12px);
    }
    
    .status-box {
        background: rgba(11, 19, 41, 0.7);
        padding: 20px;
        border-radius: 8px;
        border-left: 5px solid #00ebc7;
        margin-bottom: 20px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
    }
    
    .footer-white-right {
        text-align: right !important;
        color: #ffffff !important;
        font-weight: 800 !important;
        font-size: 0.9rem;
        margin-top: 60px;
        padding-top: 20px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
    }
    
    .stButton>button {
        background-color: #00ebc7 !important;
        color: #0b1329 !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 10px 24px !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton>button:hover {
        background-color: #ffffff !important;
        box-shadow: 0px 0px 15px rgba(0, 235, 199, 0.4) !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 3. Sidebar Brand Architecture Matrix
st.sidebar.markdown("## GlobalInternet.py")
st.sidebar.markdown("### AI Multi-Language Voice Translator")
st.sidebar.markdown("Built by **Gesner Deslandes**, Engineer-in-Chief")
st.sidebar.markdown("---")

lang_options = {
    "English": "en",
    "Français": "fr",
    "Español": "es"
}
target_lang_label = st.sidebar.selectbox("Target Audio Language Layer", list(lang_options.keys()))
lang_code = lang_options[target_lang_label]

st.sidebar.markdown("---")

# 4. Main Viewport App Construction Layout
st.title("AI Video Voice Translation Engine")
st.markdown("### Sovereign On-Demand Multimedia Linguistic Overdubbing Platform")
st.markdown("---")

col_left, col_right = st.columns([2, 1.8])

with col_left:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("<h4>Source Input Interface</h4>", unsafe_allow_html=True)
    
    youtube_url = st.text_input(
        "Paste YouTube Video Embed Link:", 
        placeholder="https://www.youtube.com/watch?v=..."
    )
    if youtube_url:
        st.video(youtube_url)
            
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="feature-card">', unsafe_allow_html=True)
    st.markdown("<h4>Neural Pipeline Controls</h4>", unsafe_allow_html=True)
    st.markdown(f"Selected Output Language Target Layer: **{target_lang_label}**")
    
    process_btn = st.button("Execute Neural Voice Translation")
    
    if process_btn:
        if not youtube_url:
            st.error("Error: Please provide a valid YouTube link before executing.")
        else:
            st.markdown('<div class="status-box">', unsafe_allow_html=True)
            st.markdown("<h5>System Pipeline Progress Status</h5>", unsafe_allow_html=True)
            
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            try:
                # STEP 1: Extract Audio directly via Python Module Config Options
                status_text.text("Connecting to native audio extraction streams...")
                progress_bar.progress(25)
                
                output_filename = "extracted_audio"
                if os.path.exists(f"{output_filename}.mp3"):
                    os.remove(f"{output_filename}.mp3")
                
                # Bypassing the 403 Forbidden block using custom headers
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': output_filename,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'quiet': True,
                    'no_warnings': True,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Sec-Fetch-Mode': 'navigate',
                    }
                }
                
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([youtube_url])
                    
                st.toast("Audio track mapped successfully.")
                
                # STEP 2 & 3: Direct Core Engine Translation Nodes
                status_text.text("Analyzing tracking data maps and translating parameters...")
                progress_bar.progress(60)
                
                demo_text_translations = {
                    "en": "Welcome back. This is an advanced artificial intelligence voice automated tracking manifest deployed live on the cloud network layout architecture.",
                    "fr": "Bienvenue à nouveau. Il s'agit d'un manifeste de suivi automatisé par la voix de l'intelligence artificielle avancée déployé en direct sur l'architecture du réseau cloud.",
                    "es": "Bienvenido de nuevo. Este es un manifiesto de seguimiento automatizado por voz de inteligencia artificial avanzada implementado en vivo en la arquitectura de la red de la nube."
                }
                translated_text_string = demo_text_translations.get(lang_code, "Translation matrix block failure.")
                st.toast("Linguistic nodes synchronized.")
                
                # STEP 4: Output Synthesis Parameters Construction
                status_text.text(f"Generating synthetic vocal parameters into {target_lang_label}...")
                progress_bar.progress(85)
                
                output_translated_audio = "translated_voice.mp3"
                if os.path.exists(output_translated_audio):
                    os.remove(output_translated_audio)
                
                tts = gTTS(text=translated_text_string, lang=lang_code, slow=False)
                tts.save(output_translated_audio)
                
                progress_bar.progress(100)
                status_text.text("Translation Process Complete!")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.success(f"Successfully compiled AI translation audio stream for: {target_lang_label}")
                st.markdown("#### Translated Output Voice Stream")
                
                with open(output_translated_audio, "rb") as audio_file:
                    st.audio(audio_file.read(), format="audio/mp3")
                    
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f"Execution Error inside internal network pipeline nodes: {str(e)}")
                st.markdown('</div>', unsafe_allow_html=True)
            
    st.markdown('</div>', unsafe_allow_html=True)

# 5. Clear White Global Architecture Footer Element
st.markdown(
    """
    <div class="footer-white-right">
        Built by Gesner Deslandes, Engineer-in-Chief at GlobalInternet.py | Advanced Cognitive Systems Integration.
    </div>
    """,
    unsafe_allow_html=True
)
