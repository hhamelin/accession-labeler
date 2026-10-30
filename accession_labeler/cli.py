"""
CLI entry point for Accession Label Generator.
Parses command line arguments and routes execution to TUI mode or batch CLI printing.
"""

import argparse
import sys
from accession_labeler.parser import parse_identifiers
from accession_labeler.printer import process_label_batch
from accession_labeler.renderer import load_template_text_baselines, get_fonts
from accession_labeler.tui import run_tui_mode


def main():
    parser = argparse.ArgumentParser(
        description="Accession Label Generator (ptouch integration)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s                                    # Full-screen interactive TUI menu
  %(prog)s 1.1.1                              # Auto zero-pads to 0001.01.01 and prints
  %(prog)s 2026.1.1A1,A3,A4 --dry-run         # Multiple specific parts (A1, A3, A4)
  %(prog)s 2026.1.1A1-3,B1-3 --dry-run        # Multi-prefix ranges (A1-A3, B1-B3) chain printed
  %(prog)s 2026.1.1A1-3 2026.1.2B1-2 --dry-run # Multiple items on one command line
  %(prog)s 2026.1.1A1 -o custom.png           # Save with specific filename
"""
    )
    parser.add_argument("identifier", nargs="*", help="Full identifier(s) (e.g. 1.1.1, 2026.01.01A1,A3,A4 or 2026.01.01A1-3,B1-3)")
    parser.add_argument("--year", help="Year")
    parser.add_argument("--item", help="Item number")
    parser.add_argument("--batch", help="Batch number")
    parser.add_argument("--part", help="Part designation(s) (e.g. 'A1,A3,A4' or 'A1-3,B1-3')")

    parser.add_argument("-o", "--output", default=None, help="Custom output PNG file path (default: labels/label_IDENTIFIER.png)")
    parser.add_argument("--svg-output", help="Save generated SVG file path (optional)")
    parser.add_argument("--engine", choices=["auto", "pillow", "svg"], default="pillow", help="Rendering engine (default: pillow)")
    parser.add_argument("--width", default="auto", help="Label width in pixels ('auto' or integer e.g. 112)")

    # Printing flags
    parser.add_argument("-n", "--dry-run", "--no-print", dest="dry_run", action="store_true", help="Generate label without sending to printer (dry run)")
    parser.add_argument("--no-chain", action="store_true", help="Disable chain printing for ranges (print each label with separate cuts)")
    parser.add_argument("--printer-cmd", default="ptouch print --image {file}", help="Custom printer command template (default: 'ptouch print --image {file}')")

    # Disc Hub sheet flags
    parser.add_argument("--disc-hub", action="store_true", help="Render Compulabel #312862 Disc Hub Label PDF sheet")
    parser.add_argument("--start-pos", type=int, default=1, help="Starting position on label sheet (1-26, default: 1)")
    parser.add_argument("--hub-pdf", default="labels/disc_hubs.pdf", help="Output PDF file path for disc hub sheet (default: labels/disc_hubs.pdf)")
    parser.add_argument("--show-guides", action="store_true", help="Draw alignment guide circles on PDF (for testing on plain paper)")
    parser.add_argument("--print-pdf", action="store_true", help="Send generated PDF directly to system printer (lpr/lp)")
    parser.add_argument("--offset-x", type=float, default=0.0, help="Calibration X shift in inches (+ right, - left)")
    parser.add_argument("--offset-y", type=float, default=0.0, help="Calibration Y shift in inches (+ up, - down)")

    args = parser.parse_args()
    year_y, id_y = load_template_text_baselines()
    font_year, font_id = get_fonts()

    is_interactive = not args.identifier and not (args.year and args.item and args.batch)

    if is_interactive:
        run_tui_mode(args, year_y, id_y, font_year, font_id)
        sys.exit(0)

    labels_to_generate = []
    try:
        if args.identifier:
            for ident in args.identifier:
                labels_to_generate.extend(parse_identifiers(identifier_str=ident))
        elif args.year and args.item and args.batch:
            labels_to_generate.extend(
                parse_identifiers(year=args.year, item=args.item, batch=args.batch, part=args.part)
            )
        else:
            parser.print_help(sys.stderr)
            sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}\n", file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)

    if args.disc_hub:
        from accession_labeler.hub_config import Compulabel312862Config
        from accession_labeler.hub_renderer import generate_hub_pdf
        from accession_labeler.printer import print_pdf_to_system_printer

        config = Compulabel312862Config()
        if args.offset_x != 0.0 or args.offset_y != 0.0:
            config.disc_spec.offset_x_in = args.offset_x
            config.disc_spec.offset_y_in = args.offset_y

        print(f"\nProcessing Disc Hub Sheet for {len(labels_to_generate)} label(s)...")
        pdf_path = generate_hub_pdf(
            labels_to_generate,
            args.hub_pdf,
            start_pos=args.start_pos,
            draw_guides=args.show_guides,
            config=config
        )

        print(f"  Disc Hub PDF Saved: {pdf_path}")

        if args.print_pdf:
            ok, msg = print_pdf_to_system_printer(pdf_path, dry_run=args.dry_run)
            if ok:
                print("  Disc Hub PDF sent to system printer.")
            else:
                print(f"  Print error: {msg}", file=sys.stderr)
    else:
        process_label_batch(labels_to_generate, args, year_y, id_y, font_year, font_id)


if __name__ == "__main__":
    main()

