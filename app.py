import os
import subprocess
import ffmpeg_static
import streamlit as st

# --- FFmpeg Configuration ---
# ffmpeg-static provides a reliable, self-contained binary path.
# This prevents the need for heavy 'apt-get' installations in Streamlit Cloud.
FFMPEG_PATH = ffmpeg_static.get_ffmpeg_exe()
FFPROBE_PATH = ffmpeg_static.get_ffprobe_exe()

# Configure environment for libraries (like imageio or others) that look for FFmpeg
os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG_PATH

def check_ffmpeg():
    """Verify that FFmpeg is accessible and returns a version string."""
    try:
        result = subprocess.run([FFMPEG_PATH, "-version"], capture_output=True, text=True, check=True)
        return True
    except Exception as e:
        return False

# --- App Logic ---
if not check_ffmpeg():
    st.error("❌ FFmpeg is not properly configured. Please check your dependencies.")
else:
    st.success("✅ FFmpeg is ready to use for video processing!")

# You can now proceed with your video translator logic below:
# st.title("Video Translator Engine")
# ...
