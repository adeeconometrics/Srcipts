
from pathlib import Path
from typing import Union
import argparse

from PIL import Image


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


def batch_compress(files: list[Path], outdir: Union[Path, str], extension: str = 'jpeg', quality: int = 75) -> None:
    """
    Compress a batch of image files and save to `outdir` using the specified extension and quality.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for file in files:
        try:
            img = Image.open(file)
            out_file = outdir / file.with_suffix(f'.{extension.lower()}').name
            if extension.lower() in ('jpg', 'jpeg'):
                img = img.convert('RGB')
                img.save(out_file, 'JPEG', quality=quality, optimize=True)
            elif extension.lower() == 'webp':
                img.save(out_file, 'WEBP', quality=quality, method=6)
            elif extension.lower() == 'png':
                img.save(out_file, 'PNG', optimize=True)
            else:
                img.save(out_file, extension.upper())
            print(f"Compressed: {file} -> {out_file}")
        except Exception as e:
            print(f"Failed to compress {file}: {e}")


def compress(dir: Path, outdir: Path, method: str = 'jpeg', quality: int = 75) -> None:
    """
    Find images in `dir` and compress them to `outdir` using the specified method and quality.
    """
    image_exts = ('jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp')
    files = find_path(dir, image_exts)
    batch_compress(files, outdir, method, quality)


def main():
    parser = argparse.ArgumentParser(
        description='Compress images in a directory.')
    parser.add_argument(
        'dir', type=str, help='Input directory containing images')
    parser.add_argument('outdir', type=str,
                        help='Output directory for compressed images')
    parser.add_argument('--method', type=str, default='jpeg',
                        choices=['jpeg', 'jpg', 'webp', 'png'], help='Compression method/format')
    args = parser.parse_args()

    compress(Path(args.dir), Path(args.outdir), args.method)


if __name__ == '__main__':
    main()
