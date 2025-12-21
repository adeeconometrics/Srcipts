#!/usr/bin/env python3
"""
General-purpose benchmark utility for comparing execution modes.

Provides a reusable framework for measuring and comparing performance
of different execution strategies (e.g., sequential vs parallel,
different algorithms, configurations).

Features:
- Configurable number of iterations with statistical analysis
- Automatic or manual cleanup of generated artifacts
- Customizable baseline for relative speed comparison
- Rich tabulated output with mean, stdev, min, max, relative speed
- Reusable as a module or standalone CLI tool
"""

import time
import argparse
import tempfile
import shutil
from pathlib import Path
from statistics import mean, stdev
from dataclasses import dataclass, field
from typing import Callable, Optional, Any
from enum import Enum, auto

from tabulate import tabulate


# =============================================================================
# Benchmark Data Structures
# =============================================================================


class CleanupMode(Enum):
    """Cleanup strategy for benchmark artifacts."""

    AUTO = auto()  # Use temp directories, auto-cleanup
    MANUAL = auto()  # User manages cleanup
    NONE = auto()  # No cleanup (keep all outputs)


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""

    name: str
    iterations: int = 3
    warmup_runs: int = 0
    cleanup_mode: CleanupMode = CleanupMode.AUTO
    output_dir: Optional[Path] = None
    verbose: bool = True

    def __post_init__(self):
        if self.cleanup_mode == CleanupMode.MANUAL and self.output_dir is None:
            raise ValueError("output_dir required when cleanup_mode is MANUAL")


@dataclass
class TimingResult:
    """Timing statistics for a single benchmark mode."""

    name: str
    times: list[float] = field(default_factory=list)

    @property
    def mean(self) -> float:
        return mean(self.times) if self.times else 0.0

    @property
    def stdev(self) -> float:
        return stdev(self.times) if len(self.times) > 1 else 0.0

    @property
    def min(self) -> float:
        return min(self.times) if self.times else 0.0

    @property
    def max(self) -> float:
        return max(self.times) if self.times else 0.0

    @property
    def total(self) -> float:
        return sum(self.times)

    @property
    def count(self) -> int:
        return len(self.times)


@dataclass
class BenchmarkResult:
    """Complete benchmark results with all modes."""

    config: BenchmarkConfig
    results: dict[str, TimingResult] = field(default_factory=dict)
    baseline: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_timing(self, mode: str, elapsed: float) -> None:
        """Add a timing measurement for a mode."""
        if mode not in self.results:
            self.results[mode] = TimingResult(name=mode)
        self.results[mode].times.append(elapsed)

    def get_speedup(self, mode: str) -> tuple[float, float]:
        """
        Calculate speedup relative to baseline.

        Returns:
            Tuple of (speedup_factor, speedup_percent)
        """
        if not self.baseline or self.baseline not in self.results:
            return (1.0, 0.0)

        baseline_mean = self.results[self.baseline].mean
        mode_mean = self.results[mode].mean

        if mode_mean == 0:
            return (float("inf"), 100.0)

        speedup = baseline_mean / mode_mean
        speedup_percent = ((baseline_mean - mode_mean) / baseline_mean) * 100

        return (speedup, speedup_percent)


# =============================================================================
# Benchmark Runner
# =============================================================================


