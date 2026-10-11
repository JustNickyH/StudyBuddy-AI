"""
StudyBuddy AI - Asisten Belajar & Tutor Interaktif Berbasis Google Gemini API
Final Project: AI Productivity and AI API Integration for Developers
"""

import os
import time
from datetime import datetime
from PIL import Image
import streamlit as st
from dotenv import load_dotenv

# Load local environment variables from .env if present
load_dotenv()

from modules.prompts import (
    TONE_PROMPTS,
    LEVEL_PROMPTS,
    SUBJECT_PROMPTS,
    build_system_instruction,
    QUIZ_SYSTEM_INSTRUCTION,
    ROADMAP_SYSTEM_INSTRUCTION,
)
from modules.gemini_client import GeminiService, SUPPORTED_MODELS, DEFAULT_MODEL
from modules.utils import (
    export_chat_to_markdown,
    export_chat_to_text,
    parse_quiz_json,
)

# -----------------------------------------------------------------------------
# Page Configuration & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="StudyBuddy AI | Tutor Belajar Cerdas",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for modern, aesthetic, student-friendly UI
st.markdown("""
<style>
    /* Global styles */
    .stApp {
        font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Header hero styling */
    .hero-container {
        background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%);
        color: #ffffff;
        padding: 1.8rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 10px 25px -5px rgba(49, 46, 129, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0;
        background: linear-gradient(90deg, #ffffff, #c7d2fe);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    
    .hero-subtitle {
        font-size: 1rem;
        color: #e0e7ff;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    }
    
    /* Parameter badges bar */
    .badge-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 0.5rem;
    }
    
    .badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.3rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        backdrop-filter: blur(8px);
        background: rgba(255, 255, 255, 0.15);
        color: #ffffff;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .badge-active {
        background: rgba(16, 185, 129, 0.25);
        border-color: rgba(52, 211, 153, 0.4);
        color: #a7f3d0;
    }
    
    /* Quick prompt starter chips */
    .stButton>button {
        border-radius: 10px;
        font-weight: 500;
        transition: all 0.2s ease-in-out;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    
    /* Metric / Stat Card */
    .stat-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }
    
    /* Quiz card */
    .quiz-box {
        background: #ffffff;
        color: #1e293b;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    
    /* Dark mode support for quiz box */
    @media (prefers-color-scheme: dark) {
        .quiz-box {
            background: #1e293b;
            color: #f8fafc;
            border-color: #334155;
        }
    }
    
    /* Pomodoro timer styling */
    .timer-display {
        font-size: 2rem;
        font-weight: 800;
        text-align: center;
        letter-spacing: 2px;
        font-family: monospace;
        color: #6366f1;
        padding: 0.5rem;
        background: rgba(99, 102, 241, 0.1);
        border-radius: 8px;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Session State Initialization
# -----------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "model",
            "content": (
                "Halo! 👋 Aku **StudyBuddy AI**, tutor dan teman belajarmu yang didukung oleh Google Gemini.\n\n"
                "Kamu bisa bertanya tentang konsep pelajaran, rumus matematika, latihan soal, bantuan debugging kode, "
                "atau meminta kuis interaktif dan roadmap belajar. Kamu juga bisa mengunggah foto soal di bawah!\n\n"
                "Mau belajar apa kita hari ini?"
            ),
            "timestamp": datetime.now().strftime("%H:%M"),
        }
    ]

if "api_key" not in st.session_state:
    st.session_state.api_key = os.environ.get("GEMINI_API_KEY", "")

if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None

if "quiz_user_answers" not in st.session_state:
    st.session_state.quiz_user_answers = {}

if "quiz_submitted" not in st.session_state:
    st.session_state.quiz_submitted = False

if "roadmap_result" not in st.session_state:
    st.session_state.roadmap_result = ""

if "timer_seconds" not in st.session_state:
    st.session_state.timer_seconds = 25 * 60  # Default 25 min Pomodoro


# -----------------------------------------------------------------------------
# Sidebar: Parameter Kreatif & Konfigurasi Bot
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://api.iconify.design/twemoji:graduation-cap.svg", width=50)
    st.title("Pengaturan Tutor")
    st.caption("AI Final Project: Custom Education Bot")

    # --- 1. Konfigurasi API Key ---
    with st.expander("🔑 Konfigurasi Gemini API", expanded=not bool(st.session_state.api_key)):
        api_key_input = st.text_input(
            "Gemini API Key",
            value=st.session_state.api_key,
            type="password",
            help="Dapatkan API Key gratis di Google AI Studio (https://aistudio.google.com/app/apikey). Jika kosong, bot otomatis berjalan dalam Mode Simulasi Edukasi.",
        )
        if api_key_input != st.session_state.api_key:
            st.session_state.api_key = api_key_input

        selected_model = st.selectbox(
            "Model Gemini",
            options=SUPPORTED_MODELS,
            index=0,
            help="Pilih model Gemini LLM yang akan digunakan.",
        )

        test_col1, test_col2 = st.columns([1, 1])
        with test_col1:
            if st.button("🧪 Tes Koneksi", use_container_width=True):
                client = GeminiService(api_key=st.session_state.api_key, model_name=selected_model)
                res = client.test_connection()
                if res["success"]:
                    st.success("✅ Koneksi Sukses!")
                else:
                    st.error(f"❌ {res['message']}")
        with test_col2:
            if st.session_state.api_key:
                st.markdown("<span style='color:#10b981; font-weight:600;'>🟢 Live API</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='color:#f59e0b; font-weight:600;'>🟡 Mode Demo</span>", unsafe_allow_html=True)

    st.markdown("---")

    # --- 2. Parameter Kreatif: Persona & Gaya Bahasa ---
    st.subheader("🎭 Parameter Kreatif")

    selected_tone = st.selectbox(
        "Gaya Bahasa (Tone Persona)",
        options=list(TONE_PROMPTS.keys()),
        index=0,
        help="Mengubah cara bot berbicara, mulai dari gaya teman sebaya hingga metode reflektif Socrates.",
    )

    selected_level = st.selectbox(
        "Jenjang Pendidikan (Target Level)",
        options=list(LEVEL_PROMPTS.keys()),
        index=1,
        help="Menyesuaikan kompleksitas penjelasan dan pemilihan kata sesuai tingkatan siswa.",
    )

    selected_subject = st.selectbox(
        "Spesialisasi Subjek",
        options=list(SUBJECT_PROMPTS.keys()),
        index=5,
        help="Memfokuskan pengetahuan dan aturan pemformatan (misal LaTeX untuk STEM, syntax highlighting untuk coding).",
    )

    # --- 3. Hyperparameter Model ---
    with st.expander("⚙️ Hyperparameter Model AI", expanded=False):
        temperature = st.slider(
            "Temperature (Kreativitas)",
            min_value=0.0,
            max_value=2.0,
            value=0.7,
            step=0.05,
            help="Nilai lebih rendah membuat jawaban lebih pasti dan presisi; nilai lebih tinggi membuat respon lebih variatif.",
        )
        top_p = st.slider(
            "Top-P (Nucleus Sampling)",
            min_value=0.1,
            max_value=1.0,
            value=0.95,
            step=0.05,
        )
        max_tokens = st.slider(
            "Max Output Tokens",
            min_value=256,
            max_value=4096,
            value=2048,
            step=128,
        )

    st.markdown("---")

    # --- 4. Fitur Ekstra: Pomodoro Study Timer ---
    with st.expander("⏱️ Pomodoro Study Timer", expanded=False):
        mins = st.session_state.timer_seconds // 60
        secs = st.session_state.timer_seconds % 60
        st.markdown(f"<div class='timer-display'>{mins:02d}:{secs:02d}</div>", unsafe_allow_html=True)

        pomo_col1, pomo_col2 = st.columns(2)
        with pomo_col1:
            if st.button("25m Fokus", use_container_width=True):
                st.session_state.timer_seconds = 25 * 60
                st.rerun()
        with pomo_col2:
            if st.button("5m Istirahat", use_container_width=True):
                st.session_state.timer_seconds = 5 * 60
                st.rerun()

    # --- 5. Export & Kelola Chat ---
    st.subheader("💾 Riwayat & Ekspor")
    chat_exp_col1, chat_exp_col2 = st.columns(2)

    session_metadata = {
        "model": selected_model,
        "tone": selected_tone,
        "level": selected_level,
        "subject": selected_subject,
        "temperature": temperature,
    }

    with chat_exp_col1:
        md_text = export_chat_to_markdown(st.session_state.messages, session_metadata)
        st.download_button(
            label="📥 Markdown",
            data=md_text,
            file_name=f"catatan_belajar_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with chat_exp_col2:
        txt_text = export_chat_to_text(st.session_state.messages)
        st.download_button(
            label="📄 Plain TXT",
            data=txt_text,
            file_name=f"catatan_belajar_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    if st.button("🗑️ Bersihkan Obrolan", use_container_width=True):
        st.session_state.messages = [
            {
                "role": "model",
                "content": "Riwayat chat telah di-reset. Siap untuk topik baru!",
                "timestamp": datetime.now().strftime("%H:%M"),
            }
        ]
        st.rerun()


# -----------------------------------------------------------------------------
# Main Header & Active Configuration Banner
# -----------------------------------------------------------------------------
st.markdown(f"""
<div class="hero-container">
    <div class="hero-title">
        <span>🎓 StudyBuddy AI</span>
    </div>
    <div class="hero-subtitle">
        Tutor Interaktif & Asisten Produktivitas Belajar Berbasis Google Gemini API
    </div>
    <div class="badge-bar">
        <span class="badge">🤖 Model: {selected_model}</span>
        <span class="badge">🎭 Gaya: {selected_tone.split(' ')[0]}</span>
        <span class="badge">🏫 Jenjang: {selected_level.split(' ')[0]}</span>
        <span class="badge">📚 Subjek: {selected_subject.split(' ')[0]}</span>
        <span class="badge">🌡️ Temp: {temperature}</span>
        <span class="badge {'badge-active' if st.session_state.api_key else ''}">
            {'🟢 Live API' if st.session_state.api_key else '🟡 Demo / Fallback Mode'}
        </span>
    </div>
</div>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Main Navigation Tabs
# -----------------------------------------------------------------------------
tab_chat, tab_quiz, tab_roadmap, tab_docs = st.tabs([
    "💬 Tanya Jawab & Tutor Interaktif",
    "📝 Generator Kuis & Flashcards",
    "🗺️ Roadmap Belajar Terstruktur",
    "ℹ️ Panduan & Info Proyek",
])


# =============================================================================
# TAB 1: Tanya Jawab & Tutor Interaktif
# =============================================================================
with tab_chat:
    # Quick Starter Prompts
    st.markdown("**💡 Pancingan Topik Cepat (Quick Starters):**")
    chip_cols = st.columns(4)
    quick_prompt = None

    with chip_cols[0]:
        if st.button("📐 Teorema Pythagoras", use_container_width=True):
            quick_prompt = "Jelaskan konsep Teorema Pythagoras secara tuntas, berikan penurunan rumusnya, dan sertakan contoh soal nyata."
    with chip_cols[1]:
        if st.button("💻 Kode Clean Python", use_container_width=True):
            quick_prompt = "Tunjukkan contoh penulisan fungsi Python yang memenuhi standar Clean Code dan type hinting."
    with chip_cols[2]:
        if st.button("🔬 Fotosintesis & Reaksi", use_container_width=True):
            quick_prompt = "Jelaskan perbedaan Reaksi Terang dan Reaksi Gelap pada fotosintesis beserta tempat terjadinya."
    with chip_cols[3]:
        if st.button("🤖 Konsep Machine Learning", use_container_width=True):
            quick_prompt = "Jelaskan konsep dasar Machine Learning dan 3 jenis utamanya dengan analogi yang mudah dipahami."

    # Multimodal image attachment option
    with st.expander("📷 Unggah Gambar Soal / Diagram (Multimodal)", expanded=False):
        uploaded_image_file = st.file_uploader(
            "Pilih gambar soal/catatan (PNG, JPG, JPEG):",
            type=["png", "jpg", "jpeg"],
            key="homework_image",
        )
        uploaded_pil_image = None
        if uploaded_image_file:
            uploaded_pil_image = Image.open(uploaded_image_file)
            st.image(uploaded_pil_image, caption="Gambar yang diunggah", width=350)

    st.markdown("---")

    # Render Chat History
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar="🎓" if message["role"] == "model" else "👤"):
            st.markdown(message["content"])
            if "timestamp" in message:
                st.caption(f"_{message['timestamp']}_")

    # Chat Input
    user_input = st.chat_input("Ketik pertanyaan, topik pelajaran, atau keluhan belajarmu di sini...")

    # Process input (either from chat input or quick starter)
    active_prompt = quick_prompt if quick_prompt else user_input

    if active_prompt:
        # Append User Message
        user_time = datetime.now().strftime("%H:%M")
        st.session_state.messages.append({
            "role": "user",
            "content": active_prompt,
            "timestamp": user_time,
        })

        with st.chat_message("user", avatar="👤"):
            st.markdown(active_prompt)
            st.caption(f"_{user_time}_")

        # Build dynamic system instruction based on current sidebar parameters
        system_instruction = build_system_instruction(
            tone=selected_tone,
            level=selected_level,
            subject=selected_subject,
        )

        # Generate Assistant Response with Streaming
        with st.chat_message("model", avatar="🎓"):
            message_placeholder = st.empty()
            full_response = ""

            client = GeminiService(api_key=st.session_state.api_key, model_name=selected_model)

            stream = client.generate_chat_stream(
                messages=st.session_state.messages,
                system_instruction=system_instruction,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                image=uploaded_pil_image,
            )

            for chunk in stream:
                full_response += chunk
                message_placeholder.markdown(full_response + "▌")

            message_placeholder.markdown(full_response)
            bot_time = datetime.now().strftime("%H:%M")
            st.caption(f"_{bot_time}_")

        st.session_state.messages.append({
            "role": "model",
            "content": full_response,
            "timestamp": bot_time,
        })


