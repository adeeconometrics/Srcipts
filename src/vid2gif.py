from pathlib import Path
from io import BytesIO
from PIL import Image
from argparse import ArgumentParser, ArgumentError

import imageio as iio
import numpy as np


def validate_dir(t_path: Path) -> Path:
    """Check if the output directory exists"""
    if not Path(Path(t_path).parent).exists():
        raise ArgumentError(message='Output directory does not exist')
    return t_path

def validate_path(path: Path) -> Path:
    """Check if the input path exists"""
    if not Path(path).exists():
        raise ArgumentError(message='Input path does not exist')
    return path


def vid2gif(t_path: Path, 
            t_outpath: Path, 
            fps: int = 10, 
            t_quality: int = 20, 
            resize: tuple = (1080,1080)) -> Path:
    """Convert a video to a GIF"""
    vid = iio.get_reader(t_path)

    frames = []
    for i, frame in enumerate(vid):
        if i % (fps*1) == 0:
            img = Image.fromarray(frame).resize(resize)
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format='JPEG',
                     quality=t_quality, optimize=True)
            img_byte_arr = BytesIO(img_byte_arr.getvalue())
            frame = np.array(Image.open(img_byte_arr))
            frames.append(frame)

    iio.mimsave(t_outpath, frames, fps=fps, format='GIF')

    return t_outpath


if __name__ == '__main__':
    parser = ArgumentParser(description='Convert a video to a GIF')
    parser.add_argument('-input', help='Path to the video file',
                        required=True, type=validate_path)
    parser.add_argument(
        '-output', help='Path to save the GIF file', required=True, type=validate_dir)

    args = parser.parse_args()
    try:
        output = vid2gif(args.input, args.output)
        print(f'GIF saved to {output}')
    except Exception as e:
        print(f'Error: {e}')
