# cpu_block.py

import curses
import psutil
import time
from collections import deque
from math import floor, ceil
from utils import addstr_clipped, draw_box, draw_bar, format_bytes

H_GRAPH_HEIGHT = 6
CPU_HISTORY_LEN = 60
GRAPH_CHARS = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
SEGMENTS_PER_CHAR_CELL = 15


cpu_percent_history = deque(maxlen=CPU_HISTORY_LEN)
previous_cpu_times = None


def calculate_cpu_percent(current_times, previous_times):
    if previous_cpu_times is None:
        return 0.0, {"user": 0.0, "system": 0.0, "idle": 100.0, "iowait": 0.0}
    delta_user = current_times.user - previous_times.user
    delta_system = current_times.system - previous_times.system
    delta_idle = current_times.idle - previous_times.idle
    delta_nice = getattr(current_times, "nice", 0.0) - getattr(
        previous_times, "nice", 0.0
    )
    delta_iowait = getattr(current_times, "iowait", 0.0) - getattr(
        previous_times, "iowait", 0.0
    )
    delta_irq = getattr(current_times, "irq", 0.0) - getattr(previous_times, "irq", 0.0)
    delta_softirq = getattr(current_times, "softirq", 0.0) - getattr(
        previous_times, "softirq", 0.0
    )
    delta_steal = getattr(current_times, "steal", 0.0) - getattr(
        previous_times, "steal", 0.0
    )
    delta_guest = getattr(current_times, "guest", 0.0) - getattr(
        previous_cpu_times, "guest", 0.0
    )
    delta_guest_nice = getattr(current_times, "guest_nice", 0.0) - getattr(
        previous_cpu_times, "guest_nice", 0.0
    )
    total_delta = (
        delta_user
        + delta_system
        + delta_idle
        + delta_nice
        + delta_iowait
        + delta_irq
        + delta_softirq
        + delta_steal
        + delta_guest
        + delta_guest_nice
    )
    total_delta = max(0.0, total_delta)
    delta_idle = max(0.0, delta_idle)
    delta_user = max(0.0, delta_user)
    delta_system = max(0.0, delta_system)
    delta_iowait = max(0.0, delta_iowait)
    if total_delta <= 1e-6:
        return 0.0, {"user": 0.0, "system": 0.0, "idle": 100.0, "iowait": 0.0}
    idle_percent = max(0.0, min(100.0, (delta_idle / total_delta) * 100.0))
    total_load_percent = max(0.0, min(100.0, 100.0 - idle_percent))
    user_p = max(0.0, min(100.0, (delta_user / total_delta) * 100.0))
    system_p = max(0.0, min(100.0, (delta_system / total_delta) * 100.0))
    iowait_p = max(0.0, min(100.0, (delta_iowait / total_delta) * 100.0))
    calculated_times = {
        "user": user_p,
        "system": system_p,
        "idle": idle_percent,
        "iowait": iowait_p,
    }
    return total_load_percent, calculated_times


