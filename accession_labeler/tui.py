"""
Curses TUI module for Accession Label Generator.
Provides interactive wizard, manual entry, tree/flat queue visualization, and chain printing.
"""

import curses
import os
import re
from accession_labeler.parser import (
    parse_identifiers,
    parse_range_expression,
    expand_part_designation,
)
from accession_labeler.printer import process_label_batch
from accession_labeler.renderer import load_template_text_baselines, get_fonts


def build_tree_lines(queue):
    """
    Converts queue of (year, rest_str) into (lines, line_meta) for TUI display and accurate deletion.
    line_meta is a list of matching queue indices for each tree line.
    """
    if not queue:
        return ["(Print queue is currently empty. Press [A] to add labels via Wizard or [M] for manual entry.)"], [[]]

    parsed_items = []
    for idx, (yr, rst) in enumerate(queue):
        m = re.match(r"^(\d+)\.(\d+)(.*)$", rst)
        if m:
            b, i, p = m.groups()
        else:
            b, i, p = "00", rst, ""
        parsed_items.append((yr, b, i, p, idx))

    tree = {}
    for yr, b, i, p, idx in parsed_items:
        if yr not in tree:
            tree[yr] = {}
        if b not in tree[yr]:
            tree[yr][b] = {}
        if i not in tree[yr][b]:
            tree[yr][b][i] = []
        tree[yr][b][i].append((p, idx))

    lines = []
    line_meta = []

    year_keys = sorted(tree.keys())
    for y_idx, y in enumerate(year_keys):
        y_prefix = "└── " if y_idx == len(year_keys) - 1 else "├── "
        lines.append(f"{y_prefix}Year {y}")
        y_indices = [idx for yr, b, i, p, idx in parsed_items if yr == y]
        line_meta.append(y_indices)

        batch_keys = sorted(tree[y].keys())
        for b_idx, b in enumerate(batch_keys):
            b_branch = "    " if y_idx == len(year_keys) - 1 else "│   "
            b_prefix = b_branch + ("└── " if b_idx == len(batch_keys) - 1 else "├── ")
            lines.append(f"{b_prefix}Batch {b}")
            b_indices = [idx for yr, b_code, i, p, idx in parsed_items if yr == y and b_code == b]
            line_meta.append(b_indices)

            item_keys = sorted(tree[y][b].keys())
            for i_idx, item_num in enumerate(item_keys):
                i_branch = b_branch + ("    " if b_idx == len(batch_keys) - 1 else "│   ")
                i_prefix = i_branch + ("└── " if i_idx == len(item_keys) - 1 else "├── ")
                parts_list = [p if p else "(Whole Item)" for p, idx in tree[y][b][item_num]]
                parts_str = ", ".join(parts_list)
                lines.append(f"{i_prefix}Item {item_num}: {parts_str}")
                i_indices = [idx for p, idx in tree[y][b][item_num]]
                line_meta.append(i_indices)

    return lines, line_meta


