# accession-labeler

A small utility for generating and printing accession identifier labels for archival artifacts and physical media. Built to automate labeling workflows without dealing with manual template alignment or proprietary GUI label software every time a batch comes in.

Supports Brother P-Touch label printers (via `ptouch-print`) and sheet-fed disc hub labels (Compulabel #312862 via ReportLab).

---

## What It Does

- **Flexible identifier syntax**: Expands years, batches, items, and multipart ranges (`2024.12.05A1-3,B1-2` or `2024.44.16`) with automatic zero-padding to match standard archival formatting.
- **Brother P-Touch printing**: Produces native 1-bit monochrome bitmap labels and handles continuous chain printing with precut/chain flags so tape isn't wasted between labels.
- **Disc hub label sheets**: Generates printable PDF sheets for round CD/DVD/disc hub labels with curved text, starting-slot offset support (so partial sheets don't go to waste), and calibration offsets.
- **Interactive TUI or direct CLI**: Run without arguments for a terminal UI (with a staged tree queue and wizard), or pass identifiers directly on the command line for headless/scripted batch generation.
- **Python API**: Import `print_accession_labels()` directly into external catalog tools or collection management scripts.

---

## Requirements

- Python 3.8+
- Pillow, reportlab
- Fonts: Droid Sans and Droid Sans Mono (included in `fonts/`)
- *(Optional, for tape printing)* `ptouch-print` utility and a compatible Brother label printer.
- *(Optional, for SVG rasterization)* `imagemagick` or `librsvg`.

---

## Usage

### Interactive TUI

Running with no arguments launches the terminal interface:

```bash
python3 accession-labeler.py
```

From here you can use the wizard (`A`), enter identifiers directly (`M`), view the staged queue as a tree (`V`), delete items (`X`), or run a chain print job (`P`).

### Command Line Examples

Print a range of subparts directly (dry run):
```bash
python3 accession-labeler.py 2024.12.5A1-3,B1-2 --dry-run
```

Print multiple distinct identifiers in one run:
```bash
python3 accession-labeler.py 2024.44.16 2024.44.17A1-2
```

Generate a disc hub PDF sheet starting on slot 5:
```bash
python3 accession-labeler.py 2024.12.5A1-4 --disc-hub --start-pos 5 --hub-pdf labels/discs.pdf
```

Test disc hub sheet alignment with guide circles on regular paper:
```bash
python3 accession-labeler.py 2024.12.5A1 --disc-hub --show-guides --hub-pdf test.pdf
```

### Python API

```python
from accession_labeler import print_accession_labels

print_accession_labels(
    identifiers=["2024.44.16A1-3", "2024.44.17B1-2"],
    dry_run=True,
)
```
