"""
OCR with Azure Computer Vision
by Sean Gilleran (sean@wgws.dev)
December 2023

Automation wrapper for downloading and organizing photos from iCloud albums
via `pyicloud` for later OCR processing.

Functions:
    login(username: str, password: str) -> PyiCloudService:
        Login to iCloud and return session handle to API.

Usage:
    Ensure that iCloud credentials are correctly provided either as arguments
    or via environment variables. 2FA/2SA login *must* be handled interactively.
    See docs for `pyicloud` at https://github.com/picklepete/pyicloud.
"""
import logging
import os
import time
from pathlib import Path

from pyicloud import PyiCloudService
from pyicloud.services.photos import PhotoAlbum, PhotoAsset

log = logging.getLogger(__name__)


def login(username: str = '', password: str = '') -> PyiCloudService:
    """
    Login to iCloud and return session handle to API.

    Account credentials must be passed via argument or stored in the environment
    variables `_ORCA_ICLOUD_USER` and `_ORCA_ICLOUD_PASS`.

    Parameters:
        username (str, optional): iCloud username.
        password (str, optional): iCloud password.

    Returns:
        PyiCloudService: Session-specific API handle.

    Code adapted from samples at https://github.com/picklepete/pyicloud.
    """
    if not username:
        username = os.environ['_ORCA_ICLOUD_USER']
    if not password:
        password = os.environ['_ORCA_ICLOUD_PASS']

    log.info('Logging in (%s)...' % username)
    api = PyiCloudService(username, password)

    if api.requires_2fa:
        print('Two-factor authentication required.')
        code = input('Enter the code you received, or (q)uit: ')
        if code.lower()[0] == 'q' or code.lower()[0] == 'x':
            exit(0)

        result = api.validate_2fa_code(code)
        print(f"Code validation result: {result}")

        if not result:
            log.error('Failed to verify security code.')
            exit(1)

        if not api.is_trusted_session:
            print('Session is not trusted. Requesting trust...')
            result = api.trust_session()
            print(f"Session trust result: {result}")

            if not result:
                log.error('Failed to request trust.')

    elif api.requires_2sa:
        import click

        print('Two-step authentication required. Your trusted devices are:')
        devices = api.trusted_devices
        for i, device in enumerate(devices):
            print(
                f"  {i}: {device.get('deviceName', 'SMS to %s' % device.get('phoneNumber'))}"
            )

        device = click.prompt('Which device would you like to use?', default=0)
        device = devices[device]
        if not api.send_verification_code(device):
            log.error('Failed to send verification code.')
            exit(1)

    return api


def heic_to_png(heic_file: str | Path, delete_old: bool = False) -> str:
    """
    Convert HEIC format image to PNG. Optionally, delete the original HEIC file.

    Parameters:
        heic_file (Path): Path to the HEIC image file.
        delete_old (bool, optional): Whether to delete the original HEIC file.
            Defaults to False.

    Returns:
        str: Path to the converted PNG image file.

    Dependencies:
        pyheif: Python library for working with HEIC images.
        PIL (Pillow): Python Imaging Library for image processing.
    """
    import pyheif
    from PIL import Image

    heic_file = Path(heic_file)

    # Load HEIC data with pyheif and use it to create a PIL image object.
    log.debug('Converting %s to PNG...' % heic_file)
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
        log.debug('Deleting %s...' % heic_file)
        heic_file.unlink()

    log.info('Converted %s to PNG at %s.' % (heic_file.name, png_file))
    return png_file.as_posix()


def download_album(download_path: str | Path, album: PhotoAlbum):
    """
    Download photos from an album and save them to the specified path.

    Parameters:
        path (str or Path): Directory path to save downloaded photos.
        album (PhotoAlbum): PhotoAlbum object containing the album to download.

    This function iterates through the photos in the specified album and
    downloads them to the provided path. It checks whether each photo has
    already been downloaded based on the filename and skips those that have. If
    a photo is in HEIC format, it automatically converts it to PNG.

    The downloaded photos will be named with a timestamp and the original
    filename to help sort them by the order they were taken. The filesystem
    timestamps are also adjusted to reflect the "created on" property from
    iCloud, providing an additional way to sort the photos.
    """
    download_path = Path(download_path)
    count = len(album)
    dl_count = 0

    log.info('Downloading %d photos from %s...' % (count, album.name))
    for i, photo in enumerate(album):
        # Add the created-on date to the filename in order to help us sort
        # images in the order they were taken.
        timestamp = photo.created.strftime('%Y-%m-%d_%H-%M-%S')
        img_file = download_path / f"{timestamp}_{photo.filename}"

        # Skip the photo if it's already been downloaded. Remember, we would
        # have changed the filename during processing!
        if img_file.exists() or img_file.with_suffix('.png').exists():
            log.warn(
                'Skipping %s (%d/%d), image already downloaded.'
                % (photo.filename, i + 1, count)
            )
            continue

        # Buffer the download so we don't have to keep the whole thing in RAM.
        log.info('%s (%d/%d)' % (photo.filename, i + 1, count))
        download = photo.download()
        with img_file.open('wb') as f:
            for chunk in download.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        dl_count += 1

        # Azure can't work with HEIC so we'll need to convert before we do OCR.
        if img_file.suffix.lower() == '.heic':
            img_file = Path(heic_to_png(img_file, delete_old=True))

        # Overwrite filesystem timestamp with iCloud's "created on" property,
        # just as another way to help sort them if necessary.
        timestamp = time.mktime(photo.created.timetuple())
        os.utime(img_file, (timestamp, timestamp))

    log.info('Done! Got %d of %d photos from %s.' % (dl_count, count, album.name))


if __name__ == '__main__':
    import argparse
    from dateutil.parser import parse
    from dotenv import load_dotenv

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

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

    # Kludge: Sometimes the name of the file gets scooped up here.
    albums = [a for a in args.albums if 'icloud.py' not in a]

    for i, album in enumerate(albums):
        # Kludge: If the title is a month/year combo, use a simplified path.
        album_folder = album
        try:
            album_folder = parse(album).strftime('%Y-%m')
        except:
            pass
        download_path = Path('data') / album_folder
        download_path.mkdir(parents=True, exist_ok=True)
        download_album(download_path, api.photos.albums[album])
