from pathlib import Path
from typing import Union, Optional, Protocol, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import argparse
import os
import io

from PIL import Image, ExifTags

# Register HEIC/HEIF support with PIL
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_SUPPORTED = True
except ImportError:
    HEIF_SUPPORTED = False


# =============================================================================
# Metadata Extraction & Preservation
# =============================================================================


@dataclass
class ImageMetadata:
    """Container for all image metadata types."""

    exif: Optional[Any] = None
    icc_profile: Optional[bytes] = None
    xmp: Optional[bytes] = None
    iptc: Optional[Any] = None
    photoshop: Optional[Any] = None

    @classmethod
    def from_image(cls, img: Image.Image) -> "ImageMetadata":
        """Extract all available metadata from a PIL Image."""
        metadata = cls()

        # EXIF data
        try:
            metadata.exif = img.getexif()
            if not metadata.exif:
                metadata.exif = None
        except Exception:
            pass

        # ICC Color Profile
        try:
            metadata.icc_profile = img.info.get("icc_profile")
        except Exception:
            pass

        # XMP data
        try:
            metadata.xmp = img.info.get("xmp")
        except Exception:
            pass

        # IPTC data
        try:
            metadata.iptc = img.info.get("iptc")
        except Exception:
            pass

        # Photoshop data
        try:
            metadata.photoshop = img.info.get("photoshop")
        except Exception:
            pass

        return metadata

    def has_data(self) -> bool:
        """Check if any metadata is present."""
        return any([self.exif, self.icc_profile, self.xmp, self.iptc, self.photoshop])


# =============================================================================
# Compression Strategies
# =============================================================================


class CompressionStrategy(Enum):
    """Compression strategy selection."""

    LOSSLESS = auto()  # No quality loss, larger files
    VISUALLY_LOSSLESS = auto()  # Imperceptible loss, good compression
    BALANCED = auto()  # Good balance of quality/size
    AGGRESSIVE = auto()  # Maximum compression, some quality loss


@dataclass
class CompressionResult:
    """Result of a compression operation."""

    success: bool
    original_size: int
    compressed_size: int
    format_used: str
    error: Optional[str] = None

    @property
    def reduction_percent(self) -> float:
        if self.original_size == 0:
            return 0.0
        return ((self.original_size - self.compressed_size) / self.original_size) * 100

    @property
    def compression_ratio(self) -> float:
        if self.compressed_size == 0:
            return 0.0
        return self.original_size / self.compressed_size


# =============================================================================
# Media Compressor Protocol (for modularity)
# =============================================================================


class MediaCompressor(ABC):
    """Abstract base class for media compressors."""

    @property
    @abstractmethod
    def supported_extensions(self) -> tuple[str, ...]:
        """Return tuple of supported file extensions."""
        pass

    @abstractmethod
    def compress(
        self,
        src_path: Path,
        dst_path: Path,
        strategy: CompressionStrategy = CompressionStrategy.VISUALLY_LOSSLESS,
    ) -> CompressionResult:
        """Compress a media file with metadata preservation."""
        pass

    def supports(self, path: Path) -> bool:
        """Check if this compressor supports the given file."""
        return path.suffix.lower().lstrip(".") in self.supported_extensions


# =============================================================================
# Image Compressor Implementation
# =============================================================================


