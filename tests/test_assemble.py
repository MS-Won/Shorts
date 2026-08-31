import json
import os
import subprocess
import wave
import struct
import pytest
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
    _make_clip(clip1, duration_sec=15)
    _make_silent_wav(music, duration_sec=40)

    storyboard = {
        "beats": [
            {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in",
             "duration_sec": 20, "caption": "intro caption"},
            {"stage": "progress", "type": "transform_video", "prompt_start": "a", "prompt_end": "b",
             "duration_sec": 15, "caption": "progress caption"},
        ],
    }

    result = assemble.assemble_video(storyboard, [still1, clip1], music, out_path, work_dir=str(tmp_path / "work"))

    assert result == out_path
    duration = _probe_duration(out_path)
    assert 34.5 <= duration <= 35.5  # 20s + 15s, small ffmpeg rounding tolerance


def test_assemble_video_output_is_vertical_1080x1920(tmp_path):
    still1 = str(tmp_path / "still1.png")
    music = str(tmp_path / "music.wav")
    out_path = str(tmp_path / "final.mp4")

    _make_still(still1)
    _make_silent_wav(music, duration_sec=35)

    storyboard = {"beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in",
         "duration_sec": 33, "caption": "intro caption"},
    ]}

    assemble.assemble_video(storyboard, [still1], music, out_path, work_dir=str(tmp_path / "work"))
    assert _probe_resolution(out_path) == (1080, 1920)


def test_assemble_video_raises_on_asset_beat_count_mismatch(tmp_path):
    still1 = str(tmp_path / "still1.png")
    music = str(tmp_path / "music.wav")
    out_path = str(tmp_path / "final.mp4")

    _make_still(still1)
    _make_silent_wav(music, duration_sec=30)

    storyboard = {
        "beats": [
            {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in",
             "duration_sec": 4, "caption": "intro caption"},
            {"stage": "progress", "type": "still_pan", "prompt": "y", "pan": "out",
             "duration_sec": 4, "caption": "progress caption"},
            {"stage": "climax", "type": "still_pan", "prompt": "z", "pan": "left",
             "duration_sec": 4, "caption": "climax caption"},
            {"stage": "resolution", "type": "still_pan", "prompt": "w", "pan": "right",
             "duration_sec": 4, "caption": "resolution caption"},
        ],
    }

    # Only one asset path provided for a 4-beat storyboard.
    with pytest.raises(ValueError):
        assemble.assemble_video(storyboard, [still1], music, out_path, work_dir=str(tmp_path / "work"))


def test_assemble_video_raises_when_music_shorter_than_video(tmp_path):
    still1 = str(tmp_path / "still1.png")
    music = str(tmp_path / "music.wav")
    out_path = str(tmp_path / "final.mp4")

    _make_still(still1)
    _make_silent_wav(music, duration_sec=2)

    storyboard = {"beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in",
         "duration_sec": 4, "caption": "intro caption"},
    ]}

    with pytest.raises(ValueError):
        assemble.assemble_video(storyboard, [still1], music, out_path, work_dir=str(tmp_path / "work"))
    assert not os.path.exists(out_path)


def test_assemble_video_with_percent_in_caption_does_not_raise(tmp_path):
    still1 = str(tmp_path / "still1.png")
    music = str(tmp_path / "music.wav")
    out_path = str(tmp_path / "final.mp4")

    _make_still(still1)
    _make_silent_wav(music, duration_sec=35)

    storyboard = {"beats": [
        {"stage": "setup", "type": "still_pan", "prompt": "x", "pan": "in",
         "duration_sec": 33, "caption": "100% satisfying"},
    ]}

    result = assemble.assemble_video(storyboard, [still1], music, out_path, work_dir=str(tmp_path / "work"))
    assert result == out_path
    assert os.path.exists(out_path)


def test_assemble_video_raises_when_final_duration_under_30s_floor(tmp_path):
    # The beat's nominal duration_sec (35s) is comfortably >= the 30s floor,
    # but the actual rendered clip (a stand-in for a video-gen API returning
    # a shorter-than-requested clip) is only 3s. _build_video_clip can't
    # extend past the source's real length, so the final assembled video
    # ends up far under 30s -- assemble_video must catch this rather than
    # silently producing a short video.
    clip1 = str(tmp_path / "clip1.mp4")
    music = str(tmp_path / "music.wav")
    out_path = str(tmp_path / "final.mp4")

    _make_clip(clip1, duration_sec=3)
    _make_silent_wav(music, duration_sec=60)

    storyboard = {"beats": [
        {"stage": "setup", "type": "transform_video", "prompt_start": "a", "prompt_end": "b",
         "duration_sec": 35, "caption": "intro caption"},
    ]}

    with pytest.raises(ValueError, match="30"):
        assemble.assemble_video(storyboard, [clip1], music, out_path, work_dir=str(tmp_path / "work"))
