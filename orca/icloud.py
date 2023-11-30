"""TODO: File description."""
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from pyicloud import PyiCloudService
from pyicloud.services.photos import PhotoAlbum, PhotoAsset


def login(username='', password='') -> PyiCloudService:
    """TODO: Description."""
    if not username:
        username = os.environ['_ORCA_ICLOUD_USER']
    if not password:
        password = os.environ['_ORCA_ICLOUD_PASS']

    # Attempt login. 2FA/2SA code adapted from https://github.com/picklepete/pyicloud.
    print(f"Logging in ({username})...")
    api = PyiCloudService(username, password)

    if api.requires_2fa:
        print('Two-factor authentication required.')
        code = input('Enter the code you received on one of your approved devices: ')
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


def get_photos_by_date(
    album: PhotoAlbum, end_date: datetime, start_date: Optional[datetime] = None
) -> Iterator[PhotoAsset]:
    """TODO: Description."""
    for photo in album:
        if start_date is None or start_date < photo.created <= end_date:
            yield photo


def heic_to_png(heic_filename: str, delete_old: bool = False) -> str:
    """TODO: Description."""
    import pyheif
    from PIL import Image

    heif = pyheif.read(heic_filename)
    img = Image.frombytes(
        heif.mode,
        heif.size,
        heif.data,
        'raw',
        heif.mode,
        heif.stride,
    )

    png_filename = f"{heic_filename[:-5]}.png"
    img.save(png_filename)

    if delete_old:
        os.remove(heic_filename)

    return png_filename


def download_photo(photo: PhotoAsset, path: str) -> bool:
    """TODO: Description."""
    ts = photo.created.strftime('%Y-%m-%d_%H-%M-%S')
    img_file = Path(path) / f"{ts}_{photo.filename}"

    if img_file.exists() or img_file.with_suffix('.png').exists():
        return False

    download = photo.download()
    with img_file.open('wb') as f:
        for chunk in download.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    # Convert from HEIC if necessary.
    if img_file.suffix.lower() == '.heic':
        img_file = Path(heic_to_png(img_file.as_posix(), delete_old=True))

    # Overwrite filesystem timestamp with iCloud's "created on" property.
    timestamp = time.mktime(photo.created.timetuple())
    os.utime(img_file, (timestamp, timestamp))

    return True


if __name__ == '__main__':
    print('Logging in...')
    api = login()

    print('Downloading photos ...')
    albums = [
        ('2023-02', 'February 2023'),
        ('2023-03', 'March 2023'),
        ('2023-04', 'April 2023'),
        ('2023-05', 'May 2023'),
        ('2023-06', 'June 2023'),
        ('2023-01', 'January 2023'),
    ]
    for i, album_info in enumerate(albums):
        album_path, album_name = album_info
        download_path = Path('data') / album_path
        download_path.mkdir(parents=True, exist_ok=True)

        album = api.photos.albums[album_name]
        count = len(album)

        for x, photo in enumerate(album):
            
            if download_photo(photo, download_path):
                print(f"  Downloading {photo.filename} ({album_name} {x + 1}/{count})")
            else:
                print(f"  Skipping {photo.filename} ({album_name} {x + 1}/{count})")

    print('Done!')