class ImageCompressor(MediaCompressor):
    """
    Advanced image compressor with full metadata preservation.

    Supports: JPEG, PNG, WebP, HEIC, HEIF, BMP, TIFF, DNG
    Preserves: EXIF, ICC profiles, XMP, IPTC
    """

    SUPPORTED_EXTENSIONS = (
        "jpg",
        "jpeg",
        "png",
        "bmp",
        "tiff",
        "tif",
        "webp",
        "heic",
        "heif",
        "dng",
    )

    # Strategy-specific quality settings
    QUALITY_SETTINGS = {
        CompressionStrategy.LOSSLESS: {"quality": 100, "lossless": True},
        CompressionStrategy.VISUALLY_LOSSLESS: {"quality": 95, "lossless": False},
        CompressionStrategy.BALANCED: {"quality": 85, "lossless": False},
        CompressionStrategy.AGGRESSIVE: {"quality": 70, "lossless": False},
    }

    def __init__(self, output_format: str = "jpeg"):
        self.output_format = output_format.lower()

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return self.SUPPORTED_EXTENSIONS

    def _analyze_image(self, img: Image.Image) -> dict[str, Any]:
        """Analyze image characteristics for optimal compression."""
        has_transparency = img.mode in ("RGBA", "LA", "PA") or (
            img.mode == "P" and "transparency" in img.info
        )
        is_photographic = self._is_photographic(img)

        return {
            "has_transparency": has_transparency,
            "is_photographic": is_photographic,
            "mode": img.mode,
            "size": img.size,
        }

    def _is_photographic(self, img: Image.Image) -> bool:
        """Heuristic to detect if image is photographic vs graphic/illustration."""
        # Sample colors to determine if image has photographic characteristics
        try:
            # Convert to RGB for analysis
            sample = img.convert("RGB")
            colors = sample.getcolors(maxcolors=10000)
            if colors is None:
                return True  # Many colors = likely photographic
            # Few distinct colors suggests graphic/illustration
            return len(colors) > 256
        except Exception:
            return True  # Default to photographic

    def _select_optimal_format(
        self,
        img: Image.Image,
        analysis: dict[str, Any],
        strategy: CompressionStrategy,
    ) -> str:
        """Select optimal output format based on image characteristics."""
        # If user specified format, respect it unless incompatible
        if self.output_format != "auto":
            return self.output_format

        # Auto-select based on content
        if analysis["has_transparency"]:
            if strategy == CompressionStrategy.LOSSLESS:
                return "png"
            return "webp"  # WebP handles transparency well

        if strategy == CompressionStrategy.LOSSLESS:
            return "webp"  # WebP lossless is smaller than PNG

        # For photographic content, WebP usually wins
        return "webp"

    def _build_save_params(
        self,
        img: Image.Image,
        format: str,
        strategy: CompressionStrategy,
        metadata: ImageMetadata,
    ) -> tuple[Image.Image, dict[str, Any]]:
        """Build optimized save parameters for the given format."""
        settings = self.QUALITY_SETTINGS[strategy]
        params: dict[str, Any] = {"format": format.upper()}
        processed_img = img

        if format == "webp":
            params.update(
                {
                    "lossless": settings["lossless"],
                    "quality": settings["quality"],
                    "method": 6,  # Best compression (0-6)
                }
            )
            if metadata.exif:
                params["exif"] = metadata.exif
            if metadata.icc_profile:
                params["icc_profile"] = metadata.icc_profile
            if metadata.xmp:
                params["xmp"] = metadata.xmp

        elif format == "png":
            params.update(
                {
                    "optimize": True,
                    "compress_level": 9,
                }
            )
            # PNG in Pillow doesn't support EXIF directly, use pnginfo
            if metadata.icc_profile:
                params["icc_profile"] = metadata.icc_profile

        elif format in ("jpeg", "jpg"):
            # JPEG doesn't support transparency
            if processed_img.mode in ("RGBA", "LA", "P", "PA"):
                # Create white background for transparency
                if processed_img.mode == "P":
                    processed_img = processed_img.convert("RGBA")
                background = Image.new("RGB", processed_img.size, (255, 255, 255))
                if processed_img.mode in ("RGBA", "LA", "PA"):
                    background.paste(processed_img, mask=processed_img.split()[-1])
                    processed_img = background
                else:
                    processed_img = processed_img.convert("RGB")
            elif processed_img.mode != "RGB":
                processed_img = processed_img.convert("RGB")

            params.update(
                {
                    "quality": settings["quality"],
                    "optimize": True,
                    "progressive": True,
                    "subsampling": 0
                    if settings["quality"] >= 90
                    else 2,  # 4:4:4 for high quality
                }
            )
            if metadata.exif:
                params["exif"] = metadata.exif
            if metadata.icc_profile:
                params["icc_profile"] = metadata.icc_profile

        else:
            # Fallback for other formats
            if metadata.exif:
                params["exif"] = metadata.exif

        return processed_img, params

    def compress(
        self,
        src_path: Path,
        dst_path: Path,
        strategy: CompressionStrategy = CompressionStrategy.VISUALLY_LOSSLESS,
    ) -> CompressionResult:
        """Compress an image with full metadata preservation."""
        try:
            original_size = src_path.stat().st_size

            # Open and analyze image
            with Image.open(src_path) as img:
                # Preserve original metadata
                metadata = ImageMetadata.from_image(img)
                analysis = self._analyze_image(img)

                # Select optimal format
                out_format = self._select_optimal_format(img, analysis, strategy)

                # Build save parameters
                processed_img, save_params = self._build_save_params(
                    img, out_format, strategy, metadata
                )

                # Update destination path with correct extension
                final_dst = dst_path.with_suffix(f".{out_format}")

                # Save with metadata
                processed_img.save(final_dst, **save_params)

            compressed_size = final_dst.stat().st_size

            return CompressionResult(
                success=True,
                original_size=original_size,
                compressed_size=compressed_size,
                format_used=out_format,
            )

        except Exception as e:
            return CompressionResult(
                success=False,
                original_size=src_path.stat().st_size if src_path.exists() else 0,
                compressed_size=0,
                format_used=self.output_format,
                error=str(e),
            )


