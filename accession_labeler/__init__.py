"""
Museum Accession Labeler Package.
Exposes public API for external catalog integrations and label printing.
"""

from typing import List, Union, Tuple
from accession_labeler.models import AccessionID
from accession_labeler.parser import (
    parse_identifiers,
    parse_range_expression,
    expand_part_designation,
)
from accession_labeler.printer import process_label_batch, print_label
from accession_labeler.renderer import get_fonts, load_template_text_baselines
from accession_labeler.tui import build_tree_lines


class PrintArgs:
    """Mock configuration arguments for API printing."""
    def __init__(
        self,
        dry_run: bool = False,
        no_chain: bool = False,
        printer_cmd: str = "ptouch print --image {file}",
        engine: str = "pillow",
        width: str = "auto",
        output: str = None,
        svg_output: str = None
    ):
        self.dry_run = dry_run
        self.no_chain = no_chain
        self.printer_cmd = printer_cmd
        self.engine = engine
        self.width = width
        self.output = output
        self.svg_output = svg_output


def print_accession_labels(
    identifiers: List[Union[str, Tuple[str, str]]],
    dry_run: bool = False,
    printer_cmd: str = "ptouch print --image {file}",
    no_chain: bool = False
) -> bool:
    """
    Public API to generate and print a list of accession labels in a single chain job.
    Accepts full accession strings (e.g. ['2024.12.05', '2024.12.05A1-3'])
    or tuple pairs (e.g. [('2024', '12.05A1')]).
    """
    labels = []
    for item in identifiers:
        if isinstance(item, tuple):
            labels.append(item)
        elif isinstance(item, str):
            labels.extend(parse_identifiers(identifier_str=item))
        else:
            raise TypeError(f"Expected str or tuple, got {type(item)}")

    args = PrintArgs(dry_run=dry_run, printer_cmd=printer_cmd, no_chain=no_chain)
    return process_label_batch(labels, args)
