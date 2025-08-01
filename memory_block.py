# memory_block.py

import curses
import psutil
import subprocess
import re
import os
import glob
from utils import addstr_clipped, draw_box, draw_bar, format_bytes


def parse_dmidecode_memory():
    modules = []
    err_msg = None
    try:
        sp = subprocess.run(["which", "dmidecode"], capture_output=True, check=False)
        if sp.returncode != 0:
            return [{"Error": "dmidecode not found (install it)"}]
        result = subprocess.run(
            ["dmidecode", "--type", "17"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2.0,
        )
        if result.returncode != 0:
            stderr_line = (
                result.stderr.strip().splitlines()[0]
                if result.stderr
                else f"ret_code={result.returncode}"
            )
            return [{"Error": f"dmidecode failed ({stderr_line[:40]})"}]
        if result.stdout:
            current_module = None
            lines = result.stdout.splitlines()
            for line in lines:
                line = line.strip()
                if line.startswith("Memory Device"):
                    if current_module:
                        modules.append(current_module)
                    current_module = {
                        "Size": "Empty",
                        "Type": "Unknown",
                        "Speed": "Unknown",
                        "Manufacturer": "N/A",
                        "Part Number": "N/A",
                        "Form Factor": "Unknown",
                    }
                    continue
                if current_module is None:
                    continue
                if m := re.match(r"Size:\s+(No Module Installed)", line):
                    current_module = None
                    continue
                elif m := re.match(
                    r"Size:\s*([\d]+\s*(?:MB|GB|TB))", line, re.IGNORECASE
                ):
                    current_module["Size"] = m.group(1)
                elif m := re.match(r"Type:\s*(\S+.*)", line):
                    current_module["Type"] = m.group(1).strip()
                elif m := re.match(
                    r"(?:Configured\s+)?Memory\s+Speed:\s*([\d]+\s*(?:MT/s|MHz))",
                    line,
                    re.IGNORECASE,
                ):
                    current_module["Speed"] = m.group(1)
                elif m := re.match(
                    r"Speed:\s*([\d]+\s*(?:MT/s|MHz))", line, re.IGNORECASE
                ):
                    current_module["Speed"] = m.group(1)
                elif m := re.match(r"Manufacturer:\s*(.+)", line):
                    current_module["Manufacturer"] = m.group(1).strip()
                elif m := re.match(r"Part\s+Number:\s*(.+)", line):
                    current_module["Part Number"] = m.group(1).strip()
                elif m := re.match(r"Form\s+Factor:\s*(.+)", line):
                    current_module["Form Factor"] = m.group(1).strip()
            if current_module and current_module["Size"] != "Empty":
                modules.append(current_module)
            modules = [m for m in modules if m.get("Size") != "Empty"]
    except FileNotFoundError:
        err_msg = "dmidecode not found (install it)"
    except subprocess.TimeoutExpired:
        err_msg = "dmidecode timed out"
    except Exception as e:
        err_msg = f"dmidecode err: {str(e)[:50]}"
    if err_msg:
        return [{"Error": err_msg}]
    elif not modules:
        return [{"Error": "No memory modules detected / readable."}]
    else:
        return modules


def draw_memory_block_content(win, key_attr, value_attr, bar_colors):
    h, w = win.getmaxyx()
    draw_box(win, "Memory", key_attr)
    current_row = 1
    col_width = w // 2
    col1_x, col2_x = 1, col_width + 1
    bar_width = max(0, w - 2 - 8)

    try:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        if current_row < h - 1:
            rp = mem.percent
            ruc = mem.total - mem.available
            ruh = format_bytes(ruc)
            rth = format_bytes(mem.total)
            rl = f"RAM: {ruh}/{rth}"
            rlp = f" ({rp:.1f}%)"
            addstr_clipped(win, current_row, 1, rl, key_attr)
            px = 1 + len(rl) + 1
            addstr_clipped(
                win, current_row, px, rlp[: w - px - 1], value_attr | curses.A_BOLD
            )
        bx = 1
        by = current_row + 1
        if by < h - 1 and bar_width > 0:
            draw_bar(win, by, bx, bar_width, mem.percent, w, bar_colors, True)
            current_row += 2
        else:
            current_row += 1
        dsr = current_row
        adc = 0
        dts = [
            ("Available", mem.available, ""),
            ("Active", getattr(mem, "active", None), ""),
            ("Free", mem.free, ""),
            ("Inactive", getattr(mem, "inactive", None), ""),
            ("Cached", getattr(mem, "cached", None), ""),
            ("Buffers", getattr(mem, "buffers", None), ""),
            ("Shared", getattr(mem, "shared", None), ""),
            ("Slab", getattr(mem, "slab", None), ""),
        ]
        for lbl, val, unt in dts:
            if current_row >= h - 1:
                break
            isc1 = adc % 2 == 0
            tx = col1_x if isc1 else col2_x
            max_dw = max(1, (col_width - 2 if isc1 else w - tx - 1) - len(lbl) - 2)
            vs = (
                format_bytes(val)
                if val is not None and unt == ""
                else f"{val}{unt}"
                if val is not None
                else "N/A"
            )
            ln = f"{lbl[:9]+':':<10} {vs}"
            att = value_attr if val is not None else value_attr | curses.A_DIM
            addstr_clipped(win, current_row, tx, ln[: (len(lbl) + 2 + max_dw)], att)
            adc += 1
            if not isc1:
                current_row += 1
        if adc > 0 and adc % 2 != 0:
            current_row += 1
        if swap.total > 0 and current_row < h - 2:
            if current_row < h - 1:
                addstr_clipped(
                    win, current_row, 1, "-" * (w - 2), value_attr | curses.A_DIM
                )
                current_row += 1
            if current_row < h - 1:
                su = format_bytes(swap.used)
                st = format_bytes(swap.total)
                sl = f"SWAP: {su}/{st}"
                sp = f" ({swap.percent:.1f}%)"
                addstr_clipped(win, current_row, 1, sl, key_attr)
                px = 1 + len(sl) + 1
                addstr_clipped(
                    win, current_row, px, sp[: w - px - 1], value_attr | curses.A_BOLD
                )
            by = current_row + 1
            bx = 1
            if by < h - 1 and bar_width > 0:
                draw_bar(win, by, bx, bar_width, swap.percent, w, bar_colors, True)
                current_row += 2
            else:
                current_row += 1
            if current_row < h - 1:
                sin = format_bytes(swap.sin)
                sout = format_bytes(swap.sout)
                l1 = f" Swapped In: {sin}"
                l2 = f" Swapped Out: {sout}"
                addstr_clipped(
                    win, current_row, col1_x, l1[: col_width - 2], value_attr
                )
                addstr_clipped(
                    win, current_row, col2_x, l2[: w - col2_x - 1], value_attr
                )
                current_row += 1

        if current_row < h - 3:
            addstr_clipped(win, current_row, 1, "=" * (w - 2), key_attr | curses.A_DIM)
            current_row += 1
            addstr_clipped(win, current_row, 1, "RAM Modules (dmidecode):", key_attr)
            current_row += 1

        phys_mem_info = parse_dmidecode_memory()

        if phys_mem_info and current_row < h - 1:
            first_item = phys_mem_info[0]
            if "Error" in first_item:
                err_msg = first_item["Error"]
                addstr_clipped(
                    win, current_row, 1, err_msg[: w - 2], curses.color_pair(4)
                )
                current_row += 1
            elif len(phys_mem_info) > 0:
                header = f"{'#':<2} {'Size':<10} {'Type':<8} {'Speed':<10} {'Manufacturer':<18} {'Part Number'}"
                if current_row < h - 1:
                    addstr_clipped(win, current_row, 1, header[: w - 2], key_attr)
                    current_row += 1
                    max_modules_to_show = h - current_row - 1
                    modules_shown = 0
                    for i, mod in enumerate(phys_mem_info):
                        if modules_shown >= max_modules_to_show:
                            break
                        size = mod.get("Size", "?")
                        mtype = mod.get("Type", "?")
                        speed = mod.get("Speed", "?")
                        manuf = mod.get("Manufacturer", "N/A")
                        part = mod.get("Part Number", "N/A")
                        manuf = manuf[:16] + ".." if len(manuf) > 18 else manuf
                        max_part_len = max(
                            5, w - 2 - (2 + 1 + 10 + 1 + 8 + 1 + 10 + 1 + 18 + 1)
                        )
                        part = part[:max_part_len]
                        mod_line = f"{i:<2} {size:<10} {mtype:<8} {speed:<10} {manuf:<18} {part}"
                        addstr_clipped(
                            win, current_row, 1, mod_line[: w - 2], value_attr
                        )
                        current_row += 1
                        modules_shown += 1
    except curses.error:
        pass
    except Exception as e:
        error_y = h - 2
        if error_y > 0:
            addstr_clipped(
                win, error_y, 1, f"Mem Err: {str(e)[:w - 10]}", curses.color_pair(4)
            )
