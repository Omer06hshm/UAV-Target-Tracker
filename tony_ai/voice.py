"""Optional text-to-speech output for Tony's API responses.

Generated speech is AI-generated; clients must disclose this to listeners.
Voice choice and style are adjustable through environment variables.
"""
import os
from openai import OpenAI

TONY_VOICE = os.getenv("TONY_VOICE", "onyx")
TONY_VOICE_STYLE = os.getenv(
    "TONY_VOICE_STYLE",
    "Speak in a natural, confident adult masculine voice, warm but professional. "
    "Use a measured pace and clear engineering terminology.",
)

def speak(text: str) -> bytes:
    """Return MP3 bytes; API key and billing required."""
    response = OpenAI().audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=TONY_VOICE,
        instructions=TONY_VOICE_STYLE,
        input=text[:4096],
        response_format="mp3",
    )
    return response.content
