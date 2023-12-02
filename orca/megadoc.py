"""TODO: File description."""
import json
from pathlib import Path
from typing import Iterable, Tuple

from docx import Document


def get_headings(file_path: Path) -> Tuple[str, str]:
    """TODO: Description."""
    from dateutil.parser import parse

    # Try to use the format from icloud.py first. If that doesn't work, just
    # come back with the original filename so we at least have something.
    try:
        parts = file_path.stem.split('_')

        date, time = parts[:2]
        timestamp = parse(f"{date} {time.replace('-', ':')}")
        timestamp = timestamp.strftime('%B %d, %Y at %I:%M %p')

        name = '_'.join(parts[2:])

        return name, timestamp

    except:
        return file_path.name, '[No timestamp.]'


def zip_files(file_paths: Iterable[Path], out_path: Path) -> None:
    """TODO: Description."""
    from zipfile import ZipFile

    with ZipFile(out_path.as_posix(), 'w') as zip:
        for file in file_paths:
            if file.exists() and file.is_file():
                zip.write(file, file.name)


def build_doc(data_path: Path, chunk_size: int = 5000) -> Path:
    """TODO: Description."""
    from natsort import natsorted
    from unidecode import unidecode

    out_path = data_path / 'megadoc'
    out_path.mkdir(parents=True, exist_ok=True)

    json_files = natsorted(list(data_path.glob('*.json')))

    # Word docs can only realistically handle so much stuff at once before we
    # start hitting RAM limits. We can manage this by breaking each megadoc
    # into bite-sized chunks.
    file_count = len(json_files)
    chunk_total = file_count // chunk_size
    if file_count % chunk_size != 0:
        chunk_total += 1

    chunk_files = []
    for chunk in range(chunk_total):
        start = chunk * chunk_size
        end = (chunk + 1) * chunk_size

        doc = Document()
        filename = (
            f"{data_path.parent.name}_{(chunk + 1):02d}of{(chunk_total):02d}.docx"
        )
        doc_file = out_path / filename

        print(f"Building {doc_file}...")
        for i, json_file in enumerate(json_files[start:end]):
            print(f"  {json_file} ({i + start + 1}/{file_count})")
            with json_file.open() as f:
                data = json.load(f)

            # Get heading from filename.
            name, timestamp = get_headings(json_file)
            doc.add_heading(name, level=1)
            doc.add_heading(timestamp, level=2)

            # Different Azure models return data in different formats. We can
            # tell which one was used by the way key used to store the result.
            # TODO: Break this out into separate function definition(s).
            # ... Computer Vision
            if 'readResult' in data:
                try:
                    lines = []
                    for line in data['readResult']['pages'][0]['lines']:
                        lines.append(unidecode(line['content']))
                    doc.add_paragraph('\n'.join(lines))
                except KeyError:
                    doc.add_paragraph('[No text recovered.]')

            # ... Document Intelligence
            elif 'analyzeResult' in data:
                try:
                    for p in data['analyzeResult']['paragraphs']:
                        doc.add_paragraph(unidecode(p['content']))
                except KeyError:
                    doc.add_paragraph('[No text recovered.]')

            # ... something went wrong; OCR errored out somehow.
            else:
                doc.add_paragraph('[No text recovered.]')

            doc.add_page_break()

        print(f"Saving {doc_file}...")
        doc.save(doc_file.as_posix())
        chunk_files.append(doc_file)

    print('Zipping files...')
    zip_files(chunk_files, out_path / f"{data_path.parent.name}_{data_path.name}.zip")

    print('Done!')


if __name__ == '__main__':
    import argparse
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'paths',
        metavar='path',
        type=str,
        nargs='+',
        help='paths containing json files',
    )
    args = parser.parse_args()

    for path in [Path(p) for p in args.paths]:
        build_doc(path)
    
    print('Done!')
