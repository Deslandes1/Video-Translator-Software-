import streamlit as st
import os
import subprocess
import requests
import asyncio
import re
from groq import Groq
import edge_tts

# 1. Page Configuration
st.set_page_config(
    page_title="GlobalInternet.py AI Video Voice Translator",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Premium Styling
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

# 3. Async TTS with fallback
async def generate_male_voice(text, output_path, voice_name, fallback_voice="fr-FR-HenriNeural"):
    try:
        communicate = edge_tts.Communicate(text, voice_name)
        await communicate.save(output_path)
        if os.path.getsize(output_path) == 0:
            raise Exception("Empty audio file")
        return True
    except Exception as e:
        st.warning(f"Primary voice '{voice_name}' failed: {str(e)}. Falling back to {fallback_voice}.")
        try:
            communicate = edge_tts.Communicate(text, fallback_voice)
            await communicate.save(output_path)
            if os.path.getsize(output_path) == 0:
                raise Exception("Fallback audio empty")
            return True
        except Exception as e2:
            st.error(f"Fallback voice also failed: {str(e2)}")
            return False

def get_duration(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        return float(result.stdout.decode('utf-8').strip())
    except:
        return 0.0

def extend_video_with_last_frame(original_video, output_video, target_duration):
    orig_dur = get_duration(original_video)
    if orig_dur >= target_duration:
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

def clean_repetitions(text):
    """Remove repeated identical phrases (like 'al-musta'khdim' repeated many times)."""
    # If text is too long and has a repeating pattern, truncate after 200 words
    words = text.split()
    if len(words) > 400:
        # Check for repetitive word at the end
        last_word = words[-1] if words else ""
        # If the same word appears more than 5 times in the last 10 words, truncate
        if words[-10:] and len(set(words[-10:])) < 3:
            # Find first occurrence of the repetition
            unique_phrases = []
            for w in words:
                if w not in unique_phrases or len(unique_phrases) > 50:
                    break
                unique_phrases.append(w)
            return " ".join(unique_phrases)
    return text

# 4. Sidebar with expanded language options
st.sidebar.markdown("## GlobalInternet.py")
st.sidebar.markdown("### AI Multi-Language Voice Translator")
st.sidebar.markdown("Built by **Gesner Deslandes**, Engineer-in-Chief")
st.sidebar.markdown("---")

voice_options = {
    "Français (Native French Male - Henri)": "fr-FR-HenriNeural",
    "Español (Native Spanish Male - Alvaro)": "es-ES-AlvaroNeural",
    "English (Native US Male - Christopher)": "en-US-ChristopherNeural",
    "Kreyòl Ayisyen (Haitian Creole Native - Michelle)": "ht-HT-MichelleNeural",
    "中文 (Chinese Mandarin Male - Yunxi)": "zh-CN-YunxiNeural",
    "العربية (Arabic Male - Hamed)": "ar-SA-HamedNeural",
    "Português (Brazilian Portuguese Male - Antonio)": "pt-BR-AntonioNeural"
}
selected_voice_label = st.sidebar.selectbox("Select Native Overdub Language Layer", list(voice_options.keys()))
voice_code = voice_options[selected_voice_label]

st.title("AI Video Voice Translation Engine")
st.markdown("### On-Demand Multimedia Linguistic Overdubbing Platform")
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
                if "dl=0" in raw_url:
                    download_url = raw_url.replace("dl=0", "raw=1")
                elif "dl=1" in raw_url:
                    download_url = raw_url.replace("dl=1", "raw=1")
                elif "raw=1" not in raw_url:
                    download_url = f"{raw_url}&raw=1" if "?" in raw_url else f"{raw_url}?raw=1"
            elif "drive.google.com" in raw_url:
                file_id = ""
                if "/file/d/" in raw_url:
                    file_id = raw_url.split("/file/d/")[1].split("/")[0]
                elif "id=" in raw_url:
                    file_id = raw_url.split("id=")[1].split("&")[0]
                if file_id:
                    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            try:
                st.video(raw_url)
            except Exception:
                st.info("Link armed for mixed-audio background operations.")
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
                # Cleanup
                for f in ["video.mp4", "extracted_audio.mp3", "translated_voice.mp3", "subtitles.srt", "final_output.mp4", "extended_video.mp4", "last.png"]:
                    if os.path.exists(f):
                        os.remove(f)
                
                # STEP 1: Download video
                if is_link:
                    status_text.text("Streaming original file...")
                    progress_bar.progress(15)
                    response = requests.get(download_url, stream=True)
                    response.raise_for_status()
                    with open("video.mp4", "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                else:
                    status_text.text("Ingesting video data...")
                    progress_bar.progress(15)
                    with open("video.mp4", "wb") as f:
                        f.write(uploaded_file.getbuffer())
                
                # STEP 2: Get video duration
                video_duration = get_duration("video.mp4")
                if video_duration <= 0:
                    video_duration = 30.0
                
                # STEP 3: Extract audio for transcription
                status_text.text("Extracting original audio...")
                progress_bar.progress(30)
                subprocess.run([
                    "ffmpeg", "-i", "video.mp4", "-vn",
                    "-acodec", "libmp3lame", "-q:a", "2", "extracted_audio.mp3", "-y"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # STEP 4: Groq Whisper Translation
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
                
                # STEP 4b: Enhanced Localization for each language
                status_text.text("Refining text into natural native phrasing...")
                
                # Language-specific instructions
                if "zh-CN" in voice_code:
                    target_lang_instruction = "natural, idiomatic, flowing Mandarin Chinese (Simplified). Output in Simplified Chinese characters (汉字), no pinyin, no transliteration. Keep the tone conversational and natural."
                elif "ar-SA" in voice_code:
                    target_lang_instruction = "natural, idiomatic, flowing Modern Standard Arabic. Output in Arabic script (العربية), no transliteration. Use correct Arabic grammar and avoid repetition. Keep the text concise (maximum 200 words)."
                elif "pt-BR" in voice_code:
                    target_lang_instruction = "natural, idiomatic, flowing Brazilian Portuguese. Output in Portuguese, avoid English words. Keep the text natural for voiceover."
                elif "fr-FR" in voice_code:
                    target_lang_instruction = "natural, idiomatic, flowing French as spoken by a native Parisian male speaker"
                elif "es-ES" in voice_code:
                    target_lang_instruction = "natural, idiomatic, flowing Spanish as spoken by a native male speaker"
                elif "ht-HT" in voice_code:
                    target_lang_instruction = "natural, idiomatic, flowing Haitian Creole (Kreyòl Ayisyen) as spoken by a native speaker"
                else:
                    target_lang_instruction = "natural, idiomatic conversational US English"

                system_prompt = f"""
                You are an expert voiceover localizer. Take the raw translated text and rewrite it into fluid, high-impact verbal prose.
                Target Style: {target_lang_instruction}
                Rules:
                - Maintain exact original core meaning.
                - Eliminate stiff grammar, literal translations, awkward structures.
                - Optimize for spoken vocal delivery (smooth, natural, no repetition).
                - Do NOT repeat words or phrases unnecessarily.
                - Keep the output length reasonable (max 250 words).
                - Return ONLY the polished text. No extras, no explanations.
                - IMPORTANT: For Arabic, output in Arabic script (عربي). For Chinese, output in Simplified Chinese characters. For Portuguese, output in Portuguese.
                """
                
                # Increase max_tokens and add repetition_penalty
                localization_response = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": base_text}
                    ],
                    temperature=0.2,           # lower temperature for more deterministic output
                    max_tokens=800,            # enough for long translations
                    frequency_penalty=0.5,     # penalize repetition
                    presence_penalty=0.5,
                )
                detected_text = localization_response.choices[0].message.content.strip()
                
                # Post-process to remove any potential repetitions
                detected_text = clean_repetitions(detected_text)
                
                st.info(f"Polished Native Expression Map: \"{detected_text[:500]}...\" (truncated)")
                
                # STEP 5: Generate TTS with appropriate fallback
                status_text.text("Synthesizing true native voice frequencies...")
                progress_bar.progress(70)
                output_audio = "translated_voice.mp3"
                
                if "fr" in voice_code:
                    fallback_voice = "fr-FR-HenriNeural"
                elif "es" in voice_code:
                    fallback_voice = "es-ES-AlvaroNeural"
                elif "ht" in voice_code:
                    fallback_voice = "fr-FR-HenriNeural"
                elif "zh" in voice_code:
                    fallback_voice = "en-US-ChristopherNeural"
                elif "ar" in voice_code:
                    fallback_voice = "en-US-ChristopherNeural"
                elif "pt" in voice_code:
                    fallback_voice = "en-US-ChristopherNeural"
                else:
                    fallback_voice = "en-US-ChristopherNeural"
                
                tts_success = asyncio.run(generate_male_voice(detected_text, output_audio, voice_code, fallback_voice))
                if not tts_success:
                    raise Exception("TTS generation failed.")
                
                # STEP 6: Check durations and extend video if needed
                status_text.text("Adjusting video length to match voiceover...")
                audio_duration = get_duration(output_audio)
                if audio_duration > video_duration:
                    st.warning(f"Voiceover duration ({audio_duration:.1f}s) longer than original video ({video_duration:.1f}s). Extending video with frozen last frame.")
                    working_video = extend_video_with_last_frame("video.mp4", "extended_video.mp4", audio_duration)
                else:
                    working_video = "video.mp4"
                
                # STEP 7: Generate subtitles (use the longer duration)
                final_duration = max(video_duration, audio_duration)
                generate_srt_file(detected_text, final_duration, "subtitles.srt")
                
                # STEP 8: Mix audio and burn subtitles
                status_text.text("Mixing audio layers and burning captions...")
                progress_bar.progress(85)
                final_video_output = "final_output.mp4"
                
                cmd = [
                    "ffmpeg", "-i", working_video, "-i", output_audio,
                    "-filter_complex", 
                    "[0:a]volume=0.2[a1];[1:a]volume=1.5[a2];[a1][a2]amix=inputs=2:duration=longest[a]",
                    "-map", "0:v", "-map", "[a]",
                    "-vf", "subtitles=subtitles.srt",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest",
                    final_video_output, "-y"
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    st.error(f"FFmpeg error: {result.stderr}")
                    raise Exception("FFmpeg mixing failed.")
                
                # Cleanup
                for f_cleanup in ["video.mp4", "extracted_audio.mp3", "translated_voice.mp3", "subtitles.srt", "extended_video.mp4", "last.png"]:
                    if os.path.exists(f_cleanup):
                        os.remove(f_cleanup)
                
                progress_bar.progress(100)
                status_text.text("All Systems Harmonized! Video Production Compiled.")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.success("Successfully Compiled Combined Studio Output Layer:")
                st.markdown("#### Translated Media Output Box")
                
                if os.path.exists(final_video_output) and os.path.getsize(final_video_output) > 0:
                    with open(final_video_output, "rb") as f:
                        st.video(f.read(), format="video/mp4")
                else:
                    st.error("Final video file was not created correctly.")
                    
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
