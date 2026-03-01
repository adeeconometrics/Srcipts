from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from argparse import ArgumentParser, ArgumentTypeError
from pathlib import Path


SUPPORTED_INPUT_EXTENSIONS = (".mov", ".mkv")


def validate_input(path_raw: str) -> Path:
    """Validate input path and enforce supported source file types."""
    path = Path(path_raw)
    if not path.exists() or not path.is_file():
        raise ArgumentTypeError(f"Input file does not exist: {path}")
    if path.suffix.lower() not in SUPPORTED_INPUT_EXTENSIONS:
        raise ArgumentTypeError(
            "Input must be one of: " + ", ".join(SUPPORTED_INPUT_EXTENSIONS)
        )
    return path


def normalize_stem(stem: str) -> str:
    """Keep only alphanumeric characters for deterministic default output names."""
    normalized = re.sub(r"[^A-Za-z0-9]", "", stem)
    return normalized or "Output"


def resolve_output_path(input_path: Path, output: str | None, out_format: str) -> Path:
    """Resolve output path from explicit path or default naming rule."""
    expected_suffix = f".{out_format}"
    if output is None:
        default_stem = f"{normalize_stem(input_path.stem)}Compressed"
        return input_path.with_name(f"{default_stem}{expected_suffix}")

    output_path = Path(output)
    if output_path.suffix == "":
        output_path = output_path.with_suffix(expected_suffix)
    elif output_path.suffix.lower() != expected_suffix:
        raise ValueError(
            f"Output extension must be {expected_suffix} for format '{out_format}'"
        )

    if not output_path.parent.exists():
        raise ValueError(f"Output directory does not exist: {output_path.parent}")

    return output_path


def run_ffmpeg(command: list[str]) -> None:
    """Run ffmpeg command and raise a readable error on failure."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg was not found in PATH") from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(
            f"ffmpeg failed with exit code {result.returncode}:\n{stderr}"
        )


def format_bytes(num_bytes: int) -> str:
    """Format bytes in a human-readable unit."""
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} TB"


def print_conversion_summary(input_path: Path, output_path: Path) -> None:
    """Display input/output files with size and reduction details."""
    raw_size = input_path.stat().st_size
    compressed_size = output_path.stat().st_size
    reduction = raw_size - compressed_size
    reduction_pct = (reduction / raw_size * 100.0) if raw_size > 0 else 0.0

    print(f"Raw:        {input_path} ({format_bytes(raw_size)})")
    print(f"Compressed: {output_path} ({format_bytes(compressed_size)})")
    print(
        "Saved:      "
        f"{format_bytes(abs(reduction))} "
        f"({'-' if reduction < 0 else ''}{abs(reduction_pct):.2f}%)"
    )


def print_batch_summary(
    total_raw_size: int, total_compressed_size: int, files_count: int
) -> None:
    """Display aggregate totals after a batch conversion run."""
    reduction = total_raw_size - total_compressed_size
    reduction_pct = (reduction / total_raw_size * 100.0) if total_raw_size > 0 else 0.0

    print("Batch summary")
    print(f"Files:       {files_count}")
    print(f"Raw total:   {format_bytes(total_raw_size)}")
    print(f"Output total:{format_bytes(total_compressed_size)}")
    print(
        "Saved total: "
        f"{format_bytes(abs(reduction))} "
        f"({'-' if reduction < 0 else ''}{abs(reduction_pct):.2f}%)"
    )


def compress_to_mp4(
    input_path: Path,
    output_path: Path,
    fps: int,
    crf: int,
    preset: str,
    keep_audio: bool,
    overwrite: bool,
) -> None:
    """Compress input video to MP4 with size-first defaults."""
    # libx264 with yuv420p requires even frame dimensions.
    video_filter = (
        f"fps={fps},"
        "scale=1280:720:force_original_aspect_ratio=decrease,"
        "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    )

    cmd = ["ffmpeg"]
    cmd.append("-y" if overwrite else "-n")
    cmd.extend(["-i", str(input_path)])
    cmd.extend(["-map", "0:v:0", "-map", "0:a:0?"])
    cmd.extend(["-vf", video_filter])
    cmd.extend(
        ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
    )

    if keep_audio:
        cmd.extend(
            [
                "-c:a",
                "aac",
                "-b:a",
                "96k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-af",
                "aresample=async=1:first_pts=0",
            ]
        )
    else:
        cmd.append("-an")

    cmd.extend(["-movflags", "+faststart", str(output_path)])
    run_ffmpeg(cmd)


def compress_to_gif(
    input_path: Path,
    output_path: Path,
    fps: int,
    gif_colors: int,
    overwrite: bool,
) -> None:
    """Compress input video to GIF using palette generation for better compression."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp_palette:
        palette_path = Path(tmp_palette.name)

        filter_base = f"fps={fps},scale=1280:720:force_original_aspect_ratio=decrease:flags=lanczos"

        cmd_palette = ["ffmpeg"]
        cmd_palette.append("-y" if overwrite else "-n")
        cmd_palette.extend(
            [
                "-i",
                str(input_path),
                "-vf",
                f"{filter_base},palettegen=max_colors={gif_colors}",
                str(palette_path),
            ]
        )
        run_ffmpeg(cmd_palette)

        cmd_gif = ["ffmpeg"]
        cmd_gif.append("-y" if overwrite else "-n")
        cmd_gif.extend(
            [
                "-i",
                str(input_path),
                "-i",
                str(palette_path),
                "-lavfi",
                f"{filter_base} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5",
                str(output_path),
            ]
        )
        run_ffmpeg(cmd_gif)