def run_tui_mode(args, year_y=None, id_y=None, font_year=None, font_id=None):
    """
    Runs full-screen Curses TUI menu for accession label building and chain printing.
    """
    os.environ.setdefault("ESCDELAY", "25")

    if year_y is None or id_y is None:
        year_y, id_y = load_template_text_baselines()
    if font_year is None or font_id is None:
        font_year, font_id = get_fonts()

    def safe_addstr(win, y, x, text, attr=0):
        h, w = win.getmaxyx()
        if 0 <= y < h and 0 <= x < w:
            max_chars = w - x - 1
            if max_chars > 0:
                try:
                    win.addstr(y, x, text[:max_chars], attr)
                except curses.error:
                    pass

    def draw_dialog(stdscr, title, prompt, default_val="", hint=""):
        curses.curs_set(1)
        max_y, max_x = stdscr.getmaxyx()

        prompt_lines = [p.strip() for p in prompt.split("\n") if p.strip()]
        box_w = min(74, max_x - 4)
        box_h = len(prompt_lines) + (1 if hint else 0) + 5
        box_y = max(0, (max_y - box_h) // 2)
        box_x = max(0, (max_x - box_w) // 2)

        win = curses.newwin(box_h, box_w, box_y, box_x)
        win.keypad(True)
        buffer = list(default_val)

        while True:
            win.erase()
            win.box()
            safe_addstr(win, 1, 2, f" {title} ", curses.A_BOLD)

            row = 2
            for line in prompt_lines:
                safe_addstr(win, row, 2, line)
                row += 1

            if hint:
                safe_addstr(win, row, 2, hint, curses.color_pair(5) if curses.has_colors() else curses.A_DIM)
                row += 1

            input_str = "".join(buffer)
            disp_str = input_str[-(box_w - 6):] if len(input_str) > (box_w - 6) else input_str
            safe_addstr(win, row, 2, "> " + disp_str + "_", curses.color_pair(2) if curses.has_colors() else curses.A_REVERSE)
            row += 1
            safe_addstr(win, row, 2, "[Enter] Accept   [Esc] Back", curses.A_DIM)

            win.refresh()
            ch = win.getch()
            if ch in (10, 13, curses.KEY_ENTER):
                curses.curs_set(0)
                return "".join(buffer).strip()
            elif ch == 27:  # ESC
                curses.curs_set(0)
                return None
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                if buffer:
                    buffer.pop()
            elif 32 <= ch <= 126:
                buffer.append(chr(ch))

    def draw_confirm(stdscr, title, prompt):
        curses.curs_set(0)
        max_y, max_x = stdscr.getmaxyx()
        box_w = min(64, max_x - 4)
        box_h = 6
        box_y = max(0, (max_y - box_h) // 2)
        box_x = max(0, (max_x - box_w) // 2)

        win = curses.newwin(box_h, box_w, box_y, box_x)
        win.keypad(True)

        while True:
            win.erase()
            win.box()
            safe_addstr(win, 1, 2, f" {title} ", curses.A_BOLD)
            safe_addstr(win, 3, 2, prompt)
            safe_addstr(win, 4, 2, "[Y] Yes   [N/Esc] No", curses.A_BOLD)
            win.refresh()
            ch = win.getch()
            if ch in (ord('y'), ord('Y'), 10, 13):
                return True
            elif ch in (ord('n'), ord('N'), 27):
                return False

    def run_wizard(stdscr, last_year="2026"):
        current_year = last_year
        all_generated_tuples = []
        last_parts = ""

        while True:
            # Step 1: Year(s)
            years_str = draw_dialog(
                stdscr,
                "Wizard 1/4: Year(s)",
                "Enter Year(s) (e.g. 2024 or 2024-2026):",
                default_val=current_year,
                hint="Press [Esc] to return."
            )
            if years_str is None:
                return all_generated_tuples, current_year

            years = parse_range_expression(years_str, zfill_len=4)
            if not years:
                years = [current_year]
            current_year = years[-1]

            for y in years:
                while True:
                    # Step 2: Batch(es)
                    batches_str = draw_dialog(
                        stdscr,
                        "Wizard 2/4: Batch(es)",
                        f"Year: {y}\nEnter Batch number(s) (e.g. 12 or 12-14):",
                        default_val="12",
                        hint="Press [Esc] to return."
                    )
                    if batches_str is None:
                        break

                    batches = parse_range_expression(batches_str, zfill_len=2)
                    if not batches:
                        continue

                    batch_completed = False
                    for b in batches:
                        # Step 3: Item(s) for Batch b
                        while True:
                            items_str = draw_dialog(
                                stdscr,
                                "Wizard 3/4: Item(s)",
                                f"Year: {y} | Batch: {b}\nEnter Item(s) for Batch {b} (e.g. 5 or 5-10):",
                                default_val="5",
                                hint="Press [Esc] to return."
                            )
                            if items_str is None:
                                break

                            items = parse_range_expression(items_str, zfill_len=2)
                            if not items:
                                continue

                            # Step 4: Part(s) for EACH Item in items
                            cancelled_item = False
                            for idx, item_num in enumerate(items):
                                while True:
                                    item_count_info = f" ({idx + 1}/{len(items)})" if len(items) > 1 else ""
                                    parts_str = draw_dialog(
                                        stdscr,
                                        f"Wizard 4/4: Part(s) for Item {item_num}{item_count_info}",
                                        f"Year: {y} | Batch: {b} | Item: {item_num}\nEnter Part(s) (e.g. A1-3, B1 or *, A1-3; or leave blank for Whole Item):",
                                        default_val=last_parts,
                                        hint="Press [Esc] to return."
                                    )
                                    if parts_str is None:
                                        cancelled_item = True
                                        break

                                    last_parts = parts_str
                                    subparts = expand_part_designation(parts_str)
                                    for sp in subparts:
                                        all_generated_tuples.append((y, f"{b}.{item_num}{sp}"))
                                    break

                                if cancelled_item:
                                    break

                            if not cancelled_item:
                                batch_completed = True
                                break

                            if cancelled_item:
                                break

                    if batch_completed:
                        return all_generated_tuples, current_year

            return all_generated_tuples, current_year

    def tui_main(stdscr):
        try:
            curses.set_escdelay(25)
        except AttributeError:
            pass
        curses.curs_set(0)
        stdscr.keypad(True)
        curses.use_default_colors()

        if curses.has_colors():
            curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
            curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
            curses.init_pair(3, curses.COLOR_GREEN, -1)
            curses.init_pair(4, curses.COLOR_YELLOW, -1)
            curses.init_pair(5, curses.COLOR_CYAN, -1)

        queue = []
        selected_index = 0
        scroll_offset = 0
        view_mode = "tree"
        last_year = "2026"
        status_msg = "Welcome to Accession Labeler TUI"

        while True:
            stdscr.erase()
            max_y, max_x = stdscr.getmaxyx()

            dry_run_flag = getattr(args, "dry_run", False)
            printer_cmd_str = getattr(args, "printer_cmd", "ptouch print --image {file}")
            mode_str = "[DRY RUN]" if dry_run_flag else "[LIVE PRINT]"
            header = f" ACCESSION LABELER TUI  |  Printer: {printer_cmd_str}  |  Mode: {mode_str} "
            safe_addstr(stdscr, 0, 0, header.ljust(max_x), curses.color_pair(1) if curses.has_colors() else curses.A_REVERSE)

            dry_status = "ON" if dry_run_flag else "OFF"
            safe_addstr(stdscr, 1, 1, "[A] Add Branch (Wizard)  [M] Manual Entry  [V] Toggle View  [C] Clear Queue", curses.A_BOLD)
            safe_addstr(stdscr, 2, 1, f"[P] Print Chain Job     [T] Dry Run: {dry_status:<3}  [X/Del] Delete Selected  [Q] Quit", curses.A_BOLD)
            safe_addstr(stdscr, 3, 0, "─" * max_x, curses.A_DIM)

            view_title = f" STAGED LABELS ({view_mode.upper()} VIEW - {len(queue)} items queued) "
            safe_addstr(stdscr, 4, 1, view_title, curses.color_pair(5) if curses.has_colors() else curses.A_BOLD)

            content_h = max(1, max_y - 8)

            if view_mode == "tree":
                tree_lines, line_meta = build_tree_lines(queue)
                if selected_index >= len(tree_lines):
                    selected_index = max(0, len(tree_lines) - 1)
                if selected_index < scroll_offset:
                    scroll_offset = selected_index
                elif selected_index >= scroll_offset + content_h:
                    scroll_offset = selected_index - content_h + 1

                for idx in range(scroll_offset, min(len(tree_lines), scroll_offset + content_h)):
                    row_y = 5 + (idx - scroll_offset)
                    attr = curses.color_pair(2) if (idx == selected_index and queue) else 0
                    safe_addstr(stdscr, row_y, 2, tree_lines[idx], attr)

            else:
                if not queue:
                    safe_addstr(stdscr, 5, 2, "(Print queue is empty. Press [A] to add labels.)", curses.A_DIM)
                else:
                    if selected_index >= len(queue):
                        selected_index = max(0, len(queue) - 1)
                    if selected_index < scroll_offset:
                        scroll_offset = selected_index
                    elif selected_index >= scroll_offset + content_h:
                        scroll_offset = selected_index - content_h + 1

                    for idx in range(scroll_offset, min(len(queue), scroll_offset + content_h)):
                        row_y = 5 + (idx - scroll_offset)
                        yr, rst = queue[idx]
                        full_id = f"{yr}.{rst}"
                        item_str = f"[{idx + 1:2d}]  {full_id:<20}"
                        attr = curses.color_pair(2) if idx == selected_index else 0
                        safe_addstr(stdscr, row_y, 2, item_str, attr)

            safe_addstr(stdscr, max_y - 2, 0, "─" * max_x, curses.A_DIM)
            safe_addstr(stdscr, max_y - 1, 1, f"Status: {status_msg}", curses.color_pair(4) if dry_run_flag else curses.color_pair(3))

            stdscr.refresh()

            ch = stdscr.getch()
            if ch in (ord('q'), ord('Q')):
                if not queue or draw_confirm(stdscr, "Quit TUI", f"Quit and discard {len(queue)} staged label(s)?"):
                    break
            elif ch in (ord('a'), ord('A')):
                new_tuples, last_year = run_wizard(stdscr, last_year)
                if new_tuples:
                    queue.extend(new_tuples)
                    status_msg = f"Added {len(new_tuples)} label(s) to queue. Total: {len(queue)}"
            elif ch in (ord('m'), ord('M')):
                syntax_str = draw_dialog(
                    stdscr,
                    "Manual Entry",
                    "Enter identifier(s) (e.g. 2024.12.5A1-3,B1-3 or 2024.14.1-3):",
                    default_val=""
                )
                if syntax_str:
                    try:
                        parsed = parse_identifiers(identifier_str=syntax_str)
                        queue.extend(parsed)
                        status_msg = f"Manual entry added {len(parsed)} label(s). Total: {len(queue)}"
                    except Exception as err:
                        status_msg = f"Syntax Error: {err}"
            elif ch in (ord('v'), ord('V'), 9):
                view_mode = "flat" if view_mode == "tree" else "tree"
                status_msg = f"Switched to {view_mode.upper()} view"
            elif ch in (ord('t'), ord('T')):
                args.dry_run = not getattr(args, "dry_run", False)
                status_msg = f"Dry Run mode set to {args.dry_run}"
            elif ch in (ord('c'), ord('C')):
                if queue and draw_confirm(stdscr, "Clear Queue", f"Clear all {len(queue)} queued labels?"):
                    queue.clear()
                    selected_index = 0
                    scroll_offset = 0
                    status_msg = "Queue cleared."
            elif ch in (ord('x'), ord('X'), curses.KEY_DC, 127, 8):
                if queue:
                    if view_mode == "tree":
                        tree_lines, line_meta = build_tree_lines(queue)
                        if 0 <= selected_index < len(line_meta):
                            targets = line_meta[selected_index]
                            if targets:
                                for idx_to_remove in sorted(targets, reverse=True):
                                    if 0 <= idx_to_remove < len(queue):
                                        queue.pop(idx_to_remove)
                                status_msg = f"Removed {len(targets)} label(s) from staged tree."
                                if selected_index >= len(tree_lines) - 1:
                                    selected_index = max(0, len(tree_lines) - 2)
                    else:
                        if 0 <= selected_index < len(queue):
                            removed = queue.pop(selected_index)
                            status_msg = f"Removed label {removed[0]}.{removed[1]}"
                            if selected_index >= len(queue):
                                selected_index = max(0, len(queue) - 1)
            elif ch in (curses.KEY_UP, ord('k')):
                if selected_index > 0:
                    selected_index -= 1
            elif ch in (curses.KEY_DOWN, ord('j')):
                tree_lines, _ = build_tree_lines(queue) if view_mode == "tree" else ([], [])
                max_len = len(tree_lines) if view_mode == "tree" else len(queue)
                if selected_index < max_len - 1:
                    selected_index += 1
            elif ch in (ord('p'), ord('P'), 10, 13):
                if not queue:
                    status_msg = "Queue is empty! Add labels first."
                else:
                    curses.endwin()
                    print("\n" + "=" * 60)
                    print(f" Executing Continuous Chain Print for {len(queue)} Labels")
                    print("=" * 60)
                    success = process_label_batch(queue, args, year_y, id_y, font_year, font_id)
                    print("\n" + "=" * 60)
                    if success:
                        print(" Batch Print Completed Successfully!")
                    else:
                        print(" Print job encountered an error.")
                    print("=" * 60)
                    input("\nPress Enter to return to TUI Menu...")
                    stdscr = curses.initscr()
                    curses.curs_set(0)
                    stdscr.keypad(True)
                    curses.use_default_colors()
                    status_msg = "Print job finished."

    try:
        curses.wrapper(tui_main)
    except (KeyboardInterrupt, EOFError):
        pass
