from pathlib import Path
from argparse import ArgumentParser, ArgumentError
from pytube import YouTube

def format_name(t_name:str) -> str:
    return ''.join(i.capitalize() for i in t_name.split(' '))

def validate_path(path:str) -> Path:
    if not Path(path).exists():
        raise ArgumentError('Output path does not exist')
    return path

def download_video(t_url:str, t_outpath:str | Path, t_reso:int | None = None) ->Path:
    yt = YouTube(t_url)
    if t_reso is None:
        stream = yt.streams.get_highest_resolution()
    else:
        stream = yt.streams.filter(res=f'{t_reso}p').first()
    # Download the video and get the path of the downloaded file
    download_path = Path(stream.download(t_outpath))

    # Create a new path with the formatted title
    new_path = download_path.parent / \
        f"{format_name(yt.title)}{download_path.suffix}"

    # Rename the downloaded file
    download_path.rename(new_path)

    return new_path


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