def parse_args() -> ArgumentParser:
    parser = ArgumentParser(
        description="Convert MOV/MKV files to compressed MP4 or GIF using ffmpeg"
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "-input", type=validate_input, help="Path to one input .mov or .mkv"
    )
    input_group.add_argument(
        "-inputs",
        nargs="+",
        type=validate_input,
        help="List of input .mov/.mkv files (batch mode)",
    )
    parser.add_argument(
        "--format",
        required=True,
        choices=["mp4", "gif"],
        help="Output format to produce (one output per run)",
    )
    parser.add_argument(
        "-output",
        required=False,
        help="Optional output path; defaults to <NormalizedBase>Compressed.<ext>",
    )
    parser.add_argument(
        "--output-dir",
        required=False,
        help="Optional output directory for generated files (useful in batch mode)",
    )
    parser.add_argument(
        "--fps", type=int, default=12, help="Target output FPS (default: 12)"
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=32,
        help="H.264 CRF for mp4 (0-51, higher means smaller file, default: 32)",
    )
    parser.add_argument(
        "--preset",
        default="veryslow",
        choices=[
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ],
        help="H.264 preset for mp4 compression efficiency (default: veryslow)",
    )
    parser.add_argument(
        "--gif-colors",
        type=int,
        default=64,
        help="Number of colors to keep in GIF palette (default: 64)",
    )
    parser.add_argument(
        "--keep-audio",
        dest="keep_audio",
        action="store_true",
        help="Keep audio in mp4 output (default)",
    )
    parser.add_argument(
        "--no-audio",
        dest="keep_audio",
        action="store_false",
        help="Disable audio in mp4 output for smaller files",
    )
    parser.set_defaults(keep_audio=True)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output file",
    )
    return parser


def main() -> int:
    parser = parse_args()
    args = parser.parse_args()

    try:
        if args.fps < 1:
            raise ValueError("--fps must be >= 1")
        if not 0 <= args.crf <= 51:
            raise ValueError("--crf must be between 0 and 51")
        if not 2 <= args.gif_colors <= 256:
            raise ValueError("--gif-colors must be between 2 and 256")

        input_paths = args.inputs if args.inputs else [args.input]

        if args.output and args.output_dir:
            raise ValueError("Use either -output or --output-dir, not both")
        if args.inputs and args.output:
            raise ValueError("-output cannot be used with -inputs batch mode")

        output_dir: Path | None = None
        if args.output_dir:
            output_dir = Path(args.output_dir)
            if not output_dir.exists() or not output_dir.is_dir():
                raise ValueError(f"Output directory does not exist: {output_dir}")

        total_raw_size = 0
        total_compressed_size = 0

        for input_path in input_paths:
            # In batch mode, outputs use either --output-dir or per-input default location.
            requested_output = None if args.inputs else args.output
            if output_dir is None:
                output_path = resolve_output_path(
                    input_path, requested_output, args.format
                )
            else:
                default_stem = f"{normalize_stem(input_path.stem)}Compressed"
                output_path = output_dir / f"{default_stem}.{args.format}"

            if output_path.exists() and not args.overwrite:
                raise ValueError(
                    f"Output already exists: {output_path}. Use --overwrite to replace it."
                )

            raw_size = input_path.stat().st_size

            if args.format == "mp4":
                compress_to_mp4(
                    input_path,
                    output_path,
                    fps=args.fps,
                    crf=args.crf,
                    preset=args.preset,
                    keep_audio=args.keep_audio,
                    overwrite=args.overwrite,
                )
            else:
                compress_to_gif(
                    input_path,
                    output_path,
                    fps=args.fps,
                    gif_colors=args.gif_colors,
                    overwrite=args.overwrite,
                )

            print(f"Created: {output_path}")
            print_conversion_summary(input_path, output_path)
            print()

            total_raw_size += raw_size
            total_compressed_size += output_path.stat().st_size

        if len(input_paths) > 1:
            print_batch_summary(total_raw_size, total_compressed_size, len(input_paths))
            print()

        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
