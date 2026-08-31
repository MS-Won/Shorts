"""ffmpeg assembly: beats in, one finished vertical Short out.

Pure subprocess work — this module never touches the network. Each beat becomes
a normalised 1080x1920 clip (a Ken Burns pan over a still, or a trimmed
generated clip), captions are burned in, the clips are concatenated, and the
music is mixed underneath.
"""

import os
import shutil
import subprocess
import textwrap

WIDTH = 1080
HEIGHT = 1920
FPS = 30

# Captions are the only text layer in v1 (no narration), so they have to be
# readable: drawtext does not wrap, so long lines are wrapped by hand.
CAPTION_FONT_SIZE = 64
CAPTION_WRAP_CHARS = 26

# drawtext needs an explicit font file. Relying on fontconfig fails outright on
# a stock Windows box ("Cannot load default config file"), which would take the
# captions — and the whole render — down with it.
FONT_CANDIDATES = (
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)

_PAN_FILTERS = {
    "in": "zoompan=z='min(zoom+0.0015,1.3)':d={frames}:s={w}x{h}:fps={fps}",
    "out": "zoompan=z='if(eq(on,1),1.3,max(1.3-0.0015*on,1.0))':d={frames}:s={w}x{h}:fps={fps}",
    "left": "zoompan=z=1.15:x='if(eq(on,1),iw*0.15,x-1)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    "right": "zoompan=z=1.15:x='if(eq(on,1),0,x+1)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
}


class AssemblyError(Exception):
    pass


def _resolve_font() -> str:
    override = os.environ.get("CAPTION_FONT")
    candidates = (override,) + FONT_CANDIDATES if override else FONT_CANDIDATES
    for path in candidates:
        if path and os.path.exists(path):
            return path
    raise AssemblyError(
        "no caption font found — set CAPTION_FONT to a .ttf path. Tried: "
        + ", ".join(FONT_CANDIDATES)
    )


def _escape_filter_path(path: str) -> str:
    """Escape a path for use *inside* an ffmpeg filter argument.

    Only filter arguments need this; `-i` paths are argv values and are passed
    through untouched. The colon in a Windows drive letter would otherwise be
    read as an option separator.
    """
    return path.replace("\\", "/").replace(":", r"\:")


def _run(cmd: list[str], cwd: str | None = None) -> None:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssemblyError(
            f"ffmpeg failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr[-2000:]}"
        )


def _write_caption_file(caption: str, work_dir: str, index: int) -> str:
    """Write the caption to a file next to the clip and return its basename.

    Passing the text through `textfile=` instead of `text=` means caption
    content never has to be escaped for the filter grammar at all — commas,
    colons and quotes are what LLM-written captions are full of.
    """
    name = f"caption_{index}.txt"
    wrapped = textwrap.fill(caption, width=CAPTION_WRAP_CHARS)
    with open(os.path.join(work_dir, name), "w", encoding="utf-8") as f:
        f.write(wrapped)
    return name


def _drawtext_filter(caption_file: str, font_path: str) -> str:
    # expansion=none: without it, drawtext reads '%' as a strftime escape and
    # errors out on any caption containing a percentage.
    return (
        f"drawtext=fontfile='{_escape_filter_path(font_path)}':"
        f"textfile={caption_file}:expansion=none:"
        f"fontcolor=white:fontsize={CAPTION_FONT_SIZE}:"
        "borderw=4:bordercolor=black:line_spacing=8:"
        "x=(w-text_w)/2:y=h-th-160"
    )


def _fit_filter() -> str:
    return (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT}"
    )


def _build_still_clip(image_path: str, duration_sec: float, pan: str, caption_file: str,
                      font_path: str, work_dir: str, out_path: str) -> None:
    if pan not in _PAN_FILTERS:
        raise AssemblyError(f"unknown pan direction {pan!r}")
    frames = int(duration_sec * FPS)
    pan_filter = _PAN_FILTERS[pan].format(frames=frames, w=WIDTH, h=HEIGHT, fps=FPS)
    vf = f"{_fit_filter()},{pan_filter},{_drawtext_filter(caption_file, font_path)}"
    _run([
        "ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", os.path.abspath(image_path),
        "-t", str(duration_sec), "-vf", vf, "-pix_fmt", "yuv420p", "-r", str(FPS),
        os.path.abspath(out_path),
    ], cwd=work_dir)


def _build_video_clip(video_path: str, duration_sec: float, caption_file: str,
                      font_path: str, work_dir: str, out_path: str) -> None:
    vf = f"{_fit_filter()},{_drawtext_filter(caption_file, font_path)}"
    _run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", os.path.abspath(video_path),
        "-t", str(duration_sec), "-vf", vf, "-pix_fmt", "yuv420p", "-r", str(FPS), "-an",
        os.path.abspath(out_path),
    ], cwd=work_dir)


def _concat_clips(clip_paths: list[str], work_dir: str, out_path: str) -> None:
    list_path = os.path.join(work_dir, "concat_list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for path in clip_paths:
            f.write("file '{}'\n".format(os.path.abspath(path).replace("\\", "/")))
    _run([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list_path,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path,
    ])


def _mix_music(video_path: str, music_path: str, out_path: str) -> None:
    # -stream_loop -1 on the music, not on the video: a track shorter than the
    # Short would otherwise cut the video off at the end of the track.
    _run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", video_path,
        "-stream_loop", "-1", "-i", music_path,
        "-filter_complex", "[1:a]volume=0.5[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", out_path,
    ])


def assemble_video(storyboard: dict, asset_paths: list[str], music_path: str,
                   out_path: str, work_dir: str = "work") -> str:
    if shutil.which("ffmpeg") is None:
        raise AssemblyError("ffmpeg is not on PATH")

    beats = storyboard["beats"]
    if len(asset_paths) != len(beats):
        raise AssemblyError(
            f"got {len(asset_paths)} assets for {len(beats)} beats — they must line up"
        )

    os.makedirs(work_dir, exist_ok=True)
    font_path = _resolve_font()

    clip_paths = []
    for i, (beat, asset_path) in enumerate(zip(beats, asset_paths)):
        caption_file = _write_caption_file(beat["caption"], work_dir, i)
        clip_path = os.path.join(work_dir, f"beat_{i}.mp4")
        if beat["type"] == "still_pan":
            _build_still_clip(asset_path, beat["duration_sec"], beat["pan"],
                              caption_file, font_path, work_dir, clip_path)
        else:
            _build_video_clip(asset_path, beat["duration_sec"],
                              caption_file, font_path, work_dir, clip_path)
        clip_paths.append(clip_path)

    concatenated_path = os.path.join(work_dir, "concatenated.mp4")
    _concat_clips(clip_paths, work_dir, concatenated_path)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    _mix_music(concatenated_path, music_path, out_path)
    return out_path
