import os
import subprocess

_WIDTH = 1080
_HEIGHT = 1920
_FPS = 30

_PAN_FILTERS = {
    "in": "zoompan=z='min(zoom+0.0015,1.3)':d={frames}:s={w}x{h}:fps={fps}",
    "out": "zoompan=z='if(eq(on,1),1.3,max(1.3-0.0015*on,1.0))':d={frames}:s={w}x{h}:fps={fps}",
    "left": "zoompan=z=1.15:x='if(eq(on,1),iw*0.15,x-1)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    "right": "zoompan=z=1.15:x='if(eq(on,1),0,x+1)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
}


def _escape_caption(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _drawtext_filter(caption: str) -> str:
    escaped = _escape_caption(caption)
    # expansion=none disables drawtext's own %{...} expansion syntax, so a
    # literal '%' in the caption (e.g. "100% satisfying") is rendered as-is
    # instead of being parsed as the start of an expansion sequence (which
    # otherwise crashes ffmpeg with "Stray % near ...").
    return (
        f"drawtext=text='{escaped}':expansion=none:fontcolor=white:fontsize=64:"
        "borderw=4:bordercolor=black:x=(w-text_w)/2:y=h-th-160"
    )


def _build_still_clip(image_path: str, duration_sec: float, pan: str, caption: str, out_path: str) -> None:
    frames = int(duration_sec * _FPS)
    pan_filter = _PAN_FILTERS[pan].format(frames=frames, w=_WIDTH, h=_HEIGHT, fps=_FPS)
    vf = f"scale={_WIDTH}:{_HEIGHT}:force_original_aspect_ratio=increase,crop={_WIDTH}:{_HEIGHT},{pan_filter},{_drawtext_filter(caption)}"
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", image_path, "-t", str(duration_sec),
        "-vf", vf, "-pix_fmt", "yuv420p", "-r", str(_FPS), out_path,
    ], check=True, capture_output=True)


def _build_video_clip(video_path: str, duration_sec: float, caption: str, out_path: str) -> None:
    vf = f"scale={_WIDTH}:{_HEIGHT}:force_original_aspect_ratio=increase,crop={_WIDTH}:{_HEIGHT},{_drawtext_filter(caption)}"
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path, "-t", str(duration_sec),
        "-vf", vf, "-pix_fmt", "yuv420p", "-r", str(_FPS), "-an", out_path,
    ], check=True, capture_output=True)


def _concat_clips(clip_paths: list[str], work_dir: str, out_path: str) -> None:
    list_path = os.path.join(work_dir, "concat_list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for path in clip_paths:
            f.write(f"file '{os.path.abspath(path)}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path,
    ], check=True, capture_output=True)


def _probe_duration(path: str) -> float:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ], check=True, capture_output=True, text=True)
    return float(result.stdout.strip())


def _mix_music(video_path: str, music_path: str, out_path: str) -> None:
    video_duration = _probe_duration(video_path)
    music_duration = _probe_duration(music_path)
    if music_duration < video_duration:
        raise ValueError(
            f"Music track ({music_duration:.2f}s) is shorter than the "
            f"concatenated video ({video_duration:.2f}s); refusing to mix, "
            "as that would silently truncate the final video."
        )
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path, "-i", music_path,
        "-filter_complex", "[1:a]volume=0.5[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", out_path,
    ], check=True, capture_output=True)


def assemble_video(storyboard: dict, asset_paths: list[str], music_path: str,
                    out_path: str, work_dir: str = "work") -> str:
    os.makedirs(work_dir, exist_ok=True)
    beats = storyboard["beats"]
    if len(asset_paths) != len(beats):
        raise ValueError(
            f"asset_paths length ({len(asset_paths)}) does not match "
            f"beats length ({len(beats)}); refusing to silently truncate "
            "the assembled video."
        )
    clip_paths = []
    for i, (beat, asset_path) in enumerate(zip(beats, asset_paths)):
        clip_path = os.path.join(work_dir, f"beat_{i}.mp4")
        if beat["type"] == "still_pan":
            _build_still_clip(asset_path, beat["duration_sec"], beat["pan"], beat["caption"], clip_path)
        else:
            _build_video_clip(asset_path, beat["duration_sec"], beat["caption"], clip_path)
        clip_paths.append(clip_path)

    concatenated_path = os.path.join(work_dir, "concatenated.mp4")
    _concat_clips(clip_paths, work_dir, concatenated_path)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    _mix_music(concatenated_path, music_path, out_path)
    return out_path
