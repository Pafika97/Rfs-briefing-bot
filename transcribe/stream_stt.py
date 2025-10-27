import asyncio, logging, io, tempfile
from typing import AsyncGenerator
from faster_whisper import WhisperModel
from pydub import AudioSegment
import soundfile as sf

_model = None
def _get_model():
    global _model
    if _model is None:
        _model = WhisperModel("small", device="auto", compute_type="int8")
    return _model

async def stream_transcribe_stdin(stdout_pipe) -> AsyncGenerator[str, None]:
    buf = bytearray()
    chunk = await stdout_pipe.read(64 * 1024)
    while chunk:
        buf.extend(chunk)
        if len(buf) > 512_000:
            text = _transcribe_bytes(bytes(buf))
            buf.clear()
            if text.strip():
                yield text.strip()
        chunk = await stdout_pipe.read(64 * 1024)

def _transcribe_bytes(b: bytes) -> str:
    try:
        seg = AudioSegment.from_file(io.BytesIO(b))
        seg = seg.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    except Exception as e:
        logging.error("decode audio failed: %s", e); return ""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        seg.export(tmp.name, format="wav")
        model = _get_model()
        segments, _ = model.transcribe(tmp.name, vad_filter=True, language="ru")
        return " ".join(s.text for s in segments)
