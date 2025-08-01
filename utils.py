# utils.py

import curses
import psutil
import datetime
import os
import re


V_GRAPH_CHARS = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
BORDER_VERT = "|"
BORDER_HORIZ = "-"
BORDER_CORNER_TL = "+"
BORDER_CORNER_TR = "+"
BORDER_CORNER_BL = "+"
BORDER_CORNER_BR = "+"

bytes_to_gb = lambda b: b / (1024**3) if b is not None else 0.0
bytes_to_mb_f = lambda b: b / (1024 * 1024) if b is not None else 0.0
format_uptime = lambda s: str(datetime.timedelta(seconds=int(s))) if s else "N/A"
format_bytes = lambda b: psutil._common.bytes2human(b) if b is not None else "0B"


def addstr_clipped(win, y, x, text, attr=0):
    try:
        if not win:
            return
        h, w = win.getmaxyx()
        if y >= h or y < 0 or x < 0 or x >= w:
            return
        available_width = w - x
        if available_width <= 0:
            return
        display_text = "".join(
            c if c.isprintable() else "?" for c in str(text)[:available_width]
        )
        try:
            win.addstr(y, x, display_text, attr)
        except curses.error:
            if len(display_text) > 0:
                try:
                    win.addstr(y, x, display_text[:-1], attr)
                except curses.error:
                    pass
    except Exception:
        pass


def draw_box(win, title="", title_attr=0):
    try:
        if not win:
            return
        win.erase()
        win.border()
        h, w = win.getmaxyx()
        if title:
            trimmed_title = title.strip()
            title_len = len(trimmed_title)
            title_x = max(1, min(w - title_len - 4, (w - (title_len + 2)) // 2))
            addstr_clipped(win, 0, title_x, f" {trimmed_title} ", title_attr)
    except curses.error:
        pass
    except Exception:
        pass


def addstr_colored_markup(win, y, start_x, text, default_attr, tag_map):
    try:
        if not win:
            return
        h, w = win.getmaxyx()
        if y >= h or y < 0:
            return
        current_x = start_x
        win.move(y, current_x)
        parts = re.split(r"(</?\w*>)", str(text))
        current_attr = default_attr
        for part in parts:
            if not part:
                continue
            if current_x >= w - 1:
                break
            if part == "</>":
                current_attr = default_attr
            elif part in tag_map:
                current_attr = tag_map[part]
            else:
                remaining_width_on_line = w - current_x - 1
                if remaining_width_on_line <= 0:
                    break
                clipped_part = "".join(
                    c if c.isprintable() else "?"
                    for c in part[:remaining_width_on_line]
                )
                try:
                    win.addstr(clipped_part, current_attr)
                    current_x += len(clipped_part)
                except curses.error:
                    break
    except curses.error:
        pass
    except Exception:
        pass


def draw_bar(win, y, x, width, percent, max_width, colors, show_percent=True):
    try:
        if not win:
            return
        h, w_win = win.getmaxyx()
    except:
        return

    percent_text_len = 7
    min_total_len_no_percent = 3
    min_total_len_with_percent = min_total_len_no_percent + percent_text_len

    if width <= 0 or y >= h or y < 0 or x < 0 or x + min_total_len_no_percent >= w_win:
        return
    if show_percent and x + width + min_total_len_with_percent >= w_win:
        show_percent = False
    if not show_percent and x + width + min_total_len_no_percent >= w_win:
        width = max(0, w_win - x - min_total_len_no_percent - 1)
        if width == 0:
            return

    clamped_percent = max(0.0, min(100.0, percent))
    filled_width = max(0, min(width, int(width * clamped_percent / 100)))

    bar_color_pair = colors.get("low", 0)
    if clamped_percent > 85:
        bar_color_pair = colors.get("high", 0)
    elif clamped_percent > 60:
        bar_color_pair = colors.get("med", 0)

    has_colors = curses.has_colors()
    if has_colors:
        bar_attr = curses.color_pair(bar_color_pair) | curses.A_BOLD
        empty_attr = curses.color_pair(5) | curses.A_DIM
    else:
        bar_attr = curses.A_REVERSE
        empty_attr = curses.A_NORMAL

    bar_str = "#" * filled_width
    empty_str = "-" * (width - filled_width)
    percent_str = f"{clamped_percent:.1f}%".rjust(6) if show_percent else ""
    try:
        addstr_clipped(win, y, x, "[", empty_attr)
        if filled_width > 0:
            addstr_clipped(win, y, x + 1, bar_str, bar_attr)
        if width - filled_width > 0:
            addstr_clipped(win, y, x + 1 + filled_width, empty_str, empty_attr)
        addstr_clipped(win, y, x + 1 + width, "]", empty_attr)
        if show_percent:
            percent_x = x + 1 + width + 2
            if percent_x + len(percent_str) < w_win:
                addstr_clipped(win, y, percent_x, percent_str, bar_attr)
    except curses.error:
        pass
    except Exception:
        pass


def print_clickable_command(win, y, x, text, attr=0):
    """
    Prints a command that the user might want to copy and paste,
    potentially highlighting it or adding visual cues.

    Args:
        win: The curses window.
        y: The y-coordinate.
        x: The x-coordinate.
        text: The command string.
        attr: curses attributes (e.g., colors, bold).
    """

    try:
        if not win:
            return
        h, w = win.getmaxyx()
        if y >= h or y < 0 or x < 0 or x >= w:
            return
        available_width = w - x
        if available_width <= 0:
            return
        display_text = str(text)[:available_width]
        win.addstr(
            y, x, display_text, attr | curses.A_UNDERLINE
        )  # Example: Add underline
    except curses.error:
        pass
    except Exception:
        pass
