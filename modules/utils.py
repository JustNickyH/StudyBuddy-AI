"""
Utility functions for StudyBuddy AI: export tools, JSON extractors, and UI helpers.
"""

import re
import json
from datetime import datetime
from typing import List, Dict, Any, Optional


def export_chat_to_markdown(messages: List[Dict[str, Any]], session_metadata: Optional[Dict[str, Any]] = None) -> str:
    """Exports chat session to formatted Markdown."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = [
        f"# 🎓 Catatan Sesi Belajar - StudyBuddy AI",
        f"**Waktu Ekspor**: {now_str}",
    ]

    if session_metadata:
        md.append(f"- **Model**: `{session_metadata.get('model', '-')}`")
        md.append(f"- **Tone / Gaya Bahasa**: {session_metadata.get('tone', '-')}")
        md.append(f"- **Jenjang Pendidikan**: {session_metadata.get('level', '-')}")
        md.append(f"- **Subjek**: {session_metadata.get('subject', '-')}")
        md.append(f"- **Temperature**: `{session_metadata.get('temperature', '-')}`")

    md.append("\n---\n")

    for i, msg in enumerate(messages, 1):
        role_label = "👤 Pengguna / Pelajar" if msg["role"] == "user" else "🤖 StudyBuddy AI"
        timestamp = msg.get("timestamp", "")
        time_tag = f" *({timestamp})*" if timestamp else ""

        md.append(f"### {role_label}{time_tag}\n")
        md.append(msg["content"].strip())
        md.append("\n---\n")

    md.append("\n*Dihasilkan secara otomatis oleh StudyBuddy AI (Powered by Google Gemini)*")
    return "\n".join(md)


def export_chat_to_text(messages: List[Dict[str, Any]]) -> str:
    """Exports chat session to plain text format."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "========================================",
        "  CATATAN BELAJAR - STUDYBUDDY AI",
        f"  Tanggal: {now_str}",
        "========================================\n",
    ]

    for msg in messages:
        role = "PELAJAR" if msg["role"] == "user" else "STUDYBUDDY AI"
        lines.append(f"[{role}]:")
        lines.append(msg["content"].strip())
        lines.append("-" * 40 + "\n")

    return "\n".join(lines)


def parse_quiz_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """Robustly extracts and parses JSON quiz structure from model response."""
    # Try direct parse
    try:
        return json.loads(raw_text)
    except Exception:
        pass

    # Try finding json block inside markdown ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass

    # Try finding first { to last }
    first_brace = raw_text.find("{")
    last_brace = raw_text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = raw_text[first_brace : last_brace + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return None