# =============================================================================
# Utility Functions
# =============================================================================


def find_path(
    dir: Path, extension: Union[str, list[str], tuple[str, ...]] = "jpg"
) -> list[Path]:
    """Recursively find all files in `dir` with the given extension(s)."""
    if isinstance(extension, str):
        extensions = [extension.lower()]
    else:
        extensions = [ext.lower() for ext in extension]
    files: list[Path] = []
    for ext in extensions:
        files.extend(dir.rglob(f"*.{ext}"))
    return files


def get_compressor(
    media_type: str = "image", output_format: str = "webp"
) -> MediaCompressor:
    """Factory function to get the appropriate compressor."""
    compressors = {
        "image": ImageCompressor,
    }
    compressor_class = compressors.get(media_type, ImageCompressor)
    return compressor_class(output_format=output_format)


# =============================================================================
# Parallel Processing Helpers
# =============================================================================


def _compress_single_file(
    args: tuple[Path, Path, str, CompressionStrategy],
) -> tuple[Path, CompressionResult]:
    """
    Compress a single file. This function is defined at module level
    to be picklable for multiprocessing.

    Args:
        args: Tuple of (src_path, dst_path, output_format, strategy)

    Returns:
        Tuple of (source_path, CompressionResult)
    """
    src_path, dst_path, output_format, strategy = args
    compressor = ImageCompressor(output_format=output_format)
    result = compressor.compress(src_path, dst_path, strategy)
    return (src_path, result)


def _get_optimal_workers(max_workers: Optional[int] = None) -> int:
    """
    Determine optimal number of worker processes.

    Uses all available CPU cores by default, leaving one core free
    for system responsiveness on systems with many cores.

    Args:
        max_workers: Override for maximum workers (None = auto)

    Returns:
        Number of worker processes to use
    """
    if max_workers is not None:
        return max(1, max_workers)

    cpu_count = os.cpu_count() or 1

    # Use all cores for small core counts, leave 1 free for 8+ cores
    if cpu_count <= 4:
        return cpu_count
    elif cpu_count <= 8:
        return cpu_count - 1
    else:
        # For high core count systems, use ~90% of cores
        return max(1, int(cpu_count * 0.9))


# =============================================================================
# Batch Processing
# =============================================================================


@dataclass
class BatchResult:
    """Summary of batch compression results."""

    total_files: int
    success_count: int
    failed_count: int
    total_original_size: int
    total_compressed_size: int
    results: list[tuple[Path, CompressionResult]]

    @property
    def reduction_percent(self) -> float:
        if self.total_original_size == 0:
            return 0.0
        return (
            (self.total_original_size - self.total_compressed_size)
            / self.total_original_size
        ) * 100

    def print_summary(self) -> None:
        """Print a formatted summary of the batch operation."""
        print(f"\n{'=' * 60}")
        print(f"Processed: {self.success_count}/{self.total_files} files")
        if self.failed_count > 0:
            print(f"Failed: {self.failed_count} files")
        print(
            f"Total: {self.total_original_size:,} → {self.total_compressed_size:,} bytes"
        )
        print(f"Overall reduction: {self.reduction_percent:.1f}%")
        print(
            f"Space saved: {(self.total_original_size - self.total_compressed_size):,} bytes"
        )
        print(f"{'=' * 60}")


