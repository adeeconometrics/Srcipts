#!/usr/bin/env python3
"""
Benchmark utility for pixcomp compression modes.

Uses the generalized bench module to compare sequential vs parallel
execution modes for image compression.
"""

import argparse
from pathlib import Path
from functools import partial

from bench import (
    BenchmarkRunner,
    BenchmarkConfig,
    CleanupMode,
    benchmark,
)
from pixcomp import (
    compress,
    find_path,
    CompressionStrategy,
    ImageCompressor,
)


def create_compress_fn(
    input_dir: Path,
    output_format: str,
    strategy: CompressionStrategy,
    parallel: bool,
):
    """Create a compression function for benchmarking."""

    def _compress(output_dir: Path):
        compress(
            input_dir,
            output_dir,
            output_format=output_format,
            strategy=strategy,
            verbose=False,
            parallel=parallel,
        )

    return _compress


def run_pixcomp_benchmark(
    input_dir: Path,
    iterations: int = 3,
    strategy: CompressionStrategy = CompressionStrategy.VISUALLY_LOSSLESS,
    output_format: str = "webp",
    baseline: str = "sequential",
    warmup_runs: int = 0,
    cleanup_mode: CleanupMode = CleanupMode.AUTO,
    output_dir: Path | None = None,
):
    """
    Run pixcomp benchmark comparing sequential vs parallel modes.

    Args:
        input_dir: Directory containing images
        iterations: Number of iterations per mode
        strategy: Compression strategy
        output_format: Output format
        baseline: Mode to use as baseline
        warmup_runs: Warmup iterations (not timed)
        cleanup_mode: Cleanup strategy
        output_dir: Output directory for MANUAL/NONE cleanup modes
    """
    # Get file count
    compressor = ImageCompressor(output_format=output_format)
    files = find_path(input_dir, compressor.supported_extensions)
    num_files = len(files)

    if num_files == 0:
        print(f"❌ No supported image files found in {input_dir}")
        return None

    # Create benchmark config
    config = BenchmarkConfig(
        name=f"Pixcomp Compression ({output_format.upper()}, {strategy.name})",
        iterations=iterations,
        warmup_runs=warmup_runs,
        cleanup_mode=cleanup_mode,
        output_dir=output_dir,
        verbose=True,
    )

    # Create runner
    runner = BenchmarkRunner(config)

    # Register modes
    runner.register_mode(
        "sequential",
        create_compress_fn(input_dir, output_format, strategy, parallel=False),
    )
    runner.register_mode(
        "parallel",
        create_compress_fn(input_dir, output_format, strategy, parallel=True),
    )

    # Run benchmark
    result = runner.run(
        baseline=baseline,
        metadata={
            "input_dir": str(input_dir),
            "files": num_files,
            "format": output_format.upper(),
            "strategy": strategy.name,
        },
    )

    # Print results
    runner.print_results(result, units_label="files", units_count=num_files)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark pixcomp compression modes (sequential vs parallel)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Benchmark with default settings (3 iterations)
  python bench_pixcomp.py ./data/img/
  
  # Run 5 iterations with aggressive compression
  python bench_pixcomp.py ./data/img/ --iterations 5 --strategy aggressive
  
  # Use parallel as baseline for comparison
  python bench_pixcomp.py ./data/img/ --baseline parallel
  
  # Keep output files for inspection
  python bench_pixcomp.py ./data/img/ --cleanup none --output-dir ./bench_out/
  
  # Add warmup runs to stabilize results
  python bench_pixcomp.py ./data/img/ --warmup 1
        """,
    )

    parser.add_argument(
        "input_dir",
        type=str,
        help="Directory containing images to benchmark",
    )
    parser.add_argument(
        "--iterations",
        "-i",
        type=int,
        default=3,
        help="Number of iterations for each mode (default: 3)",
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
        "--format",
        "-f",
        type=str,
        default="webp",
        choices=["webp", "png", "jpeg", "jpg"],
        help="Output format (default: webp)",
    )
    parser.add_argument(
        "--baseline",
        "-b",
        type=str,
        default="sequential",
        choices=["sequential", "parallel"],
        help="Mode to use as baseline for speedup calculation (default: sequential)",
    )
    parser.add_argument(
        "--warmup",
        "-w",
        type=int,
        default=0,
        help="Number of warmup runs before timing (default: 0)",
    )
    parser.add_argument(
        "--cleanup",
        "-c",
        type=str,
        default="auto",
        choices=["auto", "manual", "none"],
        help="Cleanup mode: auto=temp dirs, manual=keep with structure, none=keep all",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Output directory for manual/none cleanup modes",
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

    # Map cleanup mode
    cleanup_map = {
        "auto": CleanupMode.AUTO,
        "manual": CleanupMode.MANUAL,
        "none": CleanupMode.NONE,
    }
    cleanup_mode = cleanup_map[args.cleanup]

    # Validate output_dir requirement
    output_dir = Path(args.output_dir) if args.output_dir else None
    if cleanup_mode in (CleanupMode.MANUAL, CleanupMode.NONE) and output_dir is None:
        print("❌ --output-dir is required when --cleanup is 'manual' or 'none'")
        return 1

    # Normalize format
    output_format = "jpeg" if args.format == "jpg" else args.format

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"❌ Directory not found: {input_dir}")
        return 1

    # Run benchmark
    run_pixcomp_benchmark(
        input_dir,
        iterations=args.iterations,
        strategy=strategy,
        output_format=output_format,
        baseline=args.baseline,
        warmup_runs=args.warmup,
        cleanup_mode=cleanup_mode,
        output_dir=output_dir,
    )

    return 0


if __name__ == "__main__":
    exit(main())
