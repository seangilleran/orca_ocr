"""
OCR with Azure Computer Vision
by Sean Gilleran (sean@wgws.dev)
December 2023

This module provides functionality for performing Optical Character Recognition
(OCR) on image files using Azure Computer Vision API. It is designed to interact
with Azure's Computer Vision service to extract text from various image formats.

The module contains functions to send image files to Azure Computer Vision and
retrieve the OCR results. The primary function, `analyze_image`, manages the
process of sending the image to the Azure service. Azure Computer Vision API
keys and endpoint should be set as environment variables for the script to
function correctly.

Functions:
    analyze_image(img_file: Path, img_type: str) -> dict:
        Analyzes an image file for text content using Azure Computer Vision.
        Returns a dictionary containing the OCR results.

Usage:
    When used as a standalone script:
        - Configure Azure credentials as environment variables.
        - Run the script and it will log its process to the console.
    When imported as a module:
        - Call the `analyze_image` function with an image file path.
"""
import json
import logging
import os
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)


def get_img_type(file_path: str | Path) -> str:
    """
    Verify file exists, is a file, and is a supported image type.

    Parameters:
        file_path (str or Path): Path to the file.

    Returns:
        str: Image content-type string.
    """
    file_path = Path(file_path)
    if not file_path.exists() or not file_path.is_file():
        return
    ext = file_path.suffix.lower()

    if ext == '.bmp':
        return 'bmp'
    if ext == '.gif':
        return 'gif'
    if ext == '.heic':
        return 'heic'
    if ext == '.ico':
        return 'ico'
    if ext == '.jpg' or ext == '.jpeg':
        return 'jpeg'
    if ext == '.mpo':
        return 'mpo'
    if ext == '.png':
        return 'png'
    if ext == '.tif' or ext == '.tiff':
        return 'tiff'
    if ext == '.webp':
        return 'webp'
    return


def analyze_image(
    img_file: str | Path, max_retries: int = 0, retry_delay: float = 5.0
) -> dict:
    """
    Send image file to Azure Computer Vision for OCR.

    Parameters:
        img_file (str or Path): Path to the image file.
        max_retries (int): Retries to attempt after failed request.
        retry_delay (float): Seconds to wait between retries.

    Returns:
        dict: Image analysis results.

    API reference: https://eastus.dev.cognitive.microsoft.com/docs/services/unified-vision-apis-public-preview-2023-04-01-preview/operations/61d65934cd35050c20f73ab6
    """
    img_file = Path(img_file)
    img_type = get_img_type(img_file)
    if not img_type:
        return

    # .HEIC files need to be converted before they get sent to Azure. Doing this
    # at download would save time if we ran this a lot, but .HEIC is a very
    # efficient format, and leaving it behind would take up more disk space.
    if img_type == 'heic':
        import pyheif
        from PIL import Image

        log.debug('Converting %s to .PNG...' % img_file)
        heif = pyheif.read(img_file.as_posix())
        img = Image.frombytes(
            heif.mode,
            heif.size,
            heif.data,
            'raw',
            heif.mode,
            heif.stride,
        )
        img_file = img_file.with_suffix('.png')
        img.save(img_file.as_posix())

    with img_file.open('rb') as f:
        image = f.read()

    # Build request headers. See Azure Computer Vision docs for details.
    uri = os.environ['_ORCA_VISION_ENDPOINT'] + '/computervision/imageanalysis:analyze'
    params = {
        'api-version': os.environ['_ORCA_VISION_API_VERSION'],
        'features': 'read',
    }
    headers = {
        'Content-Type': 'application/octet-stream',
        'Ocp-Apim-Subscription-Key': os.environ['_ORCA_VISION_KEY'],
    }

    attempt = 0
    while attempt == 0 or attempt < max_retries:
        response = requests.post(uri, headers=headers, params=params, data=image)
        status = response.status_code
        if attempt < max_retries and status != 200:
            log.error('Failed with code %d.' % status)
            if attempt < max_retries:
                log.info(
                    'Retrying in %d seconds (%d/%d)...'
                    % (retry_delay, attempt + 1, max_retries)
                )
                attempt += 1
                time.sleep(retry_delay)
        else:
            break

    # Delete converted version if we made one.
    if img_type == 'heic':
        log.debug('Deleting %s...' % img_file)
        img_file.unlink()

    try:
        return response.json()
    except requests.exceptions.JSONDecodeError:
        return {}


def analyze_images(
    in_path: str | Path,
    out_path: str | Path,
    max_retries: int = 0,
    retry_delay: float = 5.0,
):
    """TODO: Description."""
    in_path = Path(in_path)
    out_path = Path(out_path)
    out_path.mkdir(parents=True, exist_ok=True)

    log.info('Sending %s to Azure Vision...' % in_path)
    img_files = natsorted([f for f in in_path.iterdir() if get_img_type(f)])
    count = len(img_files)
    for i, img_file in enumerate(img_files):
        json_file = out_path / f"{img_file.stem}.json"

        # Skip files we already have data for.
        if json_file.exists():
            log.info('Skipping %s (%d/%d), processed.' % (json_file, i + 1, count))
            continue

        log.info('%s (%d/%d)...' % (json_file, i + 1, count))
        data = analyze_image(img_file, max_retries, retry_delay)
        with json_file.open('w') as f:
            json.dump(data, f, indent=4)

    log.info('Done! Finished processing images in %s.' % in_path)


if __name__ == '__main__':
    import argparse
    from dotenv import load_dotenv
    from natsort import natsorted

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument('paths', nargs='+', help='List of file paths')
    args = parser.parse_args()

    # Kludge: nohup includes the name of the file as one of the arguments (?)
    paths = args.paths
    if 'vision.py' in args.paths[0]:
        paths = args.paths[1:]

    for in_path in [Path(p) for p in paths]:
        out_path = in_path / os.environ['_ORCA_VISION_MODEL']
        analyze_images(in_path, out_path)
