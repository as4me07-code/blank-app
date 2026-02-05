import csv
import os
import tempfile
import time
from datetime import datetime

import streamlit as st

CSV_FILE = "mental_health_logs.csv"


def initialize_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Mood", "Tags", "Notes"])


def transcribe_audio(uploaded_file) -> str:
    """Transcribe an uploaded audio file or WebRTC audio using SpeechRecognition.

    Accepts file-like object from Streamlit `file_uploader` or audio bytes from WebRTC.
    """
    try:
        import speech_recognition as sr
    except Exception:
        return "[speech_recognition not available — install it in your environment]"

    # Handle both file uploads and byte arrays from WebRTC
    if hasattr(uploaded_file, 'name'):
        # File uploader object
        suffix = os.path.splitext(uploaded_file.name)[1].lower()
        audio_bytes = uploaded_file.read()
    else:
        # Byte array from WebRTC
        suffix = ".wav"
        audio_bytes = uploaded_file

    # Write to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_in:
        temp_in.write(audio_bytes)
        temp_in_path = temp_in.name

    # Ensure we have a wav file for SpeechRecognition
    wav_path = temp_in_path
    if suffix != ".wav":
        try:
            from pydub import AudioSegment

            audio = AudioSegment.from_file(temp_in_path)
            wav_path = temp_in_path + ".wav"
            audio.export(wav_path, format="wav")
        except Exception:
            return "[Failed to convert audio — ensure pydub and ffmpeg are installed]"

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio)
            return text
    except sr.UnknownValueError:
        return "[Could not understand audio]"
    except sr.RequestError:
        return "[Speech recognition service unavailable — network required]"
    except Exception as e:
        return f"[Transcription error: {e}]"
    finally:
        try:
            os.remove(temp_in_path)
        except Exception:
            pass
        if wav_path != temp_in_path:
            try:
                os.remove(wav_path)
            except Exception:
                pass


def normalize_tags(tags_str: str) -> str:
    if not tags_str:
        return ""
    parts = [t.strip() for t in tags_str.split(',') if t.strip()]
    normalized = []
    for p in parts:
        if not p.startswith('#'):
            p = '#' + p
        normalized.append(p)
    return ', '.join(normalized)


def save_entry(mood: str, tags: str, notes: str):
    initialize_csv()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CSV_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, mood, tags, notes])


def load_entries():
    if not os.path.exists(CSV_FILE):
        return []
    with open(CSV_FILE, mode='r', newline='') as file:
        reader = list(csv.reader(file))
        return reader[1:]


