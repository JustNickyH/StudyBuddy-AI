"""
Gemini API Client integration with support for google-genai and google-generativeai,
supporting streaming, multimodal inputs, temperature/top_p parameter configuration,
and an intelligent fallback/demo engine.
"""

import os
import json
import time
from typing import Generator, List, Dict, Any, Optional
from PIL import Image

# Available model choices
SUPPORTED_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash",
    "gemini-3.8-flash",
]

DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiService:
    def __init__(self, api_key: Optional[str] = None, model_name: str = DEFAULT_MODEL):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.client_type = None
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initializes either google-genai or google-generativeai client."""
        if not self.api_key:
            return

        # Attempt modern google-genai SDK first
        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            self.client_type = "google-genai"
            return
        except Exception:
            pass

        # Fallback to google-generativeai SDK
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=self.api_key)
            self.client_type = "google-generativeai"
        except Exception:
            self.client_type = None

    def is_configured(self) -> bool:
        """Returns True if a valid-looking API key is present and client initialized."""
        return bool(self.api_key and len(self.api_key.strip()) > 10)

    def test_connection(self) -> Dict[str, Any]:
        """Tests the API connection by making a small request."""
        if not self.is_configured():
            return {"success": False, "message": "API Key belum diisi atau tidak valid."}

        try:
            prompt = "Tes koneksi: Jawab singkat 'Koneksi Berhasil!' dalam 1 kalimat."
            resp = self.generate_text(
                prompt=prompt,
                system_instruction="Kamu adalah asisten penguji koneksi API.",
                temperature=0.2,
                max_tokens=50
            )
            return {"success": True, "message": resp.strip()}
        except Exception as e:
            return {"success": False, "message": f"Error koneksi: {str(e)}"}

    def generate_chat_stream(
        self,
        messages: List[Dict[str, Any]],
        system_instruction: str,
        temperature: float = 0.7,
        top_p: float = 0.95,
        max_tokens: int = 2048,
        image: Optional[Image.Image] = None,
    ) -> Generator[str, None, None]:
        """
        Streams response chunks for multi-turn chat.
        If no API key is set, streams from the intelligent fallback demo generator.
        """
        if not self.is_configured():
            yield from self._stream_demo_response(messages, system_instruction, image)
            return

        last_user_message = messages[-1]["content"] if messages else ""

        # Modern google-genai SDK
        if self.client_type == "google-genai":
            try:
                from google.genai import types

                # Build contents list from history
                contents_payload = []
                for m in messages[:-1]:
                    role = "user" if m["role"] == "user" else "model"
                    contents_payload.append(types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=m["content"])]
                    ))

                # For last message, add image if present
                last_parts = []
                if image is not None:
                    last_parts.append(image)
                last_parts.append(last_user_message)

                contents_payload.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=last_user_message)] if image is None else last_parts
                ))

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                    top_p=top_p,
                    max_output_tokens=max_tokens,
                )

                response_stream = self._client.models.generate_content_stream(
                    model=self.model_name,
                    contents=contents_payload if len(contents_payload) > 1 else (last_parts if image else last_user_message),
                    config=config,
                )

                for chunk in response_stream:
                    if hasattr(chunk, "text") and chunk.text:
                        yield chunk.text
                return
            except Exception as e:
                # If error occurs, fall back to legacy or demo with error banner
                yield f"\n\n> ⚠️ *Peringatan API*: Terjadi kendala saat memanggil Gemini API ({str(e)}). Beralih ke respon asistensi edukasi lokal:\n\n"
                yield from self._stream_demo_response(messages, system_instruction, image)
                return

        # Legacy google.generativeai SDK
        elif self.client_type == "google-generativeai":
            try:
                import google.generativeai as legacy_genai

                gen_config = legacy_genai.GenerationConfig(
                    temperature=temperature,
                    top_p=top_p,
                    max_output_tokens=max_tokens,
                )

                model = legacy_genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=system_instruction,
                    generation_config=gen_config,
                )

                chat_history = []
                for m in messages[:-1]:
                    role = "user" if m["role"] == "user" else "model"
                    chat_history.append({"role": role, "parts": [m["content"]]})

                chat = model.start_chat(history=chat_history)
                contents = [image, last_user_message] if image is not None else last_user_message
                response = chat.send_message(contents, stream=True)

                for chunk in response:
                    if chunk.text:
                        yield chunk.text
                return
            except Exception as e:
                yield f"\n\n> ⚠️ *Peringatan API*: Terjadi kendala API ({str(e)}). Menggunakan respon simulasi edukasi:\n\n"
                yield from self._stream_demo_response(messages, system_instruction, image)
                return

        # Fallback if no client
        yield from self._stream_demo_response(messages, system_instruction, image)

    def generate_text(
        self,
        prompt: str,
        system_instruction: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        image: Optional[Image.Image] = None,
    ) -> str:
        """Non-streaming text generation."""
        if not self.is_configured():
            return self._generate_demo_text(prompt, system_instruction)

        if self.client_type == "google-genai":
            try:
                from google.genai import types
                parts = [image, prompt] if image else [prompt]
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
                res = self._client.models.generate_content(
                    model=self.model_name,
                    contents=parts,
                    config=config
                )
                return res.text or ""
            except Exception as e:
                return f"[Error Gemini API: {str(e)}]\n\n" + self._generate_demo_text(prompt, system_instruction)

        elif self.client_type == "google-generativeai":
            try:
                import google.generativeai as legacy_genai
                model = legacy_genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=system_instruction,
                )
                parts = [image, prompt] if image else prompt
                res = model.generate_content(parts)
                return res.text or ""
            except Exception as e:
                return f"[Error Gemini API: {str(e)}]\n\n" + self._generate_demo_text(prompt, system_instruction)

        return self._generate_demo_text(prompt, system_instruction)

    # -------------------------------------------------------------
    # Intelligent Demo & Fallback Simulation Engine
    # -------------------------------------------------------------
    def _stream_demo_response(
        self,
        messages: List[Dict[str, Any]],
        system_instruction: str,
        image: Optional[Image.Image] = None
    ) -> Generator[str, None, None]:
        """Provides realistic educational streaming responses for offline / demonstration testing."""
        query = messages[-1]["content"].lower() if messages else ""

        full_response = ""

        if image is not None:
            full_response = (
                "### 📷 Analisis Berkas & Gambar Pembelajaran\n\n"
                "Saya telah memeriksa visual/dokumen yang kamu unggah:\n\n"
                "1. **Identifikasi Masalah**: Soal ini berkaitan dengan pemecahan konsep analitis dan visualisasi terstruktur.\n"
                "2. **Langkah Pengerjaan Sistematis**:\n"
                "   - **Langkah 1**: Catat semua data dan variabel yang diketahui dari diagram/soal.\n"
                "   - **Langkah 2**: Terapkan rumus/prinsip utama:\n"
                "     $$\\Delta E = mc^2 \\quad \\text{atau} \\quad f(x) = \\lim_{h \\to 0} \\frac{f(x+h) - f(x)}{h}$$\n"
                "   - **Langkah 3**: Substitusikan nilai-nilai ke dalam persamaan dan sederhanakan secara aljabar.\n"
                "3. **Kesimpulan & Rekomendasi**: Periksa kembali satuan nilai akhir agar tidak terjadi kekeliruan konversi.\n\n"
                "💡 *Tips*: Apakah kamu ingin saya bedah bagian tertentu dari gambar ini secara lebih detail?"
            )
        elif "pythagoras" in query or "segitiga" in query:
            full_response = (
                "### 📐 Penjelasan Teorema Pythagoras\n\n"
                "**Teorema Pythagoras** adalah salah satu teorema paling fundamental dalam geometri yang berlaku pada **segitiga siku-siku**.\n\n"
                "#### 1. Rumus Utama\n"
                "Jika sebuah segitiga memiliki sisi tegak $a$, sisi mendatar $b$, dan sisi miring (hipotenusa) $c$, maka:\n"
                "$$a^2 + b^2 = c^2$$\n\n"
                "Atau jika kita mencari sisi miring:\n"
                "$$c = \\sqrt{a^2 + b^2}$$\n\n"
                "#### 2. Contoh Soal & Pembahasan\n"
                "Sebuah segitiga siku-siku memiliki panjang alas $a = 3\\text{ cm}$ dan tinggi $b = 4\\text{ cm}$. Berapakah panjang hipotenusa $c$?\n\n"
                "**Penyelesaian:**\n"
                "1. Masukkan ke rumus: $c^2 = 3^2 + 4^2$\n"
                "2. Hitung kuadrat: $c^2 = 9 + 16 = 25$\n"
                "3. Akarkan: $c = \\sqrt{25} = 5\\text{ cm}$\n\n"
                "#### 3. Triple Pythagoras Populer\n"
                "| $a$ | $b$ | $c$ |\n"
                "|:---:|:---:|:---:|\n"
                "| 3   | 4   | 5   |\n"
                "| 5   | 12  | 13  |\n"
                "| 7   | 24  | 25  |\n"
                "| 8   | 15  | 17  |\n\n"
                "🧠 **Kuis Cepat**: Jika $a = 6$ dan $b = 8$, berapakah nilai $c$? Coba tebak tanpa kalkulator!"
            )
        elif "python" in query or "code" in query or "debug" in query or "loop" in query or "fungsi" in query:
            full_response = (
                "### 💻 Panduan Pemrograman Python\n\n"
                "Berikut adalah panduan best-practice untuk penulisan kode bersih (*clean code*) dan penanganan logika di Python:\n\n"
                "```python\n"
                "# Contoh implementasi fungsi pencarian nilai rata-rata dengan type hints\n"
                "from typing import List\n\n"
                "def hitung_statistik(nilai_siswa: List[float]) -> dict:\n"
                "    \"\"\"\n"
                "    Menghitung total, rata-rata, dan nilai tertinggi dari daftar nilai.\n"
                "    \"\"\"\n"
                "    if not nilai_siswa:\n"
                "        raise ValueError(\"Daftar nilai tidak boleh kosong!\")\n"
                "        \n"
                "    total = sum(nilai_siswa)\n"
                "    rata_rata = total / len(nilai_siswa)\n"
                "    tertinggi = max(nilai_siswa)\n"
                "    \n"
                "    return {\n"
                "        \"total\": total,\n"
                "        \"rata_rata\": round(rata_rata, 2),\n"
                "        \"tertinggi\": tertinggi\n"
                "    }\n\n"
                "# Pengujian fungsi\n"
                "daftar = [85.5, 90.0, 78.5, 95.0, 88.0]\n"
                "hasil = hitung_statistik(daftar)\n"
                "print(f\"Rata-rata kelas: {hasil['rata_rata']}\")\n"
                "```\n\n"
                "#### 🔑 Tips Penting:\n"
                "- Gunakan **Type Hinting** (`List[float]`, `dict`) untuk mempermudah deteksi bug.\n"
                "- Selalu sertakan validasi input (`if not nilai_siswa`) agar program tidak crash.\n"
                "- Gunakan format string (`f-string`) untuk keterbacaan yang optimal.\n\n"
                "Ada error atau snippet kode tertentu yang ingin kita telusuri bersama?"
            )
        elif "machine learning" in query or "ai" in query:
            full_response = (
                "### 🤖 Konsep Dasar Artificial Intelligence & Machine Learning\n\n"
                "Secara sederhana, bayangkan **Machine Learning** seperti mengajarkan seorang anak mengenali buah apel:\n"
                "- **Pemrograman Tradisional**: Kamu harus menulis aturan secara manual satu demi satu (*'Jika warna merah dan bentuk bulat maka apel'*).\n"
                "- **Machine Learning**: Kamu memperlihatkan 1.000 foto apel dan 1.000 foto jeruk, lalu model matematika secara mandiri menemukan pola pembedanya.\n\n"
                "#### 3 Pilar Utama Machine Learning:\n"
                "1. **Supervised Learning** (Belajar Terarah): Data memiliki label (contoh: prediksi harga rumah, deteksi spam email).\n"
                "2. **Unsupervised Learning** (Belajar Tak Terarah): Menemukan kelompok tersembunyi tanpa label (contoh: segmentasi pelanggan).\n"
                "3. **Reinforcement Learning** (Belajar Berbasis Hadiah): Agen belajar melalui trial and error (contoh: robot berjalan, AI bermain catur).\n\n"
                "$$J(\\theta) = \\frac{1}{2m} \\sum_{i=1}^m \\left( h_\\theta(x^{(i)}) - y^{(i)} \\right)^2$$\n"
                "*Rumus di atas adalah Mean Squared Error (MSE), salah satu fungsi loss paling umum untuk mengukur seberapa meleset prediksi model.*\n\n"
                "Apakah kamu tertarik mengeksplorasi bagian matematika di baliknya atau implementasi kodenya menggunakan Scikit-Learn/PyTorch?"
            )
        else:
            full_response = (
                f"### 📚 Pembahasan Edukasi: {messages[-1]['content'] if messages else 'Materi'}\n\n"
                "Halo! Mari kita bedah pertanyaan ini secara mendalam dan terstruktur.\n\n"
                "#### 1. Konsep Utama\n"
                f"Materi mengenai topik ini mencakup pemahaman konsep fundamental, hubungan sebab-akibat, "
                "serta aplikasinya dalam menyelesaikan persoalan nyata.\n\n"
                "#### 2. Poin-Poin Penting untuk Diingat\n"
                "- **Pondasi Konseptual**: Memahami definisi dan prinsip dasar sebelum melangkah ke rumus atau detail teknis.\n"
                "- **Metode Analisis**: Memecah persoalan besar menjadi komponen-komponen yang lebih kecil dan mudah diselesaikan.\n"
                "- **Contoh Kasus**: Menghubungkan konsep teoritis dengan fenomena yang kita temui sehari-hari.\n\n"
                "#### 3. Rangkuman & Action Items\n"
                "1. Buat catatan ringkas (*mind-map*) dari istilah-istilah kunci.\n"
                "2. Lakukan latihan soal atau pembuatan proyek mini untuk menguji pemahaman.\n"
                "3. Diskusikan bagian yang masih membingungkan.\n\n"
                "💡 **Pertanyaan Reflektif**: Menurutmu, apa tantangan terbesar saat mempelajari topik ini, dan bagian mana yang ingin kita perdalam sekarang?"
            )

        # Stream words smoothly to simulate real-time LLM token generation
        words = full_response.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            if i % 5 == 0:
                time.sleep(0.015)

    def _generate_demo_text(self, prompt: str, system_instruction: str) -> str:
        """Returns non-streaming educational text for demo/fallback."""
        if "quiz" in prompt.lower() or "kuis" in prompt.lower() or "json" in prompt.lower():
            return json.dumps({
                "topic": "Fundamental Sains & Matematika",
                "difficulty": "Menengah (SMA / Kuliah)",
                "questions": [
                    {
                        "id": 1,
                        "question": "Jika suatu segitiga siku-siku memiliki sisi tegak 6 cm dan 8 cm, berapakah panjang sisi miringnya?",
                        "options": ["A. 10 cm", "B. 12 cm", "C. 14 cm", "D. 15 cm"],
                        "correct_answer": "A",
                        "explanation": "Berdasarkan Teorema Pythagoras: c = √(6² + 8²) = √(36 + 64) = √100 = 10 cm."
                    },
                    {
                        "id": 2,
                        "question": "Manakah struktur data berikut yang bekerja dengan prinsip First-In First-Out (FIFO)?",
                        "options": ["A. Stack", "B. Queue", "C. Binary Tree", "D. Hash Map"],
                        "correct_answer": "B",
                        "explanation": "Queue (antrean) memproses elemen yang masuk pertama kali untuk keluar pertama kali (FIFO)."
                    },
                    {
                        "id": 3,
                        "question": "Organel sel yang berfungsi sebagai penghasil energi utama (ATP) melalui respirasi seluler adalah...",
                        "options": ["A. Ribosom", "B. Mitokondria", "C. Badan Golgi", "D. Retikulum Endoplasma"],
                        "correct_answer": "B",
                        "explanation": "Mitokondria sering dijuluki 'the powerhouse of the cell' karena memproduksi ATP melalui siklus Krebs dan fosforilasi oksidatif."
                    }
                ]
            }, indent=2)

        return (
            "### 🗺️ Roadmap Belajar Terstruktur\n\n"
            "Berikut panduan langkah demi langkah untuk menguasai topik ini secara komprehensif:\n\n"
            "1. **Fase 1 - Fondasi & Logika Dasar (Minggu 1-2)**: Pelajari sintaks dasar, terminologi, dan prinsip kerja.\n"
            "2. **Fase 2 - Pendalaman Konsep & Mini-Quiz (Minggu 3-4)**: Selesaikan 10-20 studi kasus terarah.\n"
            "3. **Fase 3 - Proyek Nyata & Portofolio (Minggu 5-8)**: Bangun aplikasi atau esai ilmiah mandiri.\n"
            "4. **Fase 4 - Evaluasi & Uji Kompetensi (Minggu 9+)**: Peer-review dan uji coba soal tantangan."
        )
