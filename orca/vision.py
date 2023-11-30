"""TODO: File description."""
import json
import os
import time
from pathlib import Path


def analyze_image(path: str, img_type='png') -> dict:
    """TODO: Description."""
    import requests

    uri = '{endpoint}/computervision/imageanalysis:analyze'.format(
        endpoint=os.environ['_ORCA_VISION_ENDPOINT'],
    )
    headers = {
        'Content-Type': f"image/{img_type}",
        'Ocp-Apim-Subscription-Key': os.environ['_ORCA_VISION_KEY'],
    }
    params = {
        'api-version': os.environ['_ORCA_VISION_API_VERSION'],
        'features': 'read',
    }
    with open(path, 'rb') as f:
        image = f.read()

    # POST image; collect result URI.
    max_retries = 3
    retry_delay = 60
    for attempt in range(max_retries):
        try:
            response = requests.post(uri, headers=headers, params=params, data=image)
            response.raise_for_status()
            break
        except requests.exceptions.HTTPError as e:
            if attempt <= max_retries:
                print(f"  Connection error, retrying in {retry_delay} seconds...")
                with open('error.json', 'w') as f:
                    json.dump(response.json(), f, indent=4)
                time.sleep(retry_delay)
            else:
                print(f"Max retries exceeded, connection failed, exiting.")
                exit(1)
        except requests.exceptions.RequestException:
            raise

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

    for path in [Path('data/2023-01')]:
        print(f"Sending {path} to Azure Vision...")
        out_path = path / os.environ['_ORCA_VISION_MODEL']
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
        print('Done!')
