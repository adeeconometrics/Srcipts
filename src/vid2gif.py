from pathlib import Path
from argparse import ArgumentParser, ArgumentError

import imageio as iio

def validate_dir(t_path:Path) -> Path:
    if not Path(Path(t_path).parent).exists():
        raise ArgumentError('Output directory does not exist')
    return t_path

def validate_path(path:str) -> Path:
    path = Path(path)
    if not path.exists():
        raise ArgumentError('Output path does not exist')
    if not path.is_dir():
        raise ArgumentError('Output path is not a directory')
    return path

def vid2gif(vid_path:Path, gif_path:Path) -> Path:
    vid = iio.get_reader(vid_path)
    gif = iio.get_writer(gif_path, mode='I', duration=1/vid.get_meta_data()['fps'])
    for frame in vid:
        gif.append_data(frame)
    gif.close()
    return gif_path

if __name__ == '__main__':
    parser = ArgumentParser(description='Convert a video to a GIF')
    parser.add_argument('-input', help='Path to the video file', required=True, type=validate_path)
    parser.add_argument('-output', help='Path to save the GIF file', required=True, type=validate_dir)

    args = parser.parse_args()
    try:
        output = vid2gif(args.input, args.output)
        print(f'GIF saved to {output}')
    except Exception as e:
        print(f'Error: {e}')