def inject_css():
    st.markdown(
        """
        <style>
        :root{
          --bg:#E6DBEF;
          --card:#FFFFFF;
          --muted:#6B7280;
          --accent:#C8E6F5;
          --accent-2:#E8F2F0;
          --lav:#EDE7F6;
        }
        .stApp {
          background: linear-gradient(180deg, #E6DBEF, #F0E6F3);
        }
        .card {
          background: var(--card);
          border-radius: 14px;
          padding: 16px;
          box-shadow: 0 6px 18px rgba(13,38,59,0.06);
        }
        .rounded-input .stTextInput>div>input{border-radius:10px}
        .rounded-textarea textarea{border-radius:10px}
        .tag-pill{display:inline-block;background:var(--accent-2);padding:6px 10px;border-radius:999px;margin-right:6px;color:#1f2937}
        .mood-bar{height:10px;background:linear-gradient(90deg,#A7F3D0,#C7D2FE);border-radius:999px}
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(page_title='Calm Journal', layout='centered')
    inject_css()

    # Initialize session state for voice recording
    if 'voice_recorded' not in st.session_state:
        st.session_state.voice_recorded = False
    if 'recorded_audio_bytes' not in st.session_state:
        st.session_state.recorded_audio_bytes = None

    # Common stress situations library
    COMMON_STRESSORS = [
        'Work Stress',
        'Relationship Issues',
        'Financial Worry',
        'Health Concerns',
        'Sleep Deprivation',
        'Social Anxiety',
        'Deadline Pressure',
        'Family Conflict',
        'Academic Stress',
        'Burnout',
        'Grief/Loss',
        'Uncertainty'
    ]

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.title('Calm Journal')
    st.markdown('A simple, calming place to check in with yourself.')

    # Voice recording section (outside form so it can update state)
    st.subheader('Or record your voice:')
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown('🎤 Click the button to start recording. Grant microphone access when prompted.')
    
    with col2:
        if st.button('🎙️ Record Note', key='record_btn'):
            # WebRTC configuration
            rtc_configuration = RTCConfiguration(
                {"iceServers": [{"urls": ["stun:stun1.l.google.com:19302"]}]}
            )
            
            webrtc_ctx = webrtc_streamer(
                key="voice-note-recorder",
                mode="sendrecv",
                rtc_configuration=rtc_configuration,
                media_stream_constraints={"audio": True, "video": False},
                async_processing=True,
            )
            
            if webrtc_ctx.state.playing:
                st.info('🎙️ Recording in progress... Speak clearly into your microphone.')
                st.write('*The recording will process when you stop speaking. Click Stop to finish.*')

    # Show status of voice recording if completed
    if st.session_state.voice_recorded:
        st.success('✅ Voice note recorded successfully!')
        if st.button('Clear voice recording'):
            st.session_state.voice_recorded = False
            st.session_state.recorded_audio_bytes = None
            st.rerun()

    with st.form('entry_form'):
        st.subheader('How are you feeling right now?')
        st.markdown("""
        **Mood Levels:**
        - **1** 🔴 Very Sad/Overwhelmed
        - **2** 🟠 Sad/Anxious
        - **3** 🟡 Neutral/Okay
        - **4** 🟢 Good/Happy
        - **5** 🟣 Great/Joyful
        """)
        mood = st.slider('Select your mood level:', min_value=1, max_value=5, value=3, format='%d')
        st.markdown(f"<div style='margin-top:6px' class='mood-bar'></div>", unsafe_allow_html=True)

        st.subheader('What\'s causing stress? (select any that apply)')
        selected_stressors = st.multiselect('Common Stressors:', COMMON_STRESSORS, default=[])
        
        st.subheader('Add your own tags')
        custom_tags = st.text_input('Personal tags (comma separated)', placeholder='exercise, therapy, rest')
        
        # Combine stressors and custom tags
        all_tags = ', '.join(selected_stressors)
        if custom_tags:
            all_tags = (all_tags + ', ' + custom_tags) if all_tags else custom_tags

        st.subheader('Your Notes')
        notes = st.text_area('Type your thoughts and feelings here...', placeholder='Type anything you need to offload...', height=120)
        
        # Show file upload option as well
        st.write('**Or upload an audio file:**')
        uploaded_audio = st.file_uploader('Upload an audio note (wav, mp3, m4a, ogg)', type=['wav', 'mp3', 'm4a', 'ogg'])
        
        if uploaded_audio is not None:
            st.info('📝 Audio file selected. Click Save to transcribe and add it to your notes.')

        submitted = st.form_submit_button('Save')
        if submitted:
            tags = normalize_tags(all_tags)
            
            # Transcribe audio if uploaded
            transcribed_text = ""
            if uploaded_audio is not None:
                with st.spinner('🎤 Transcribing audio...'):
                    transcribed_text = transcribe_audio(uploaded_audio)
            elif st.session_state.voice_recorded and st.session_state.recorded_audio_bytes:
                with st.spinner('🎤 Transcribing voice note...'):
                    transcribed_text = transcribe_audio(st.session_state.recorded_audio_bytes)
            
            # Combine typed notes with transcribed audio
            final_notes = notes
            if transcribed_text and transcribed_text.startswith('['):
                # Error message from transcription
                st.warning(f"Audio transcription issue: {transcribed_text}")
            elif transcribed_text:
                if notes:
                    final_notes = f"{notes}\n\n[Voice note]: {transcribed_text}"
                else:
                    final_notes = transcribed_text

            if not final_notes:
                st.warning('Please add some notes (typed or voice/audio) before saving.')
            else:
                # subtle progress
                prog = st.progress(0)
                for i in range(0, 101, 20):
                    prog.progress(i)
                    time.sleep(0.06)
                save_entry(str(mood), tags, final_notes)
                st.session_state.voice_recorded = False
                st.session_state.recorded_audio_bytes = None
                st.success('✨ Entry saved — good job taking a moment for yourself')

    st.markdown('</div>', unsafe_allow_html=True)

    # Sidebar: recent entries
    st.sidebar.title('Recent Check-ins')
    entries = load_entries()
    if entries:
        num = st.sidebar.slider('Show last N', min_value=1, max_value=min(20, len(entries)), value=min(5, len(entries)))
        for row in reversed(entries[-num:]):
            ts, mood, tags, notes = (row + [''] * 4)[:4]
            st.sidebar.markdown(f"<div class='card' style='margin-bottom:8px'><strong>{ts}</strong><br/>Mood: {mood}<br/>{tags}<div style='margin-top:6px;color:var(--muted)'>" + (notes[:120] + ('...' if len(notes) > 120 else '')) + '</div></div>', unsafe_allow_html=True)
    else:
        st.sidebar.info('No entries yet. Add your first calming check-in above.')


if __name__ == '__main__':
    main()
