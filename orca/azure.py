"""TODO: File description."""
import json
import os
import time
from pathlib import Path


def analyze_image(path: str, img_type='jpeg', delay=1) -> dict:
    """TODO: Description."""
    import requests

    uri = '{endpoint}formrecognizer/documentModels/{modelId}:analyze'.format(
        endpoint=os.environ['_ORCA_AZURE_ENDPOINT'],
        modelId=os.environ['_ORCA_AZURE_MODEL'],
    )
    headers = {
        'Content-Type': f"image/{img_type}",
        'Ocp-Apim-Subscription-Key': os.environ['_ORCA_AZURE_KEY'],
    }
    params = {
        'api-version': os.environ['_ORCA_AZURE_API_VERSION'],
        'locale': 'en',
        'features': 'ocrHighResolution',
    }
    with open(path, 'rb') as f:
        image = f.read()

    # POST image; collect result URI.
    response = requests.post(uri, headers=headers, params=params, data=image)
    response.raise_for_status()  # TODO: Error handling.
    result_uri = response.headers['Operation-Location']

    # Collect results.
    data = {}
    while 'analyzeResult' not in data:
        time.sleep(delay)  # TODO: Error handling.
        response = requests.get(result_uri, headers=headers)
        data = response.json()

    return data


def get_text(data: dict) -> str:
    """TODO: Description."""
    from unidecode import unidecode

    metatext = 'test'
    text = unidecode(data['analyzeResult']['content'])

    return text, metatext


if __name__ == '__main__':
    from natsort import natsorted

    path = Path('data/2022-11')
    print(f"Sending {path} to Azure OCR...")
    out_path = path / os.environ['_ORCA_AZURE_MODEL']
    out_path.mkdir(parents=True, exist_ok=True)

    img_files = natsorted(list(path.glob('*.png')))
    for i, img_file in enumerate(img_files):
        
        json_file = out_path / f"{img_file.stem}.json"
        if json_file.exists():
            print(f"  Skipping {json_file} ...")
            continue

        print(f"  {img_file} ({i + 1}/{len(img_files)})")
        data = analyze_image(img_file.as_posix(), img_type='png')

        with open(json_file, 'w') as f:
            json.dump(data, f, indent=4)