def batch_compress(
    files: list[Path],
    outdir: Union[Path, str],
    output_format: str = "webp",
    strategy: CompressionStrategy = CompressionStrategy.VISUALLY_LOSSLESS,
    verbose: bool = True,
    parallel: bool = False,
    max_workers: Optional[int] = None,
) -> BatchResult:
    """
    Compress a batch of media files with metadata preservation.

    Args:
        files: List of file paths to compress
        outdir: Output directory for compressed files
        output_format: Output format ('webp', 'png', 'jpeg', 'auto')
        strategy: Compression strategy to use
        verbose: Print progress for each file
        parallel: Use parallel multiprocessing for faster compression
        max_workers: Maximum worker processes (None = auto-detect optimal)

    Returns:
        BatchResult with summary statistics
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if parallel:
        return _batch_compress_parallel(
            files, outdir, output_format, strategy, verbose, max_workers
        )
    else:
        return _batch_compress_sequential(
            files, outdir, output_format, strategy, verbose
        )


def _batch_compress_sequential(
    files: list[Path],
    outdir: Path,
    output_format: str,
    strategy: CompressionStrategy,
    verbose: bool,
) -> BatchResult:
    """Sequential (single-threaded) batch compression."""
    compressor = get_compressor("image", output_format)

    total_original_size = 0
    total_compressed_size = 0
    success_count = 0
    failed_count = 0
    results: list[tuple[Path, CompressionResult]] = []

    for file in files:
        out_file = outdir / file.stem
        result = compressor.compress(file, out_file, strategy)
        results.append((file, result))

        if result.success:
            total_original_size += result.original_size
            total_compressed_size += result.compressed_size
            success_count += 1

            if verbose:
                print(f"✓ {file.name} → .{result.format_used}")
                print(
                    f"  {result.original_size:,} → {result.compressed_size:,} bytes "
                    f"({result.reduction_percent:.1f}% reduction)"
                )
        else:
            failed_count += 1
            if verbose:
                print(f"✗ {file.name}: {result.error}")

    return BatchResult(
        total_files=len(files),
        success_count=success_count,
        failed_count=failed_count,
        total_original_size=total_original_size,
        total_compressed_size=total_compressed_size,
        results=results,
    )


def _batch_compress_parallel(
    files: list[Path],
    outdir: Path,
    output_format: str,
    strategy: CompressionStrategy,
    verbose: bool,
    max_workers: Optional[int] = None,
) -> BatchResult:
    """
    Parallel batch compression using ProcessPoolExecutor.

    Maximizes CPU core utilization for CPU-bound image compression tasks.
    """
    num_workers = _get_optimal_workers(max_workers)

    if verbose:
        print(f"🚀 Parallel mode: {num_workers} worker processes\n")

    # Prepare task arguments
    tasks = [(file, outdir / file.stem, output_format, strategy) for file in files]

    total_original_size = 0
    total_compressed_size = 0
    success_count = 0
    failed_count = 0
    results: list[tuple[Path, CompressionResult]] = []

    # Use spawn context for clean process creation (recommended for Py3.12+)
    ctx = multiprocessing.get_context("spawn")

    with ProcessPoolExecutor(max_workers=num_workers, mp_context=ctx) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(_compress_single_file, task): task[0] for task in tasks
        }

        # Process results as they complete
        for future in as_completed(future_to_file):
            src_file = future_to_file[future]
            try:
                file_path, result = future.result()
                results.append((file_path, result))

                if result.success:
                    total_original_size += result.original_size
                    total_compressed_size += result.compressed_size
                    success_count += 1

                    if verbose:
                        print(f"✓ {file_path.name} → .{result.format_used}")
                        print(
                            f"  {result.original_size:,} → {result.compressed_size:,} bytes "
                            f"({result.reduction_percent:.1f}% reduction)"
                        )
                else:
                    failed_count += 1
                    if verbose:
                        print(f"✗ {file_path.name}: {result.error}")

            except Exception as e:
                failed_count += 1
                if verbose:
                    print(f"✗ {src_file.name}: Process error - {e}")
                results.append(
                    (
                        src_file,
                        CompressionResult(
                            success=False,
                            original_size=0,
                            compressed_size=0,
                            format_used=output_format,
                            error=str(e),
                        ),
                    )
                )

    return BatchResult(
        total_files=len(files),
        success_count=success_count,
        failed_count=failed_count,
        total_original_size=total_original_size,
        total_compressed_size=total_compressed_size,
        results=results,
    )


# =============================================================================
# Main Compress Function
# =============================================================================


def compress(
    dir: Path,
    outdir: Path,
    output_format: str = "webp",
    strategy: CompressionStrategy = CompressionStrategy.VISUALLY_LOSSLESS,
    verbose: bool = True,
    parallel: bool = False,
    max_workers: Optional[int] = None,
) -> BatchResult:
    """
    Find media files in `dir` and compress them to `outdir` with metadata preservation.

    Args:
        dir: Input directory containing media files
        outdir: Output directory for compressed files
        output_format: Output format ('webp', 'png', 'jpeg', 'auto')
        strategy: Compression strategy (LOSSLESS, VISUALLY_LOSSLESS, BALANCED, AGGRESSIVE)
        verbose: Print progress messages
        parallel: Use multiprocessing for faster compression
        max_workers: Maximum worker processes (None = auto-detect based on CPU cores)

    Returns:
        BatchResult with compression statistics
    """
    compressor = get_compressor("image", output_format)
    files = find_path(dir, compressor.supported_extensions)

    if not files:
        print(f"No supported files found in {dir}")
        return BatchResult(0, 0, 0, 0, 0, [])

    mode = "parallel" if parallel else "sequential"
    print(f"Found {len(files)} files to compress...")
    print(
        f"Format: {output_format.upper()} | Strategy: {strategy.name} | Mode: {mode}\n"
    )

    result = batch_compress(
        files, outdir, output_format, strategy, verbose, parallel, max_workers
    )
    result.print_summary()

    return result


# =============================================================================
# CLI Entry Point
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Compress media files with optimal compression and full metadata preservation. "
        "Supports JPEG, PNG, WebP, HEIC, HEIF, BMP, TIFF, DNG.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Compression Strategies:
  lossless         No quality loss, larger files (WebP lossless, PNG)
  visually-lossless Imperceptible quality loss, good compression (default)
  balanced         Good balance of quality and size (quality ~85)
  aggressive       Maximum compression, noticeable quality loss

Examples:
  # Visually lossless WebP (recommended - best quality/size ratio)
  python pixcomp.py ~/Pictures/Photos ~/Pictures/Compressed
  
  # Lossless compression (no quality loss)
  python pixcomp.py ~/Pictures/Photos ~/Pictures/Compressed --strategy lossless
  
  # Maximum compression (smaller files, some quality loss)
  python pixcomp.py ~/Pictures/Photos ~/Pictures/Compressed --strategy aggressive
  
  # Output as JPEG with balanced compression
  python pixcomp.py ~/Pictures/Photos ~/Pictures/Compressed --format jpeg --strategy balanced

Parallel Processing:
  # Use all CPU cores for maximum speed
  python pixcomp.py ~/Pictures/Photos ~/Pictures/Compressed --parallel
  
  # Limit to 4 worker processes
  python pixcomp.py ~/Pictures/Photos ~/Pictures/Compressed --parallel --workers 4

Metadata Preserved:
  - EXIF (camera info, date, GPS, etc.)
  - ICC Color Profiles
  - XMP (editing history, ratings, etc.)
  - IPTC (copyright, captions, keywords)
        """,
    )

    parser.add_argument("dir", type=str, help="Input directory containing media files")
    parser.add_argument(
        "outdir", type=str, help="Output directory for compressed files"
    )
    parser.add_argument(
        "--format",
        "-f",
        type=str,
        default="webp",
        choices=["webp", "png", "jpeg", "jpg", "auto"],
        help="Output format (default: webp - best compression ratio)",
    )
    parser.add_argument(
        "--strategy",
        "-s",
        type=str,
        default="visually-lossless",
        choices=["lossless", "visually-lossless", "balanced", "aggressive"],
        help="Compression strategy (default: visually-lossless)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only show summary, not individual file progress",
    )
    parser.add_argument(
        "--parallel",
        "-p",
        action="store_true",
        help="Enable parallel multiprocessing to maximize CPU utilization",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=None,
        help="Number of worker processes for parallel mode (default: auto-detect)",
    )

    args = parser.parse_args()

    # Map strategy string to enum
    strategy_map = {
        "lossless": CompressionStrategy.LOSSLESS,
        "visually-lossless": CompressionStrategy.VISUALLY_LOSSLESS,
        "balanced": CompressionStrategy.BALANCED,
        "aggressive": CompressionStrategy.AGGRESSIVE,
    }
    strategy = strategy_map[args.strategy]

    # Normalize format
    output_format = "jpeg" if args.format == "jpg" else args.format

    compress(
        Path(args.dir),
        Path(args.outdir),
        output_format,
        strategy,
        verbose=not args.quiet,
        parallel=args.parallel,
        max_workers=args.workers,
    )


if __name__ == "__main__":
    main()
