"""
Script registry and configuration for srcipts.

This module defines all available scripts, their dependencies,
and metadata for discovery and execution.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class ScriptConfig:
    """Configuration for a script."""

    name: str
    module: str
    description: str
    extras: List[str]
    example: str


# Registry of all available scripts
SCRIPTS = {
    "pixcomp": ScriptConfig(
        name="pixcomp",
        module="pixcomp",
        description="Compress images using PIL with customizable quality and formats",
        extras=["pixcomp"],
        example="srcipts pixcomp ./images ./output --method webp",
    ),
    "cupixcomp": ScriptConfig(
        name="cupixcomp",
        module="cupixcomp",
        description="CUDA-accelerated image compression with multiple algorithms",
        extras=["cupixcomp"],
        example="srcipts cupixcomp compress ./images ./output --compressor lz4",
    ),
    "vid2gif": ScriptConfig(
        name="vid2gif",
        module="vid2gif",
        description="Convert video files to animated GIFs",
        extras=["vid2gif"],
        example="srcipts vid2gif -input video.mp4 -output output.gif",
    ),
    "movcomp": ScriptConfig(
        name="movcomp",
        module="movcomp",
        description="Convert MOV files to compressed MP4 or GIF via ffmpeg",
        extras=[],
        example="srcipts movcomp -input video.mov --format mp4",
    ),
    "pdf2xls": ScriptConfig(
        name="pdf2xls",
        module="pdf2xls",
        description="Extract tables from PDFs and convert to Excel or Markdown",
        extras=["pdf2xls"],
        example="srcipts pdf2xls -input document.pdf -output document.xlsx",
    ),
    "downloader": ScriptConfig(
        name="downloader",
        module="downloader",
        description="Download videos from YouTube",
        extras=["downloader"],
        example='srcipts downloader -url "https://youtube.com/..." -output ~/Downloads',
    ),
}


def get_script(name: str) -> ScriptConfig | None:
    """Get script configuration by name."""
    return SCRIPTS.get(name)


def list_scripts() -> List[ScriptConfig]:
    """Get list of all available scripts."""
    return list(SCRIPTS.values())