def draw_cpu_block_content(win, key_attr, value_attr, gradient_colors, update_interval):
    global previous_cpu_times, cpu_percent_history
    h, w = win.getmaxyx()
    draw_box(win, "CPU", key_attr)
    current_row = 1
    bg_attr = curses.color_pair(5) | curses.A_DIM
    bg_char = "."
    num_gradient_steps = len(gradient_colors)

    try:
        current_times = psutil.cpu_times()
        cpu_total, cpu_times_dict = calculate_cpu_percent(
            current_times, previous_cpu_times
        )
        previous_cpu_times = current_times
        cpu_percent_history.append(cpu_total)
        cpu_total_str = f"{cpu_total:.1f}%".rjust(6)
        load_label = "Load:"
        cores_str = "N/A"
        freq_str = "N/A"
        try:
            l = psutil.cpu_count(logical=True)
            p = psutil.cpu_count(logical=False)
            cores_str = f"{l}" + (f"({p}p)" if p and l != p else "")
        except:
            pass
        try:
            f = psutil.cpu_freq()
            if f and f.current:
                c = int(f.current)
                freq_str = f"{c}MHz" if c < 1500 else f"{c / 1000.0:.2f}GHz"
        except:
            pass
        info_line = (
            f"{load_label} {cpu_total_str}  Cores: {cores_str}  Freq: {freq_str}"
        )
        if current_row < h - 1:
            addstr_clipped(win, current_row, 1, info_line[: w - 2], value_attr)
            addstr_clipped(
                win,
                current_row,
                1 + len(load_label) + 1,
                cpu_total_str,
                value_attr | curses.A_BOLD,
            )
            current_row += 1
        else:
            return

        graph_start_row = current_row
        graph_height = H_GRAPH_HEIGHT
        graph_width = max(1, w - 2)
        if len(cpu_percent_history) > graph_width:
            t = list(cpu_percent_history)
            cpu_percent_history.clear()
            cpu_percent_history.extend(t[-graph_width:])
        if cpu_percent_history.maxlen != graph_width:
            cpu_percent_history = deque(cpu_percent_history, maxlen=graph_width)

        if graph_start_row + graph_height < h - 2:
            total_segments_possible = graph_height * SEGMENTS_PER_CHAR_CELL
            low_percent_threshold_dot = (
                100.0 / total_segments_possible if total_segments_possible > 0 else 1.0
            )

            for r in range(graph_height):
                addstr_clipped(
                    win, graph_start_row + r, 1, bg_char * graph_width, bg_attr
                )
            history_list = list(cpu_percent_history)
            num_chars = len(GRAPH_CHARS)
            segments_per_char = num_chars - 1

            for col_idx, percent in enumerate(history_list):
                graph_x = 1 + col_idx
                if percent <= 0:
                    continue
                filled_segments_total = ceil(total_segments_possible * percent / 100.0)
                filled_segments_total = min(
                    total_segments_possible, max(0, filled_segments_total)
                )

                if 0 < percent < low_percent_threshold_dot * 1.5:
                    graph_y = graph_start_row + graph_height - 1
                    dot_attr = curses.color_pair(gradient_colors[0])
                    addstr_clipped(win, graph_y, graph_x, ".", dot_attr)
                elif filled_segments_total >= 1:
                    if filled_segments_total == 0:
                        filled_segments_total = 1
                    for row_idx in range(graph_height):
                        graph_y = graph_start_row + graph_height - 1 - row_idx
                        segments_for_full_rows_below = row_idx * SEGMENTS_PER_CHAR_CELL
                        segments_remaining = (
                            filled_segments_total - segments_for_full_rows_below
                        )
                        if segments_remaining <= 0:
                            continue
                        segments_this_cell = min(
                            segments_remaining, SEGMENTS_PER_CHAR_CELL
                        )
                        if segments_this_cell <= 0:
                            continue
                        base_char_index = min(7, floor((segments_this_cell - 1) / 2))
                        use_underline = segments_this_cell % 2 != 0
                        graph_char = GRAPH_CHARS[base_char_index]
                        current_segment_level = (
                            segments_for_full_rows_below + segments_this_cell
                        )
                        segment_percent = min(
                            100.0,
                            (current_segment_level / total_segments_possible) * 100.0,
                        )
                        gradient_index = min(
                            num_gradient_steps - 1,
                            max(
                                0, floor(segment_percent / (100.0 / num_gradient_steps))
                            ),
                        )
                        color_pair_id = gradient_colors[gradient_index]
                        segment_fill_attr = curses.color_pair(color_pair_id)
                        if use_underline:
                            segment_fill_attr |= curses.A_UNDERLINE
                        addstr_clipped(
                            win, graph_y, graph_x, graph_char, segment_fill_attr
                        )
            current_row += graph_height
        else:
            current_row = h - 2

        if current_row < h - 1:
            addstr_clipped(win, current_row, 1, "Per Core:", key_attr)
            current_row += 1
            per_core_error = None
            try:
                simple_bar_colors = {"high": 10, "med": 9, "low": 8}
                cpu_percents = psutil.cpu_percent(interval=0.1, percpu=True)
                if cpu_percents:
                    num_cores = len(cpu_percents)
                    core_bar_width = 5
                    core_info_width = 3 + core_bar_width + 9
                    cores_per_line = max(1, (w - 2) // core_info_width)
                    start_y_cores = current_row
                    max_core_lines = h - start_y_cores - 1
                    cores_to_show = min(num_cores, cores_per_line * max_core_lines)
                    for i in range(cores_to_show):
                        perc = cpu_percents[i]
                        if perc is None:
                            perc = 0.0
                        li = i // cores_per_line
                        ci = i % cores_per_line
                        cy = start_y_cores + li
                        cx = 1 + ci * core_info_width
                        cl = f"{i}:"
                        addstr_clipped(win, cy, cx, cl, key_attr)
                        draw_bar(
                            win,
                            cy,
                            cx + len(cl) + 1,
                            core_bar_width,
                            perc,
                            w,
                            simple_bar_colors,
                            show_percent=False,
                        )
                        ps = f"{perc:.1f}%".rjust(6)
                        pa = value_attr
                        cpu_med_threshold = 60.0
                        cpu_high_threshold = 80.0
                        if perc > cpu_high_threshold:
                            pa = (
                                curses.color_pair(simple_bar_colors["high"])
                                | curses.A_BOLD
                            )
                        elif perc > cpu_med_threshold:
                            pa = (
                                curses.color_pair(simple_bar_colors["med"])
                                | curses.A_BOLD
                            )
                        addstr_clipped(
                            win, cy, cx + len(cl) + 1 + core_bar_width + 2, ps, pa
                        )
                else:
                    per_core_error = "Per Core data N/A"
            except Exception as e_core:
                per_core_error = f"Per Core Err: {str(e_core)[:w - 20]}"

            if per_core_error and current_row < h - 1:
                addstr_clipped(
                    win, current_row, 1, per_core_error, curses.color_pair(4)
                )

    except curses.error:
        pass
    except Exception as e:
        error_y = h - 2
        if error_y > 0:
            addstr_clipped(
                win,
                error_y,
                1,
                f"CPU Draw Err: {str(e)[:w - 15]}",
                curses.color_pair(4),
            )
