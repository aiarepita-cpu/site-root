#!/usr/bin/env python3
"""Descarga reels de Instagram y los convierte en mosaicos de frames legibles.

Los reels de trading traen subtitulos quemados en pantalla, asi que los frames
contienen tanto el grafico como la narracion: no hace falta transcribir audio.

Uso:
    python3 extract_reels.py <url_o_shortcode> [...]
    python3 extract_reels.py --urls-file urls.txt
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

OUT = Path(__file__).parent / "out"
FRAME_EVERY_SEC = 3
COLS, ROWS = 3, 4          # 12 frames por mosaico
TILE_WIDTH = 460           # ancho de cada frame dentro del mosaico


def ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def shortcode(url: str) -> str:
    m = re.search(r"/(?:reel|reels|p)/([A-Za-z0-9_-]{8,15})", url)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{8,15}", url):
        return url
    raise ValueError(f"No pude extraer el shortcode de: {url}")


def download(code: str, dest: Path) -> Path | None:
    video = dest / f"{code}.mp4"
    if video.exists():
        return video
    url = f"https://www.instagram.com/reel/{code}/"
    r = subprocess.run(
        ["yt-dlp", "--no-warnings", "-o", str(dest / "%(id)s.%(ext)s"), url],
        capture_output=True, text=True, timeout=300,
    )
    if not video.exists():
        print(f"  ERROR descargando {code}: {r.stderr.strip().splitlines()[-1:]}", file=sys.stderr)
        return None
    return video


def duration_sec(video: Path) -> float:
    out = subprocess.run([ffmpeg(), "-i", str(video)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", out)
    if not m:
        return 0.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def make_sheets(video: Path, code: str) -> list[Path]:
    """Extrae frames y los agrupa en mosaicos de COLS x ROWS."""
    frames_dir = video.parent / f"frames_{code}"
    frames_dir.mkdir(exist_ok=True)
    subprocess.run([
        ffmpeg(), "-v", "error", "-y", "-i", str(video),
        "-vf", f"fps=1/{FRAME_EVERY_SEC},scale={TILE_WIDTH}:-2",
        "-q:v", "3", str(frames_dir / "f_%03d.jpg"),
    ], check=True)

    frames = sorted(frames_dir.glob("f_*.jpg"))
    if not frames:
        return []

    per_sheet = COLS * ROWS
    sheets = []
    for idx in range(0, len(frames), per_sheet):
        chunk = frames[idx:idx + per_sheet]
        sheet = video.parent / f"sheet_{code}_{idx // per_sheet + 1}.jpg"
        subprocess.run([
            ffmpeg(), "-v", "error", "-y", "-pattern_type", "glob",
            "-i", str(frames_dir / "f_*.jpg"),
            "-vf", f"select='between(n\\,{idx}\\,{idx + len(chunk) - 1})',"
                   f"tile={COLS}x{ROWS}:padding=6:color=0x444444",
            "-frames:v", "1", "-q:v", "4", str(sheet),
        ], check=True)
        sheets.append(sheet)
    return sheets


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--urls-file")
    args = ap.parse_args()

    urls = list(args.urls)
    if args.urls_file:
        urls += [l.strip() for l in Path(args.urls_file).read_text().split() if l.strip()]
    if not urls:
        ap.error("hacen falta URLs o --urls-file")

    OUT.mkdir(parents=True, exist_ok=True)
    for url in urls:
        code = shortcode(url)
        print(f"\n== {code} ==")
        video = download(code, OUT)
        if video is None:
            continue
        dur = duration_sec(video)
        sheets = make_sheets(video, code)
        print(f"  {dur:.0f}s -> {len(sheets)} mosaico(s)")
        for s in sheets:
            print(f"  {s}")


if __name__ == "__main__":
    main()
