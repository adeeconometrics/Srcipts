from pathlib import Path
from argparse import ArgumentParser, ArgumentError
from pytube import YouTube

def validate_path(path:str) -> Path:
    path = Path(path)
    if not path.exists():
        raise ArgumentError('Output path does not exist')
    if not path.is_dir():
        raise ArgumentError('Output path is not a directory')
    return path

def download_video(t_url:str, t_outpath:str | Path, t_reso:int = 360) ->Path:
    yt = YouTube(t_url)
    stream = yt.streams.filter(res=f'{t_reso}p').first()
    return stream.download(t_outpath)


if __name__ == '__main__':
    parser = ArgumentParser(description='Download a video from YouTube')
    parser.add_argument('-url', help='URL of the video to download', required=True, type=str)
    parser.add_argument('-output', help='Output directory to save the video', required=True, type=validate_path)

    args = parser.parse_args()
    try:
        output = download_video(args.url, args.output)
        print(f'Video downloaded to {output}')
    except Exception as e:
        print(f'Error: {e}')