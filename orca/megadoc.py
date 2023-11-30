"""TODO: File description."""
import json
from pathlib import Path
from typing import List, Tuple


def get_headings(file_path: Path) -> Tuple[str, str]:
    """TODO: Description."""
    from dateutil.parser import parse

    date, time = file_path.stem.split('_')[:2]
    name = '_'.join(file_path.stem.split('_')[2:])

    timestamp = parse(f"{date} {time.replace('-', ':')}")
    timestamp_str = timestamp.strftime('%B %d, %Y at %I:%M %p')

    return timestamp_str, name


def get_text(ocr_data: dict, vision: bool = False) -> Tuple[List[str], List[str]]:
    """TODO: Description"""
    from unidecode import unidecode

    text = []
    metatext = []

    try:
        paragraphs = ocr_data['analyzeResult']['paragraphs']
    except KeyError:
        return None

    for p in paragraphs:
        content = unidecode(p['content'])

        # Discard pargraphs taller than they are wide.
        # x1, y1, x2, y2, x3, y3, x4, y4 = p['boundingRegions'][0]['polygon']
        # width = abs(x2- x1)
        # height = abs(y3-y1)
        # if width <= height:
        #     metatext.append(content)
        #     continue

        text.append(content)

    return text, metatext


def build_doc(data_path: Path) -> Path:
    """TODO: Description."""
    from docx import Document
    from natsort import natsorted
    from unidecode import unidecode

    json_files = natsorted(list(data_path.glob('*.json')))
    file_count = len(json_files)

    # Split each set of files into 5000-page chunks.
    chunk_size = 5000
    for chunk_count in range(0, file_count, chunk_size):
        chunk = json_files[chunk_count : chunk_count + chunk_size]

        doc = Document()
        doc_file = (
            data_path
            / f"{data_path.parent.name}_{chunk_count + 1}-{chunk_count + chunk_size}.docx"
        )
        print(f"Building {doc_file} ...")

        for i, json_file in enumerate(chunk):
            print(f"  {json_file} ({i + 1 + chunk_count}/{chunk_count + chunk_size})")
            with json_file.open() as f:
                data = json.load(f)

            # Get heading from filename.
            timestamp, name = get_headings(json_file)
            doc.add_heading(name, level=1)
            doc.add_heading(timestamp, level=2)

            # Used Computer Vision model.
            if 'readResult' in data:
                try:
                    lines = []
                    for line in data['readResult']['pages'][0]['lines']:
                        lines.append(unidecode(line['content']))
                    doc.add_paragraph('\n'.join(lines))
                except KeyError:
                    doc.add_paragraph('[No text recovered.]')

            # Used Document Intelligence model.
            elif 'analyzeResult' in data:
                try:
                    for p in data['analyzeResult']['paragraphs']:
                        doc.add_paragraph(unidecode(p['content']))
                except KeyError:
                    doc.add_paragraph('[No text recovered.]')

            else:
                doc.add_paragraph('[No text recovered.]')

            doc.add_page_break()

        doc.save(doc_file.as_posix())
        print('Done!')


if __name__ == '__main__':
    for path in [
        Path('data/2022-11/imageanalysis'),
    ]:
        build_doc(path)
