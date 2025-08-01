# misc_block.py

import curses
import psutil
import platform
import socket
import time
import datetime
import os
from math import ceil
from utils import (
    addstr_clipped,
    draw_box,
    format_bytes,
    format_uptime,
    print_clickable_command,
)

DISK_THRESHOLD_HIGH = 90.0
LOAD_AVG_THRESHOLDS = {"high": 5.0, "med": 2.0}


def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 53))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            for snics in psutil.net_if_addrs().values():
                for snic in snics:
                    if snic.family == socket.AF_INET and not snic.address.startswith(
                        "127."
                    ):
                        return snic.address
        except Exception:
            return "N/A"
    return "N/A"


def get_cpu_model():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    proc = platform.processor()
    return proc if proc else "N/A"


def draw_misc_block_content(
    win, key_attr, value_attr, disk_high_attr, net_attr, load_colors
):
    h, w = win.getmaxyx()
    draw_box(win, "System Info", key_attr)
    current_row = 1
    col1_x = 1
    col2_x = max(col1_x + 25, (w // 2))
    col1_width = col2_x - col1_x - 1
    col2_width = w - col2_x - 1
    items_in_row = 0

    def add_misc_line(label, value_str, value_attr_override=None):
        nonlocal current_row, items_in_row
        if current_row >= h - 1:
            return False
        is_col1 = items_in_row == 0
        target_x = col1_x if is_col1 else col2_x
        label_len = len(label) + 1
        available_value_width = max(
            1, (col1_width if is_col1 else col2_width) - label_len - 1
        )
        line = f"{label}:"
        attr = value_attr_override if value_attr_override is not None else value_attr
        addstr_clipped(win, current_row, target_x, line, key_attr)
        addstr_clipped(
            win,
            current_row,
            target_x + label_len + 1,
            value_str[:available_value_width],
            attr,
        )
        items_in_row += 1
        if items_in_row == 2:
            current_row += 1
            items_in_row = 0
        return True

    try:
        hostname = platform.node()
        os_info = f"{platform.system()} {platform.release()}"
        cpu_model = get_cpu_model()
        ip_addr = get_ip_address()
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        uptime_seconds = time.time() - psutil.boot_time()
        uptime_str = format_uptime(uptime_seconds)
        load_avg = psutil.getloadavg()
        load_str = f"{load_avg[0]:.2f} {load_avg[1]:.2f} {load_avg[2]:.2f}"
        users_list = []
        user_str = "N/A"
        try:
            users_list = psutil.users()
            user_str = ", ".join(sorted([u.name for u in users_list]))
        except Exception:
            pass
        num_cores = psutil.cpu_count() or 1
        load_1min_per_core = load_avg[0] / num_cores
        load_attr = curses.color_pair(load_colors["low"]) | curses.A_BOLD
        if load_1min_per_core > LOAD_AVG_THRESHOLDS["high"]:
            load_attr = curses.color_pair(load_colors["high"]) | curses.A_BOLD
        elif load_1min_per_core > LOAD_AVG_THRESHOLDS["med"]:
            load_attr = curses.color_pair(load_colors["med"]) | curses.A_BOLD

        if not add_misc_line("Hostname", hostname, value_attr | curses.A_BOLD):
            return
        if not add_misc_line("Time", now_str):
            return
        if not add_misc_line("OS", os_info):
            return
        if not add_misc_line("IP Address", ip_addr):
            return
        if current_row < h - 1:
            addstr_clipped(win, current_row, 1, f"{'CPU Model:':<10}", key_attr)
            addstr_clipped(win, current_row, 1 + 10, cpu_model[: w - 12], value_attr)
            current_row += 1
            items_in_row = 0
        else:
            return
        if not add_misc_line("Uptime", uptime_str):
            return
        if not add_misc_line("Load Avg", load_str, load_attr):
            return
        if items_in_row == 0 and current_row < h - 1:
            addstr_clipped(win, current_row, 1, f"{'Users:':<10}", key_attr)
            addstr_clipped(win, current_row, 1 + 10, user_str[: w - 12], value_attr)
            current_row += 1
        elif items_in_row == 1:
            pass
        elif current_row < h - 1:
            addstr_clipped(win, current_row, 1, "Users: N/A", value_attr | curses.A_DIM)
            current_row += 1
    except Exception as e:
        if current_row < h - 1:
            addstr_clipped(
                win,
                current_row,
                1,
                f"Sys Info Err: {str(e)[:w - 4]}",
                curses.color_pair(4),
            )
            current_row += 1

    try:
        if current_row < h - 3:
            current_row += 1
        if current_row < h - 2:
            addstr_clipped(win, current_row, 1, "Disk Usage:", key_attr)
            current_row += 1
            disk_info_str = " N/A"
            disk_info_attr = value_attr | curses.A_DIM
            try:
                partitions = psutil.disk_partitions(all=False)
                root_part = next((p for p in partitions if p.mountpoint == "/"), None)
                part_to_show = root_part
                if not part_to_show:
                    relevant = [
                        p
                        for p in partitions
                        if p.fstype
                        and not p.mountpoint.startswith(
                            ("/boot", "/snap", "/var/lib/docker")
                        )
                        and "loop" not in p.device
                    ]
                    if relevant:
                        part_to_show = relevant[0]
                if part_to_show:
                    p = part_to_show
                    usage = psutil.disk_usage(p.mountpoint)
                    used_h = format_bytes(usage.used)
                    total_h = format_bytes(usage.total)
                    perc = usage.percent
                    perc_attr = (
                        curses.color_pair(4) | curses.A_BOLD
                        if perc > DISK_THRESHOLD_HIGH
                        else value_attr
                    )
                    device = f"({os.path.basename(p.device) if p.device else p.fstype})"
                    disk_info_str = f" {p.mountpoint:<4} {device:<8} {used_h:>7}/{total_h:<7} ({perc:.1f}%)"
                    disk_info_attr = perc_attr
            except Exception as e:
                disk_info_str = f" Disk Read Err: {str(e)[:w - 16]}"
                disk_info_attr = curses.color_pair(4)
            addstr_clipped(win, current_row, 1, disk_info_str[: w - 2], disk_info_attr)
            current_row += 1
        if current_row < h - 1:
            addstr_clipped(win, current_row, 1, "Network I/O:", key_attr)
            current_row += 1
            net_info_str = " N/A"
            net_info_attr = value_attr | curses.A_DIM
            try:
                net_io = psutil.net_io_counters()
                if net_io:
                    sent = format_bytes(net_io.bytes_sent)
                    recv = format_bytes(net_io.bytes_recv)
                    if w > 60:
                        line1 = f" Total Sent: {sent}"
                        line2 = f" Total Recv: {recv}"
                        addstr_clipped(
                            win, current_row, col1_x, line1[:col1_width], net_attr
                        )
                        addstr_clipped(
                            win, current_row, col2_x, line2[:col2_width], net_attr
                        )
                    else:
                        net_info_str = f" S:{sent} R:{recv}"
                        addstr_clipped(
                            win, current_row, 1, net_info_str[: w - 2], net_attr
                        )
                    current_row += 1
                else:
                    addstr_clipped(win, current_row, 1, net_info_str, net_info_attr)
                    current_row += 1
            except Exception as e:
                if current_row < h - 1:
                    addstr_clipped(
                        win,
                        current_row,
                        1,
                        f" Net Err: {str(e)[:w - 10]}",
                        curses.color_pair(4),
                    )
                    current_row += 1
    except curses.error:
        pass
    except Exception as e:
        error_y = h - 2
        if error_y > 0:
            addstr_clipped(
                win, error_y, 1, f"Misc Err: {str(e)[:w - 10]}", curses.color_pair(4)
            )
