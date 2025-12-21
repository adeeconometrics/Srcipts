#!/usr/bin/env python3
"""
Benchmark utility for pixcomp compression modes.

Compares performance of sequential vs parallel execution modes,
measuring execution time and relative speedup.
"""

import time
import argparse
from pathlib import Path
from statistics import mean, stdev
from typing import Optional
import tempfile
import shutil

from tabulate import tabulate

from pixcomp import (
    compress,
    find_path,
    CompressionStrategy,
    ImageCompressor,
)


def run_benchmark(
    input_dir: Path,
    iterations: int = 3,
    strategy: CompressionStrategy = CompressionStrategy.VISUALLY_LOSSLESS,
    output_format: str = "webp",
) -> dict:
    """
    Run comprehensive benchmark comparing sequential vs parallel modes.

    Args:
        input_dir: Directory containing images to compress
        iterations: Number of times to run each mode
        strategy: Compression strategy to use
        output_format: Output format for compressed images

    Returns:
        Dictionary with benchmark results
    """
    compressor = ImageCompressor(output_format=output_format)
    files = find_path(input_dir, compressor.supported_extensions)

    if not files:
        print(f"❌ No image files found in {input_dir}")
        return {}

    print(f"\n{'=' * 70}")
    print(f"Benchmark Configuration")
    print(f"{'=' * 70}")
    print(f"Input directory: {input_dir}")
    print(f"Files found: {len(files)}")
    print(f"Format: {output_format.upper()}")
    print(f"Strategy: {strategy.name}")
    print(f"Iterations: {iterations}")
    print(f"{'=' * 70}\n")

    results = {
        "sequential": [],
        "parallel": [],
    }

    # Benchmark sequential mode
    print(f"Running sequential benchmark ({iterations} iterations)...")
    for i in range(iterations):
        with tempfile.TemporaryDirectory() as tmpdir:
            start_time = time.perf_counter()
            compress(
                input_dir,
                Path(tmpdir),
                output_format=output_format,
                strategy=strategy,
                verbose=False,
                parallel=False,
            )
            elapsed = time.perf_counter() - start_time
            results["sequential"].append(elapsed)
            print(f"  Iteration {i + 1}: {elapsed:.2f}s")

    # Benchmark parallel mode
    print(f"\nRunning parallel benchmark ({iterations} iterations)...")
    for i in range(iterations):
        with tempfile.TemporaryDirectory() as tmpdir:
            start_time = time.perf_counter()
            compress(
                input_dir,
                Path(tmpdir),
                output_format=output_format,
                strategy=strategy,
                verbose=False,
                parallel=True,
            )
            elapsed = time.perf_counter() - start_time
            results["parallel"].append(elapsed)
            print(f"  Iteration {i + 1}: {elapsed:.2f}s")

    return results


def format_benchmark_results(results: dict, num_files: int) -> None:
    """
    Format and display benchmark results using tabulate.

    Args:
        results: Dictionary with sequential and parallel timings
        num_files: Number of files processed
    """
    if not results:
        return

    seq_times = results["sequential"]
    par_times = results["parallel"]

    # Calculate statistics
    seq_mean = mean(seq_times)
    seq_stdev = stdev(seq_times) if len(seq_times) > 1 else 0.0

    par_mean = mean(par_times)
    par_stdev = stdev(par_times) if len(par_times) > 1 else 0.0

    # Calculate speedup
    speedup = seq_mean / par_mean
    speedup_percent = ((seq_mean - par_mean) / seq_mean) * 100

    # Per-file metrics
    seq_per_file = seq_mean / num_files
    par_per_file = par_mean / num_files

    # Build results table
    table_data = [
        [
            "Sequential",
            f"{seq_mean:.3f}s",
            f"±{seq_stdev:.3f}s",
            f"{seq_per_file:.3f}s",
            "1.00x (baseline)",
        ],
        [
            "Parallel",
            f"{par_mean:.3f}s",
            f"±{par_stdev:.3f}s",
            f"{par_per_file:.3f}s",
            f"{speedup:.2f}x ({speedup_percent:+.1f}%)",
        ],
    ]

    headers = [
        "Mode",
        "Avg Time",
        "Std Dev",
        "Time/File",
        "Relative Speed",
    ]

    print(f"\n{'=' * 70}")
    print("Benchmark Results")
    print(f"{'=' * 70}\n")
    print(
        tabulate(
            table_data,
            headers=headers,
            tablefmt="grid",
            stralign="center",
        )
    )

    print(f"\n{'=' * 70}")
    print("Summary")
    print(f"{'=' * 70}")

    if speedup > 1.0:
        print(f"✅ Parallel mode is {speedup:.2f}x faster")
        print(f"   Speedup: {speedup_percent:.1f}% faster than sequential")
        print(f"   Time saved per run: {(seq_mean - par_mean):.2f}s")
    else:
        print(f"⚠️  Sequential mode is {abs(speedup):.2f}x faster")
        print(f"   Sequential is {abs(speedup_percent):.1f}% faster than parallel")
        print(f"   Overhead: {(par_mean - seq_mean):.2f}s per run")

    print(f"\nTotal files processed per iteration: {num_files}")
    print(
        f"Sequential total time: {seq_mean * len(seq_times):.2f}s ({len(seq_times)} runs)"
    )
    print(
        f"Parallel total time: {par_mean * len(par_times):.2f}s ({len(par_times)} runs)"
    )
    print(f"{'=' * 70}\n")


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
  
  # Benchmark with JPEG output
  python bench_pixcomp.py ~/Pictures/Photos --format jpeg --iterations 10
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

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"❌ Directory not found: {input_dir}")
        return 1

    # Get file count
    compressor = ImageCompressor()
    files = find_path(input_dir, compressor.supported_extensions)
    num_files = len(files)

    if num_files == 0:
        print(f"❌ No supported image files found in {input_dir}")
        return 1

    # Run benchmark
    results = run_benchmark(
        input_dir,
        iterations=args.iterations,
        strategy=strategy,
        output_format=output_format,
    )

    # Format and display results
    format_benchmark_results(results, num_files)

    return 0


if __name__ == "__main__":
    exit(main())
