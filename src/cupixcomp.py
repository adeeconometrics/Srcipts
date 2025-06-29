import os
import sys
from pathlib import Path
from typing import Union, List
import argparse
import numpy as np
from PIL import Image
import cupy as cp
import nvcomp


def find_path(dir: Path, extension: Union[str, list[str], tuple[str, ...]] = 'jpg') -> list[Path]:
    """
    Recursively find all files in `dir` with the given extension(s).
    """
    if isinstance(extension, str):
        extensions = [extension.lower()]
    else:
        extensions = [ext.lower() for ext in extension]
    files: list[Path] = []
    for ext in extensions:
        files.extend(dir.rglob(f'*.{ext}'))
    return files


def compress_image_cuda(image_path: Path, compressor_type: str = 'lz4') -> tuple[bytes, tuple, np.dtype]:
    """
    Compress a single image using CUDA acceleration with nvcomp.

    Args:
        image_path: Path to the image file
        compressor_type: Type of compression ('lz4', 'snappy', 'gdeflate', 'cascaded')

    Returns:
        Tuple of (compressed_data, original_shape, original_dtype)
    """
    # Load image and convert to numpy array
    img = Image.open(image_path)
    img_array = np.array(img)

    # Transfer to GPU memory
    gpu_data = cp.asarray(img_array)

    # Flatten the array for compression
    flat_data = gpu_data.flatten()

    # Convert to bytes for nvcomp
    data_bytes = flat_data.tobytes()

    # Choose compressor based on type
    if compressor_type.lower() == 'lz4':
        compressor = nvcomp.LZ4Compressor()
    elif compressor_type.lower() == 'snappy':
        compressor = nvcomp.SnappyCompressor()
    elif compressor_type.lower() == 'gdeflate':
        compressor = nvcomp.GdeflateCompressor()
    elif compressor_type.lower() == 'cascaded':
        compressor = nvcomp.CascadedCompressor()
    else:
        raise ValueError(f"Unsupported compressor type: {compressor_type}")

    # Compress the data
    compressed_data = compressor.compress(data_bytes)

    return compressed_data, img_array.shape, img_array.dtype


def decompress_image_cuda(compressed_data: bytes, shape: tuple, dtype: np.dtype, compressor_type: str = 'lz4') -> np.ndarray:
    """
    Decompress image data using CUDA acceleration with nvcomp.

    Args:
        compressed_data: Compressed image data
        shape: Original image shape
        dtype: Original image data type
        compressor_type: Type of compression used

    Returns:
        Decompressed image as numpy array
    """
    # Choose decompressor based on type
    if compressor_type.lower() == 'lz4':
        decompressor = nvcomp.LZ4Decompressor()
    elif compressor_type.lower() == 'snappy':
        decompressor = nvcomp.SnappyDecompressor()
    elif compressor_type.lower() == 'gdeflate':
        decompressor = nvcomp.GdeflateDecompressor()
    elif compressor_type.lower() == 'cascaded':
        decompressor = nvcomp.CascadedDecompressor()
    else:
        raise ValueError(f"Unsupported decompressor type: {compressor_type}")

    # Decompress the data
    decompressed_bytes = decompressor.decompress(compressed_data)

    # Convert back to numpy array
    flat_array = np.frombuffer(decompressed_bytes, dtype=dtype)

    # Reshape to original dimensions
    img_array = flat_array.reshape(shape)

    return img_array


