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
    img_file: str | Path, max_retries: int = 3, retry_delay: float = 5.0
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
    with img_file.open('rb') as f:
        image = f.read()

    uri = os.environ['_ORCA_VISION_ENDPOINT'] + '/computervision/imageanalysis:analyze'
    params = {
        'api-version': os.environ['_ORCA_VISION_API_VERSION'],
        'features': 'read',
    }
    headers = {
        'Content-Type': 'application/octet-stream',
        'Ocp-Apim-Subscription-Key': os.environ['_ORCA_VISION_KEY'],
    }

    for attempt in range(max_retries):
        response = requests.post(uri, headers=headers, params=params, data=image)
        status = response.status_code
        if attempt <= max_retries and status != 200:
            log.warning('Failed (%d), retrying in %ds...' % (status, retry_delay))
            time.sleep(retry_delay)
        elif status == 200:
            break
        else:
            log.error('Skipping %s, error.' % img_file)
            return {}

    return response.json()


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

    for path in [Path(p) for p in paths]:
        log.info('Sending %s to Azure Vision...' % path)
        out_path = path / os.environ['_ORCA_VISION_MODEL']
        out_path.mkdir(parents=True, exist_ok=True)

        img_files = [f for f in path.iterdir() if get_img_type(f)]
        count = len(img_files)
        img_files = natsorted(img_files)
        for i, img_file in enumerate(img_files):
            json_file = out_path / f"{img_file.stem}.json"

            # Skip files we already have data for.
            if json_file.exists():
                log.info('Skipping %s (%d/%d), processed.' % (img_file, i + 1, count))
                continue

            log.info('%s (%d/%d)...' % (img_file, i + 1, count))
            data = analyze_image(img_file)
            with json_file.open('w') as f:
                json.dump(data, f, indent=4)

        log.info('Done! Finished processing images in %s.' % path)
