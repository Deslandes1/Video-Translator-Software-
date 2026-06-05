import streamlit as st
import os
import subprocess
import requests
import shutil
import re
from gtts import gTTS

# ================== Page Config ==================
st.set_page_config(page_title="GlobalInternet.py | TikTok AI Narrator", layout="wide")

# ================== FFmpeg Setup ==================
FFMPEG_PATH = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG_PATH

def generate_voiceover(text, output_path):
    """Generates female voice audio using gTTS."""
    tts = gTTS(text=text, lang='en', slow=False)
    tts.save(output_path)
    return os.path.exists(output_path)

def merge_audio_to_video(video_path, audio_path, output_path):
    """Merges voiceover audio into the video."""
    cmd = [
        FFMPEG_PATH, "-i", video_path, "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", output_path, "-y"
    ]
    subprocess.run(cmd)
    return os.path.exists(output_path)

# ================== UI ==================
st.title("🎬 GlobalInternet.py: AI TikTok Ads Narrator")
st.markdown("### Upload your silent TikTok Ads Manager screen recording and paste your script.")

video_url = st.text_input("Paste Dropbox Video URL:", "https://www.dropbox.com/scl/fi/87a03o1alh4cq3ds5qxr6/TikTokAd.mp4?rlkey=skyjiorytjmwd7v3kb446r6xf&st=wp6rebex&dl=1")
script_text = st.text_area("Paste your script for the AI Voice:", 
    "Haitian TikTok creators, are you ready to generate real money? Unfortunately, PayPal doesn't work in Haiti, but you can change the game. By using TikTok Ads Manager, you turn your content into a business. With as little as five dollars, you can start investing in ads to reach a global market. Don't wait, start building your business center account today.")

if st.button("Generate Narrated Video"):
    if not video_url or not script_text:
        st.error("Please provide both a video URL and a script.")
    else:
        with st.spinner("Processing..."):
            # Download
            video_path = "input_video.mp4"
            r = requests.get(video_url, stream=True)
            with open(video_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Generate Audio
            audio_path = "voiceover.mp3"
            generate_voiceover(script_text, audio_path)
            
            # Merge
            final_path = "final_narrated_video.mp4"
            merge_audio_to_video(video_path, audio_path, final_path)
            
            st.success("Video ready!")
            st.video(final_path)
            with open(final_path, "rb") as f:
                st.download_button("⬇️ Download Final Video", f, "tiktok_ads_guide.mp4")
