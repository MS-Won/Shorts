import json
import shutil
import subprocess
import wave

import pytest
from PIL import Image

from pipeline import assemble

# These tests drive the real ffmpeg binary. Without it they fail with a pile of
# unrelated-looking errors, so say plainly what is missing instead.
pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not on PATH — install ffmpeg (winget install Gyan.FFmpeg) "
           "and reopen the terminal so the updated PATH is picked up",
)


def _make_still(path, color=(200, 50, 50)):
    Image.new("RGB", (640, 480), color).save(path)


def _make_clip(path, duration_sec=2, color="red"):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=640x480:d={duration_sec}",
        "-pix_fmt", "yuv420p", path,
    ], check=True, capture_output=True)


def _make_silent_wav(path, duration_sec=10):
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * duration_sec)


def _probe_duration(path) -> float:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", path,
    ], check=True, capture_output=True, text=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def _probe_resolution(path) -> tuple[int, int]:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "json", path,
    ], check=True, capture_output=True, text=True)
    stream = json.loads(result.stdout)["streams"][0]
    return stream["width"], stream["height"]


def _probe_has_audio(path) -> bool:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
        "stream=codec_type", "-of", "json", path,
    ], check=True, capture_output=True, text=True)
    return bool(json.loads(result.stdout).get("streams"))


def test_assemble_video_produces_output_with_expected_total_duration(tmp_path):
    still1 = str(tmp_path / "still1.png")
    clip1 = str(tmp_path / "clip1.mp4")
    music = str(tmp_path / "music.wav")
    out_path = str(tmp_path / "final.mp4")

    _make_still(still1)
    _make_clip(clip1, duration_sec=3)
    _make_silent_wav(music, duration_sec=10)

    storyboard = {
        "beats": [
            {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in",
             "duration_sec": 4, "caption": "intro caption"},
            {"stage": "progress", "type": "transform_video", "prompt_start": "a", "prompt_end": "b",
             "duration_sec": 3, "caption": "progress caption"},
        ],
    }

    result = assemble.assemble_video(storyboard, [still1, clip1], music, out_path,
                                     work_dir=str(tmp_path / "work"))

    assert result == out_path
    duration = _probe_duration(out_path)
    assert 6.5 <= duration <= 7.5  # 4s + 3s, small ffmpeg rounding tolerance


def test_assemble_video_output_is_vertical_1080x1920(tmp_path):
    still1 = str(tmp_path / "still1.png")
    music = str(tmp_path / "music.wav")
    out_path = str(tmp_path / "final.mp4")

    _make_still(still1)
    _make_silent_wav(music, duration_sec=5)

    storyboard = {"beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in",
         "duration_sec": 4, "caption": "intro caption"},
    ]}

    assemble.assemble_video(storyboard, [still1], music, out_path, work_dir=str(tmp_path / "work"))
    assert _probe_resolution(out_path) == (1080, 1920)


def test_assemble_video_keeps_an_audio_track(tmp_path):
    still1 = str(tmp_path / "still1.png")
    music = str(tmp_path / "music.wav")
    out_path = str(tmp_path / "final.mp4")
    _make_still(still1)
    _make_silent_wav(music, duration_sec=5)

    storyboard = {"beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in",
         "duration_sec": 3, "caption": "hi"},
    ]}
    assemble.assemble_video(storyboard, [still1], music, out_path, work_dir=str(tmp_path / "work"))
    assert _probe_has_audio(out_path)


def test_assemble_video_does_not_truncate_when_music_is_shorter_than_video(tmp_path):
    # A 30s+ Short over a 20s track must stay 30s — the track loops.
    still1 = str(tmp_path / "still1.png")
    music = str(tmp_path / "music.wav")
    out_path = str(tmp_path / "final.mp4")

    _make_still(still1)
    _make_silent_wav(music, duration_sec=2)

    storyboard = {"beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in",
         "duration_sec": 6, "caption": "long shot"},
    ]}

    assemble.assemble_video(storyboard, [still1], music, out_path, work_dir=str(tmp_path / "work"))
    assert _probe_duration(out_path) >= 5.5


def test_assemble_video_survives_captions_with_filter_metacharacters(tmp_path):
    # Commas separate ffmpeg filters, colons separate filter options, and '%'
    # is a strftime escape. A caption is free-form LLM text and will contain all
    # three sooner or later.
    still1 = str(tmp_path / "still1.png")
    music = str(tmp_path / "music.wav")
    out_path = str(tmp_path / "final.mp4")

    _make_still(still1)
    _make_silent_wav(music, duration_sec=5)

    storyboard = {"beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in", "duration_sec": 3,
         "caption": "wait, there's a hidden room: 100% over budget [day 1]"},
    ]}

    assemble.assemble_video(storyboard, [still1], music, out_path, work_dir=str(tmp_path / "work"))
    assert _probe_resolution(out_path) == (1080, 1920)


@pytest.mark.parametrize("pan", ["in", "out", "left", "right"])
def test_assemble_video_renders_every_pan_direction(tmp_path, pan):
    still1 = str(tmp_path / "still1.png")
    music = str(tmp_path / "music.wav")
    out_path = str(tmp_path / f"final_{pan}.mp4")

    _make_still(still1)
    _make_silent_wav(music, duration_sec=5)

    storyboard = {"beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": pan,
         "duration_sec": 2, "caption": "pan test"},
    ]}
    assemble.assemble_video(storyboard, [still1], music, out_path, work_dir=str(tmp_path / "work"))
    assert _probe_resolution(out_path) == (1080, 1920)


def test_resolve_font_raises_a_clear_error_when_no_font_is_available(monkeypatch):
    monkeypatch.delenv("CAPTION_FONT", raising=False)
    monkeypatch.setattr(assemble, "FONT_CANDIDATES", ("/definitely/not/a/font.ttf",))
    with pytest.raises(assemble.AssemblyError, match="font"):
        assemble._resolve_font()
