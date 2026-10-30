"""
Printer module for Accession Label Generator.
Handles ptouch CLI invocation, single and batch label processing, USB status polling,
and chain/precut options.
"""

import subprocess
import sys
import time
from pathlib import Path
from accession_labeler.renderer import (
    LABELS_DIR,
    CANVAS_HEIGHT,
    load_template_text_baselines,
    get_fonts,
    calculate_label_width,
    render_pillow,
    generate_svg,
    render_svg_to_png,
)


def check_printer_ready(timeout=1):
    """
    Queries ptouch info to check printer connection and readiness.
    Returns (is_ready, status_message).
    """
    try:
        res = subprocess.run(
            ["ptouch", "info", "--timeout", str(timeout)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode == 0:
            return True, "Ready"
        err = res.stderr.strip() or res.stdout.strip() or "Printer not ready"
        return False, err
    except FileNotFoundError:
        return False, "ptouch command not found"
    except Exception as e:
        return False, str(e)


def wait_for_printer_ready(max_timeout=15.0, poll_interval=0.25):
    """
    Actively checks printer status via 'ptouch info' until it responds with a ready status.
    Avoids arbitrary sleep delays by proceeding as soon as the printer finishes cycling.
    """
    start_time = time.time()
    while time.time() - start_time < max_timeout:
        ready, _ = check_printer_ready(timeout=1)
        if ready:
            return True
        time.sleep(poll_interval)
    return False


def print_label(
    png_filepath,
    printer_cmd="ptouch print --timeout 5 --image {file}",
    dry_run=False,
    chain=False,
    precut=False,
    max_retries=2
):
    """Invokes ptouch CLI to send label PNG to the printer with automatic retry on busy status."""
    cmd_template = printer_cmd
    if "ptouch print" in cmd_template and "--timeout" not in cmd_template:
        cmd_template = cmd_template.replace("ptouch print", "ptouch print --timeout 5")

    chain_arg = "--chain" if chain else ""
    precut_arg = "--precut" if precut else ""

    if "{file}" in cmd_template:
        kwargs = {"file": str(png_filepath)}
        if "{chain}" in cmd_template:
            kwargs["chain"] = chain_arg
        if "{precut}" in cmd_template:
            kwargs["precut"] = precut_arg
        formatted_cmd = cmd_template.format(**kwargs)
        if "{chain}" not in cmd_template and chain:
            formatted_cmd += " --chain"
        if "{precut}" not in cmd_template and precut:
            formatted_cmd += " --precut"
    else:
        formatted_cmd = f"{cmd_template} {png_filepath}"
        if chain:
            formatted_cmd += " --chain"
        if precut:
            formatted_cmd += " --precut"

    formatted_cmd = " ".join(formatted_cmd.split())
    print(f"  [Print Command]: {formatted_cmd}")

    if dry_run:
        print("  [Dry Run]:       Command not executed.")
        return True

    for attempt in range(max_retries + 1):
        res = subprocess.run(formatted_cmd, shell=True)
        if res.returncode == 0:
            return True
        if attempt < max_retries:
            print(f"  Printer busy or cutter cycling (exit {res.returncode}). Retrying in 2s ({attempt + 1}/{max_retries})...", file=sys.stderr)
            time.sleep(2.0)

    return False


def process_single_label(
    year_str,
    rest_str,
    args,
    year_y=None,
    id_y=None,
    font_year=None,
    font_id=None,
    chain=False,
    precut=False,
    total_count=1
):
    """Renders and prints a single label for given year and rest identifier."""
    if year_y is None or id_y is None:
        year_y, id_y = load_template_text_baselines()
    if font_year is None or font_id is None:
        font_year, font_id = get_fonts()

    if year_str.isdigit():
        year_str = year_str.zfill(4)

    full_id = f"{year_str}.{rest_str}"
    width_setting = getattr(args, "width", "auto")
    width = calculate_label_width(year_str, rest_str, font_year, font_id, width_setting)

    print(f"\nProcessing Label: {full_id}")
    print(f"  Canvas Size: {width}x{CANVAS_HEIGHT} px")

    output_arg = getattr(args, "output", None)
    svg_output_arg = getattr(args, "svg_output", None)
    engine_setting = getattr(args, "engine", "pillow")
    dry_run = getattr(args, "dry_run", False)
    printer_cmd = getattr(args, "printer_cmd", "ptouch print --image {file}")

    if output_arg:
        out_path = Path(output_arg).resolve()
        if total_count > 1:
            if "{id}" in str(output_arg):
                output_png = Path(str(output_arg).format(id=full_id)).resolve()
            else:
                output_png = out_path.with_name(f"{out_path.stem}_{full_id}{out_path.suffix}").resolve()
        else:
            output_png = out_path
    else:
        LABELS_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"label_{full_id}.png"
        output_png = (LABELS_DIR / filename).resolve()

    if engine_setting == "svg":
        svg_str = generate_svg(year_str, rest_str, width, year_y, id_y)
        tmp_svg = output_png.with_suffix(".tmp.svg")
        with open(tmp_svg, "w") as f:
            f.write(svg_str)
        render_svg_to_png(tmp_svg, output_png)
        if tmp_svg.exists() and not svg_output_arg:
            tmp_svg.unlink()
    else:  # pillow (default)
        img_1bit = render_pillow(year_str, rest_str, width, year_y, id_y)
        img_1bit.save(output_png)

    print(f"  PNG Saved:   {output_png}")

    if svg_output_arg:
        svg_path = Path(svg_output_arg).resolve()
        if total_count > 1:
            svg_path = svg_path.with_name(f"{svg_path.stem}_{full_id}{svg_path.suffix}").resolve()
        with open(svg_path, "w") as f:
            f.write(generate_svg(year_str, rest_str, width, year_y, id_y))
        print(f"  SVG Saved:   {svg_path}")

    if dry_run:
        print_label(output_png, printer_cmd=printer_cmd, dry_run=True, chain=chain, precut=precut)
    else:
        print("  Printing label via ptouch...")
        success = print_label(output_png, printer_cmd=printer_cmd, dry_run=False, chain=chain, precut=precut)
        if not success:
            print("  Printer command returned non-zero exit status.", file=sys.stderr)
            return False

    return True


def process_label_batch(
    label_list,
    args,
    year_y=None,
    id_y=None,
    font_year=None,
    font_id=None
):
    """
    Renders and prints a sequence of labels.
    By default, ranges/batches use Brother's chain printing pipeline:
      - Label 0: --chain (printed and held in mechanism, 1-label lag)
      - Middle labels (1..total-2): --chain --precut (cuts previous label, prints current, held)
      - Last label (total-1): --precut (cuts previous label, prints last label, feeds and cuts)
    Between labels, actively queries printer readiness via 'ptouch info' so the cutter
    completes its cycle without USB connection errors.
    If --no-chain is specified, prints each label with independent cut and feed cycles.
    """
    if year_y is None or id_y is None:
        year_y, id_y = load_template_text_baselines()
    if font_year is None or font_id is None:
        font_year, font_id = get_fonts()

    total = len(label_list)
    no_chain = getattr(args, "no_chain", False)
    dry_run = getattr(args, "dry_run", False)
    printer_cmd = getattr(args, "printer_cmd", "ptouch print --image {file}")

    enable_chain = not no_chain and (total > 1)

    for i, (yr, rst) in enumerate(label_list):
        if i > 0 and not dry_run and "ptouch" in printer_cmd:
            sys.stdout.write("  Waiting for cutter to finish...")
            sys.stdout.flush()
            if wait_for_printer_ready(max_timeout=15.0):
                print(" ready.")
            else:
                print(" timeout warning (proceeding anyway).", file=sys.stderr)

        if enable_chain:
            is_chain = (i < total - 1)
            is_precut = (i > 0)
        else:
            is_chain = False
            is_precut = False

        success = process_single_label(
            yr, rst, args, year_y, id_y, font_year, font_id,
            chain=is_chain, precut=is_precut, total_count=total
        )
        if not success:
            return False
    return True


def get_system_printers():
    """
    Returns list of available CUPS printer queue names using lpstat.
    """
    try:
        res = subprocess.run(["lpstat", "-e"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            printers = [p.strip() for p in res.stdout.splitlines() if p.strip()]
            if printers:
                return printers
        res_p = subprocess.run(["lpstat", "-p"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res_p.returncode == 0:
            printers = []
            for line in res_p.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "printer":
                    printers.append(parts[1])
            if printers:
                return printers
    except Exception:
        pass
    return []


def print_pdf_to_system_printer(pdf_filepath, printer_name=None, dry_run=False, verbose=True):
    """
    Sends generated PDF sheet to standard system printer using CUPS 'lpr' or 'lp'.
    Auto-detects available CUPS system printers if no default is configured.
    Returns (success: bool, message: str).
    """
    pdf_path = Path(pdf_filepath).resolve()
    if not pdf_path.exists():
        return False, f"PDF file not found: {pdf_path}"

    available = get_system_printers()
    if not printer_name and available:
        printer_name = available[0]

    cmd = ["lpr", "-o", "fit-to-page=false", "-o", "natural-scaling=100"]
    if printer_name:
        cmd.extend(["-P", printer_name])
    cmd.append(str(pdf_path))

    cmd_str = " ".join(cmd)
    if verbose:
        print(f"  [PDF Print Command]: {cmd_str}")

    if dry_run:
        if verbose:
            print("  [Dry Run]: Command not executed.")
        return True, f"Dry run complete ({cmd_str})"


    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            dest_info = f" to printer '{printer_name}'" if printer_name else ""
            return True, f"Job sent{dest_info}"

        cmd_lp = ["lp", "-o", "fit-to-page=false", "-o", "natural-scaling=100"]
        if printer_name:
            cmd_lp.extend(["-d", printer_name])
        cmd_lp.append(str(pdf_path))
        res_lp = subprocess.run(cmd_lp, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res_lp.returncode == 0:
            dest_info = f" to printer '{printer_name}'" if printer_name else ""
            return True, f"Job sent{dest_info} via lp"


        err_msg = res.stderr.strip() or res_lp.stderr.strip() or "Print command failed"
        if "No default destination" in err_msg and not available:
            return False, "No default printer set in CUPS. PDF saved to labels/disc_hubs.pdf for manual printing."
        return False, err_msg
    except Exception as e:
        return False, str(e)