# =============================================================================
# TAB 2: Generator Kuis & Flashcards
# =============================================================================
with tab_quiz:
    st.subheader("📝 Generator Kuis Interaktif")
    st.write("Uji pemahamanmu secara mandiri dengan kuis pilihan ganda yang digenerate langsung oleh AI!")

    quiz_col1, quiz_col2, quiz_col3 = st.columns([2, 1, 1])
    with quiz_col1:
        quiz_topic = st.text_input("Topik Kuis:", value="Hukum Newton dan Dinamika Gerak")
    with quiz_col2:
        quiz_q_count = st.selectbox("Jumlah Soal:", [3, 5], index=0)
    with quiz_col3:
        quiz_diff = st.selectbox("Kesulitan:", ["Mudah", "Sedang", "Tantangan"])

    if st.button("🚀 Buat Kuis Baru", type="primary"):
        with st.spinner("Menyusun butir pertanyaan kuis berkualitas..."):
            client = GeminiService(api_key=st.session_state.api_key, model_name=selected_model)
            prompt = (
                f"Buatkan {quiz_q_count} butir soal pilihan ganda tentang topik: '{quiz_topic}'. "
                f"Tingkat kesulitan: {quiz_diff}. Untuk jenjang: {selected_level}. "
                "Output HARUS berupa JSON murni sesuai format kuis."
            )
            raw_result = client.generate_text(
                prompt=prompt,
                system_instruction=QUIZ_SYSTEM_INSTRUCTION,
                temperature=0.4,
            )
            parsed = parse_quiz_json(raw_result)

            if parsed and "questions" in parsed:
                st.session_state.quiz_data = parsed
                st.session_state.quiz_user_answers = {}
                st.session_state.quiz_submitted = False
                st.success("Kuis berhasil digenerate!")
            else:
                # Fallback quiz if parsing fails
                st.session_state.quiz_data = {
                    "topic": quiz_topic,
                    "difficulty": quiz_diff,
                    "questions": [
                        {
                            "id": 1,
                            "question": f"Manakah pernyataan paling tepat mengenai konsep fundamental {quiz_topic}?",
                            "options": [
                                "A. Pernyataan pertama yang paling mendasar",
                                "B. Pernyataan kedua yang sering disalahartikan",
                                "C. Pernyataan ketiga yang menjadi pengecualian",
                                "D. Pernyataan keempat yang salah total",
                            ],
                            "correct_answer": "A",
                            "explanation": "Pilihan A tepat karena mencerminkan definisi konseptual utama yang telah diuji secara eksperimental.",
                        }
                    ],
                }
                st.session_state.quiz_user_answers = {}
                st.session_state.quiz_submitted = False

    # Display Quiz Questions if available
    if st.session_state.quiz_data:
        st.markdown(f"### 📋 Kuis: {st.session_state.quiz_data.get('topic', 'Topik Pelajaran')}")
        st.caption(f"Tingkat: {st.session_state.quiz_data.get('difficulty', 'Sedang')}")

        questions = st.session_state.quiz_data.get("questions", [])

        for idx, q in enumerate(questions):
            st.markdown(f"""
            <div class="quiz-box">
                <h4>Pertanyaan {idx + 1}:</h4>
                <p style="font-size: 1.05rem; font-weight: 500;">{q.get('question')}</p>
            </div>
            """, unsafe_allow_html=True)

            options = q.get("options", [])
            choice = st.radio(
                f"Pilih jawaban untuk No. {idx + 1}:",
                options=options,
                key=f"q_{idx}",
                index=None if idx not in st.session_state.quiz_user_answers else options.index(st.session_state.quiz_user_answers[idx]) if st.session_state.quiz_user_answers[idx] in options else None,
            )
            if choice:
                st.session_state.quiz_user_answers[idx] = choice

            st.write("")

        submit_col1, submit_col2 = st.columns([1, 3])
        with submit_col1:
            if st.button("📊 Kumpulkan & Periksa Nilai", type="secondary"):
                st.session_state.quiz_submitted = True

        if st.session_state.quiz_submitted:
            score = 0
            st.markdown("---")
            st.subheader("🎯 Hasil & Pembahasan Kuis:")

            for idx, q in enumerate(questions):
                user_ans = st.session_state.quiz_user_answers.get(idx, "")
                user_letter = user_ans[0] if user_ans else ""
                correct_letter = q.get("correct_answer", "")

                is_correct = user_letter == correct_letter
                if is_correct:
                    score += 1
                    st.success(f"**Soal {idx + 1}: Benar!** (Jawabanmu: {user_ans})")
                else:
                    st.error(f"**Soal {idx + 1}: Kurang Tepat.** Jawabanmu: {user_ans or 'Belum dijawab'} | Kunci: **{correct_letter}**")

                with st.expander(f"💡 Pembahasan Soal {idx + 1}", expanded=True):
                    st.markdown(q.get("explanation", "Tidak ada pembahasan."))

            final_percent = (score / len(questions)) * 100 if questions else 0
            st.metric(label="Skor Akhir", value=f"{final_percent:.0f}%", delta=f"{score}/{len(questions)} Benar")