class BenchmarkRunner:
    """
    Generalized benchmark runner for comparing execution modes.

    Usage:
        runner = BenchmarkRunner(config)
        runner.register_mode("sequential", my_sequential_func)
        runner.register_mode("parallel", my_parallel_func)
        result = runner.run(baseline="sequential")
        runner.print_results(result)
    """

    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.modes: dict[str, Callable[..., Any]] = {}
        self.mode_kwargs: dict[str, dict] = {}
        self.setup_fn: Optional[Callable[[], Any]] = None
        self.teardown_fn: Optional[Callable[[Any], None]] = None
        self.cleanup_fn: Optional[Callable[[Path], None]] = None

    def register_mode(
        self,
        name: str,
        func: Callable[..., Any],
        **kwargs,
    ) -> "BenchmarkRunner":
        """
        Register an execution mode to benchmark.

        Args:
            name: Mode identifier
            func: Callable to benchmark (should accept output_dir as first arg)
            **kwargs: Additional kwargs to pass to the function

        Returns:
            Self for method chaining
        """
        self.modes[name] = func
        self.mode_kwargs[name] = kwargs
        return self

    def set_setup(self, func: Callable[[], Any]) -> "BenchmarkRunner":
        """Set a setup function to run before each iteration."""
        self.setup_fn = func
        return self

    def set_teardown(self, func: Callable[[Any], None]) -> "BenchmarkRunner":
        """Set a teardown function to run after each iteration."""
        self.teardown_fn = func
        return self

    def set_cleanup(self, func: Callable[[Path], None]) -> "BenchmarkRunner":
        """Set a custom cleanup function for output directories."""
        self.cleanup_fn = func
        return self

    def _get_output_dir(self, mode: str, iteration: int) -> tuple[Path, bool]:
        """
        Get output directory based on cleanup mode.

        Returns:
            Tuple of (output_path, is_temp)
        """
        if self.config.cleanup_mode == CleanupMode.AUTO:
            # Will be handled by context manager
            return (Path(tempfile.mkdtemp()), True)
        elif self.config.cleanup_mode == CleanupMode.MANUAL:
            out_dir = self.config.output_dir / f"{mode}_iter{iteration + 1}"
            out_dir.mkdir(parents=True, exist_ok=True)
            return (out_dir, False)
        else:  # NONE
            out_dir = self.config.output_dir / f"{mode}_iter{iteration + 1}"
            out_dir.mkdir(parents=True, exist_ok=True)
            return (out_dir, False)

    def _cleanup_dir(self, path: Path) -> None:
        """Clean up a directory."""
        if self.cleanup_fn:
            self.cleanup_fn(path)
        elif path.exists():
            shutil.rmtree(path, ignore_errors=True)

    def run(
        self,
        baseline: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> BenchmarkResult:
        """
        Run the benchmark for all registered modes.

        Args:
            baseline: Mode to use as baseline for speedup calculation
            metadata: Additional metadata to include in results

        Returns:
            BenchmarkResult with all timing data
        """
        if not self.modes:
            raise ValueError("No modes registered. Use register_mode() first.")

        # Use first mode as baseline if not specified
        if baseline is None:
            baseline = next(iter(self.modes.keys()))

        result = BenchmarkResult(
            config=self.config,
            baseline=baseline,
            metadata=metadata or {},
        )

        if self.config.verbose:
            self._print_header()

        for mode_name, mode_func in self.modes.items():
            if self.config.verbose:
                print(
                    f"\nRunning '{mode_name}' ({self.config.iterations} iterations)..."
                )

            # Warmup runs
            for _ in range(self.config.warmup_runs):
                out_dir, is_temp = self._get_output_dir(mode_name, -1)
                try:
                    mode_func(out_dir, **self.mode_kwargs.get(mode_name, {}))
                finally:
                    if is_temp or self.config.cleanup_mode == CleanupMode.AUTO:
                        self._cleanup_dir(out_dir)

            # Timed runs
            for i in range(self.config.iterations):
                out_dir, is_temp = self._get_output_dir(mode_name, i)

                # Setup
                setup_result = None
                if self.setup_fn:
                    setup_result = self.setup_fn()

                try:
                    # Time the execution
                    start_time = time.perf_counter()
                    mode_func(out_dir, **self.mode_kwargs.get(mode_name, {}))
                    elapsed = time.perf_counter() - start_time

                    result.add_timing(mode_name, elapsed)

                    if self.config.verbose:
                        print(f"  Iteration {i + 1}: {elapsed:.3f}s")

                finally:
                    # Teardown
                    if self.teardown_fn:
                        self.teardown_fn(setup_result)

                    # Cleanup
                    if is_temp or self.config.cleanup_mode == CleanupMode.AUTO:
                        self._cleanup_dir(out_dir)

        return result

    def _print_header(self) -> None:
        """Print benchmark configuration header."""
        print(f"\n{'=' * 70}")
        print(f"Benchmark: {self.config.name}")
        print(f"{'=' * 70}")
        print(f"Iterations: {self.config.iterations}")
        if self.config.warmup_runs:
            print(f"Warmup runs: {self.config.warmup_runs}")
        print(f"Cleanup mode: {self.config.cleanup_mode.name}")
        print(f"Modes to test: {', '.join(self.modes.keys())}")
        print(f"{'=' * 70}")

    def print_results(
        self,
        result: BenchmarkResult,
        units_label: str = "ops",
        units_count: Optional[int] = None,
    ) -> None:
        """
        Print formatted benchmark results.

        Args:
            result: BenchmarkResult from run()
            units_label: Label for per-unit metrics (e.g., "files", "ops")
            units_count: Number of units processed (for per-unit stats)
        """
        if not result.results:
            print("No results to display.")
            return

        # Build table data
        table_data = []
        baseline_name = result.baseline

        for mode_name, timing in result.results.items():
            speedup, speedup_pct = result.get_speedup(mode_name)

            if mode_name == baseline_name:
                speed_str = "1.00x (baseline)"
            elif speedup >= 1.0:
                speed_str = f"{speedup:.2f}x ({speedup_pct:+.1f}%)"
            else:
                speed_str = f"{speedup:.2f}x ({speedup_pct:+.1f}%)"

            row = [
                mode_name,
                f"{timing.mean:.3f}s",
                f"±{timing.stdev:.3f}s",
                f"{timing.min:.3f}s",
                f"{timing.max:.3f}s",
            ]

            if units_count:
                row.append(f"{timing.mean / units_count:.4f}s")

            row.append(speed_str)
            table_data.append(row)

        headers = ["Mode", "Mean", "Std Dev", "Min", "Max"]
        if units_count:
            headers.append(f"Per {units_label.rstrip('s')}")
        headers.append("Rel. Speed")

        print(f"\n{'=' * 70}")
        print("Benchmark Results")
        print(f"{'=' * 70}\n")
        print(tabulate(table_data, headers=headers, tablefmt="grid", stralign="center"))

        # Summary
        self._print_summary(result, units_label, units_count)

    def _print_summary(
        self,
        result: BenchmarkResult,
        units_label: str,
        units_count: Optional[int],
    ) -> None:
        """Print benchmark summary."""
        print(f"\n{'=' * 70}")
        print("Summary")
        print(f"{'=' * 70}")

        baseline_name = result.baseline
        baseline_timing = result.results.get(baseline_name)

        if not baseline_timing:
            return

        # Find fastest mode
        fastest_mode = min(result.results.keys(), key=lambda m: result.results[m].mean)
        fastest_timing = result.results[fastest_mode]

        if fastest_mode == baseline_name:
            print(f"✅ Baseline '{baseline_name}' is the fastest")
        else:
            speedup, speedup_pct = result.get_speedup(fastest_mode)
            time_saved = baseline_timing.mean - fastest_timing.mean
            print(f"✅ '{fastest_mode}' is {speedup:.2f}x faster than baseline")
            print(f"   Time saved per run: {time_saved:.3f}s ({speedup_pct:.1f}%)")

        if units_count:
            print(f"\nTotal {units_label} per iteration: {units_count}")

        print(f"Baseline: '{baseline_name}'")

        for mode_name, timing in result.results.items():
            print(f"  {mode_name}: {timing.total:.2f}s total ({timing.count} runs)")

        # Metadata
        if result.metadata:
            print(f"\nMetadata:")
            for key, value in result.metadata.items():
                print(f"  {key}: {value}")

        print(f"{'=' * 70}\n")


# =============================================================================
# Convenience Functions
# =============================================================================


def benchmark(
    name: str,
    modes: dict[str, Callable[..., Any]],
    iterations: int = 3,
    baseline: Optional[str] = None,
    cleanup_mode: CleanupMode = CleanupMode.AUTO,
    output_dir: Optional[Path] = None,
    warmup_runs: int = 0,
    units_label: str = "ops",
    units_count: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
    verbose: bool = True,
) -> BenchmarkResult:
    """
    Convenience function for quick benchmarking.

    Args:
        name: Benchmark name
        modes: Dict of mode_name -> callable
        iterations: Number of iterations per mode
        baseline: Mode to use as baseline (first if None)
        cleanup_mode: How to handle cleanup
        output_dir: Output directory (required for MANUAL/NONE cleanup)
        warmup_runs: Number of warmup iterations (not timed)
        units_label: Label for per-unit stats
        units_count: Number of units for per-unit calculation
        metadata: Additional metadata
        verbose: Print progress

    Returns:
        BenchmarkResult with all data
    """
    config = BenchmarkConfig(
        name=name,
        iterations=iterations,
        warmup_runs=warmup_runs,
        cleanup_mode=cleanup_mode,
        output_dir=output_dir,
        verbose=verbose,
    )

    runner = BenchmarkRunner(config)

    for mode_name, mode_func in modes.items():
        runner.register_mode(mode_name, mode_func)

    result = runner.run(baseline=baseline, metadata=metadata)
    runner.print_results(result, units_label=units_label, units_count=units_count)

    return result


def time_function(
    func: Callable[..., Any],
    iterations: int = 3,
    *args,
    **kwargs,
) -> TimingResult:
    """
    Simple function timer without output directory management.

    Args:
        func: Function to time
        iterations: Number of iterations
        *args, **kwargs: Arguments to pass to func

    Returns:
        TimingResult with statistics
    """
    result = TimingResult(name=func.__name__)

    for _ in range(iterations):
        start = time.perf_counter()
        func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        result.times.append(elapsed)

    return result


# =============================================================================
# CLI Entry Point
# =============================================================================


def main():
    """CLI entry point for standalone benchmark utility."""
    parser = argparse.ArgumentParser(
        description="General-purpose benchmark utility for comparing execution modes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This module is primarily designed to be imported and used programmatically.
For standalone CLI usage with specific scripts, see bench_pixcomp.py or
create your own benchmark script using this module.

Example usage as a module:

    from bench import BenchmarkRunner, BenchmarkConfig, CleanupMode
    
    config = BenchmarkConfig(
        name="My Benchmark",
        iterations=5,
        cleanup_mode=CleanupMode.AUTO,
    )
    
    runner = BenchmarkRunner(config)
    runner.register_mode("mode1", my_func1)
    runner.register_mode("mode2", my_func2)
    
    result = runner.run(baseline="mode1")
    runner.print_results(result, units_label="files", units_count=100)

Quick usage with convenience function:

    from bench import benchmark, CleanupMode
    
    result = benchmark(
        name="Quick Test",
        modes={
            "fast": fast_function,
            "slow": slow_function,
        },
        iterations=3,
        baseline="slow",
    )
        """,
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a demo benchmark with synthetic functions",
    )
    parser.add_argument(
        "--iterations",
        "-i",
        type=int,
        default=3,
        help="Number of iterations (default: 3)",
    )

    args = parser.parse_args()

    if args.demo:
        print("Running demo benchmark...\n")

        # Demo functions
        def slow_operation(output_dir: Path):
            time.sleep(0.1)

        def fast_operation(output_dir: Path):
            time.sleep(0.03)

        def medium_operation(output_dir: Path):
            time.sleep(0.06)

        result = benchmark(
            name="Demo Benchmark",
            modes={
                "slow": slow_operation,
                "medium": medium_operation,
                "fast": fast_operation,
            },
            iterations=args.iterations,
            baseline="slow",
            units_label="operations",
            units_count=10,
            metadata={
                "type": "synthetic",
                "purpose": "demonstration",
            },
        )

        return 0
    else:
        parser.print_help()
        print("\n\nRun with --demo to see an example benchmark.")
        return 0


if __name__ == "__main__":
    exit(main())
