"""TODO: File description."""
import os
import time
from pathlib import Path

from pyicloud import PyiCloudService
from pyicloud.services.photos import PhotoAlbum, PhotoAsset


def login(username: str = '', password: str = '') -> PyiCloudService:
    """
    Login to iCloud and return an interface to the API. 2FA/2SA code adapted
    from https://github.com/picklepete/pyicloud.
    """
    if not username:
        username = os.environ['_ORCA_ICLOUD_USER']
    if not password:
        password = os.environ['_ORCA_ICLOUD_PASS']

    print(f"Logging in ({username})...")
    api = PyiCloudService(username, password)

    if api.requires_2fa:
        print('Two-factor authentication required.')
        code = input('Enter the code you received on one of your approved devices: ')

        if code.lower()[0] == 'q' or code.lower()[0] == 'x':
            print('Exiting.')
            exit(0)

        result = api.validate_2fa_code(code)
        print(f"Code validation result: {result}")

        if not result:
            print('Failed to verify security code.')
            exit(1)

        if not api.is_trusted_session:
            print('Session is not trusted. Requesting trust...')
            result = api.trust_session()
            print(f"Session trust result: {result}")

            if not result:
                print('Failed to request trust.')

    elif api.requires_2sa:
        import click

        print('Two-step authentication required. Your trusted devices are:')
        devices = api.trusted_devicesF
        for i, device in enumerate(devices):
            print(
                f" {i}: {device.get('deviceName', 'SMS to %s' % device.get('phoneNumber'))}"
            )

        device = click.prompt('Which device would you like to use?', default=0)
        device = devices[device]
        if not api.send_verification_code(device):
            print('Failed to send verification code.')
            exit(1)

    return api


def heic_to_png(heic_file: Path, delete_old: bool = False) -> Path:
    """TODO: Description."""
    import pyheif
    from PIL import Image

    heif = pyheif.read(heic_file.as_posix())
    img = Image.frombytes(
        heif.mode,
        heif.size,
        heif.data,
        'raw',
        heif.mode,
        heif.stride,
    )

    png_file = heic_file.with_suffix('.png')
    img.save(png_file.as_posix())
    if delete_old:
        heic_file.unlink()

    return png_file


def download_album(album: PhotoAlbum, path: Path) -> None:
    """TODO: Description."""
    count = len(album)
    print(f"Downloading {count} photos from {album.name}...")
    for i, photo in enumerate(album):
        # Add the created-on date to the filename in order to help us sort
        # images in the order they were taken.
        timestamp = photo.created.strftime('%Y-%m-%d_%H-%M-%S')
        img_file = Path(path) / f"{timestamp}_{photo.filename}"

        # Skip the photo if it's already been downloaded. Use the new filename!
        if img_file.exists() or img_file.with_suffix('.png').exists():
            print(f"  Skipping {photo.filename} ({i}/{count})")
            continue

        # Buffer the download so we don't have to keep the whole thing in RAM.
        print(f"  Downloading {photo.filename} ({i}/{count})")
        download = photo.download()
        with img_file.open('wb') as f:
            for chunk in download.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

        # Azure can't work with HEIC so we'll need to convert.
        if img_file.suffix.lower() == '.heic':
            img_file = heic_to_png(img_file, delete_old=True)

        # Overwrite filesystem timestamp with iCloud's "created on" property,
        # just as another way to help sort them if necessary.
        timestamp = time.mktime(photo.created.timetuple())
        os.utime(img_file, (timestamp, timestamp))

    print('Done!')


if __name__ == '__main__':
    import argparse
    from dateutil.parser import parse
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'albums',
        metavar='album',
        type=str,
        nargs='*',
        help='album titles separated by spaces',
    )
    args = parser.parse_args()

    api = login()

    for i, album in enumerate(args.albums):
        # Kludge: If the title is a month/year combo, use a simplified path.
        album_folder = album
        try:
            album_folder = parse(album).strftime('%Y-%m')
        except:
            pass
        download_path = Path('data') / album_folder
        download_path.mkdir(parents=True, exist_ok=True)

        download_album(api.photos.albums[album])

    print('Done!')