# =============================================================================
# TAB 3: Roadmap Belajar Terstruktur
# =============================================================================
with tab_roadmap:
    st.subheader("🗺️ Kurator Kurikulum & Roadmap Belajar Mandiri")
    st.write("Masukkan bidang atau topik keahlian yang ingin kamu kuasai untuk mendapatkan panduan belajar terarah.")

    road_col1, road_col2 = st.columns([3, 1])
    with road_col1:
        target_subject = st.text_input("Keahlian / Topik Belajar Sasaran:", value="Data Science & Machine Learning")
    with road_col2:
        available_hours = st.selectbox("Komitmen Waktu per Minggu:", ["5-10 Jam", "10-20 Jam", "Full-time (30+ Jam)"])

    if st.button("✨ Rancang Roadmap", type="primary"):
        with st.spinner("Menyusun kurikulum dan tahapan pembelajaran terbaik..."):
            client = GeminiService(api_key=st.session_state.api_key, model_name=selected_model)
            prompt = (
                f"Rancang kurikulum dan roadmap belajar mendalam untuk topik: '{target_subject}'. "
                f"Alokasi waktu: {available_hours} per minggu. Target jenjang: {selected_level}. "
                "Sertakan: Tahapan (Fase 1 sampai 4), konsep kunci tiap fase, proyek implementasi nyata, "
                "rekomendasi referensi buku/kursus gratis, serta tips konsistensi."
            )
            result = client.generate_text(
                prompt=prompt,
                system_instruction=ROADMAP_SYSTEM_INSTRUCTION,
                temperature=0.6,
            )
            st.session_state.roadmap_result = result

    if st.session_state.roadmap_result:
        st.markdown("---")
        st.markdown(st.session_state.roadmap_result)

        st.download_button(
            label="📥 Unduh Roadmap (Markdown)",
            data=st.session_state.roadmap_result,
            file_name=f"roadmap_{target_subject.replace(' ', '_').lower()}.md",
            mime="text/markdown",
        )