def batch_compress_cuda(files: list[Path], outdir: Union[Path, str], compressor_type: str = 'lz4', save_metadata: bool = True) -> None:
    """
    Compress a batch of image files using CUDA acceleration and save compressed data.

    Args:
        files: List of image file paths
        outdir: Output directory for compressed files
        compressor_type: Type of compression to use
        save_metadata: Whether to save metadata for decompression
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Create metadata directory if saving metadata
    if save_metadata:
        metadata_dir = outdir / "metadata"
        metadata_dir.mkdir(exist_ok=True)

    for file in files:
        try:
            print(f"Compressing: {file}")

            # Compress the image
            compressed_data, shape, dtype = compress_image_cuda(
                file, compressor_type)

            # Save compressed data
            compressed_file = outdir / f"{file.stem}.{compressor_type}"
            with open(compressed_file, 'wb') as f:
                f.write(compressed_data)

            # Save metadata for decompression
            if save_metadata:
                metadata_file = metadata_dir / f"{file.stem}.meta"
                metadata = {
                    'shape': shape,
                    'dtype': str(dtype),
                    'compressor': compressor_type,
                    'original_name': file.name
                }
                import json
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f)

            # Calculate compression ratio
            original_size = file.stat().st_size
            compressed_size = len(compressed_data)
            ratio = original_size / compressed_size if compressed_size > 0 else 0

            print(f"Compressed: {file} -> {compressed_file}")
            print(
                f"Compression ratio: {ratio:.2f}x ({original_size} -> {compressed_size} bytes)")

        except Exception as e:
            print(f"Failed to compress {file}: {e}")


def decompress_cuda(compressed_dir: Path, outdir: Path, file_pattern: str = "*") -> None:
    """
    Decompress CUDA-compressed files back to images.

    Args:
        compressed_dir: Directory containing compressed files
        outdir: Output directory for decompressed images
        file_pattern: Pattern to match compressed files
    """
    outdir.mkdir(parents=True, exist_ok=True)
    metadata_dir = compressed_dir / "metadata"

    if not metadata_dir.exists():
        print("No metadata directory found. Cannot decompress without metadata.")
        return

    # Find all compressed files
    compressed_files = list(compressed_dir.glob(file_pattern))
    compressed_files = [
        f for f in compressed_files if f.is_file() and f.parent.name != "metadata"]

    for compressed_file in compressed_files:
        try:
            # Load metadata
            metadata_file = metadata_dir / f"{compressed_file.stem}.meta"
            if not metadata_file.exists():
                print(f"No metadata found for {compressed_file}")
                continue

            import json
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

            # Load compressed data
            with open(compressed_file, 'rb') as f:
                compressed_data = f.read()

            # Decompress
            shape = tuple(metadata['shape'])
            dtype = np.dtype(metadata['dtype'])
            compressor_type = metadata['compressor']

            img_array = decompress_image_cuda(
                compressed_data, shape, dtype, compressor_type)

            # Save as image
            img = Image.fromarray(img_array)
            original_name = metadata['original_name']
            output_file = outdir / original_name
            img.save(output_file)

            print(f"Decompressed: {compressed_file} -> {output_file}")

        except Exception as e:
            print(f"Failed to decompress {compressed_file}: {e}")


def compress(dir: Path, outdir: Path, compressor_type: str = 'lz4') -> None:
    """
    Find images in `dir` and compress them to `outdir` using CUDA acceleration.
    """
    image_exts = ('jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp')
    files = find_path(dir, image_exts)
    batch_compress_cuda(files[:1000], outdir, compressor_type)


def main():
    parser = argparse.ArgumentParser(
        description='CUDA-accelerated image compression using nvcomp.')

    subparsers = parser.add_subparsers(
        dest='command', help='Available commands')

    # Compress command
    compress_parser = subparsers.add_parser('compress', help='Compress images')
    compress_parser.add_argument(
        'dir', type=str, help='Input directory containing images')
    compress_parser.add_argument(
        'outdir', type=str, help='Output directory for compressed files')
    compress_parser.add_argument('--compressor', type=str, default='lz4',
                                 choices=['lz4', 'snappy',
                                          'gdeflate', 'cascaded'],
                                 help='Compression algorithm to use')

    # Decompress command
    decompress_parser = subparsers.add_parser(
        'decompress', help='Decompress images')
    decompress_parser.add_argument(
        'compressed_dir', type=str, help='Directory containing compressed files')
    decompress_parser.add_argument(
        'outdir', type=str, help='Output directory for decompressed images')
    decompress_parser.add_argument(
        '--pattern', type=str, default='*', help='File pattern to match')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Check CUDA availability
    try:
        import cupy as cp
        print(f"CUDA available: {cp.cuda.is_available()}")
        if cp.cuda.is_available():
            print(f"CUDA device count: {cp.cuda.runtime.getDeviceCount()}")
    except ImportError:
        print("CuPy not available. Please install CuPy for CUDA support.")
        sys.exit(1)

    if args.command == 'compress':
        compress(Path(args.dir), Path(args.outdir), args.compressor)
    elif args.command == 'decompress':
        decompress_cuda(Path(args.compressed_dir),
                        Path(args.outdir), args.pattern)


if __name__ == '__main__':
    main()
