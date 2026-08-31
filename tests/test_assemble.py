import json
import subprocess
import wave
import struct
from PIL import Image
from pipeline import assemble


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

    result = assemble.assemble_video(storyboard, [still1, clip1], music, out_path, work_dir=str(tmp_path / "work"))

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