# =============================================================================
# TAB 4: Panduan & Info Proyek
# =============================================================================
with tab_docs:
    st.subheader("📖 Dokumentasi Proyek & Spesifikasi Sistem")
    st.markdown("""
### Proyek: AI Productivity and AI API Integration for Developers
**Nama Aplikasi**: StudyBuddy AI (Tutor Cerdas Interaktif & Asisten Produktivitas Belajar)

#### 1. Arsitektur & Teknologi:
- **LLM Engine**: Google Gemini API (`gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-1.5-flash`, `gemini-3.8-flash`) via `google-genai` & `google-generativeai`.
- **Framework UI**: Streamlit 1.x (Python) dengan custom CSS glassmorphism, responsive chat components, and typography.
- **Multimodal**: Mendukung analisis teks dan gambar (soal/diagram pelajaran) via Gemini Vision.
- **Export System**: Otomatisasi ekspor catatan sesi belajar ke Markdown dan Plain Text.

#### 2. Konfigurasi Parameter Kreatif:
| Parameter | Deskripsi & Dampak | Pilihan Nilai |
|---|---|---|
| **Gaya Bahasa (Tone)** | Memodulasi persona tutor | Santai (Peer), Formal Akademis, Metode Socrates, ELI5, To-the-Point |
| **Jenjang Pendidikan** | Menyesuaikan kedalaman materi | SD/SMP (Dasar), SMA/SMK, Kuliah/Universitas, Umum |
| **Spesialisasi Subjek** | Mengoptimalkan pemformatan respon | STEM (LaTeX rumus), Coding (Syntax highlight), Bahasa, Sejarah, All-Rounder |
| **Temperature & Top-P** | Mengatur tingkat kreativitas vs determinisme | 0.0 - 2.0 (Temperature), 0.1 - 1.0 (Top-P) |
| **Mode Interaktif** | Fitur fungsional spesifik | Tanya Jawab, Kuis Interaktif, Roadmap Belajar, Pomodoro Timer |

#### 3. Cara Menjalankan Secara Lokal:
```bash
# 1. Clone repository
git clone https://github.com/JustNickyH/studybuddy-bot.git
cd studybuddy-bot

# 2. Aktifkan virtual environment & install dependencies
source env/bin/activate
pip install -r requirements.txt

# 3. Setup API Key (Opsional: buat file .env)
cp .env.example .env
# Edit .env dan masukkan GEMINI_API_KEY=AIzaSy...

# 4. Jalankan aplikasi Streamlit
streamlit run app.py
```
    """)
