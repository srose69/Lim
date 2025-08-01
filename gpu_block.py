# gpu_block.py

import curses
import subprocess
import os
import glob
from utils import addstr_clipped, draw_box, draw_bar, format_bytes

GPU_TEMP_THRESHOLD_HIGH = 85
GPU_TEMP_THRESHOLD_MED = 70
GPU_UTIL_THRESHOLD_HIGH = 85
GPU_UTIL_THRESHOLD_MED = 60


def parse_nv_smi():
    gpus = []
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=index,name,utilization.gpu,temperature.gpu,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ]
        res = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=1.5
        )
        if res.returncode == 0 and res.stdout:
            for line in res.stdout.strip().splitlines():
                p = line.split(",")
                if len(p) == 6:
                    try:
                        gpus.append(
                            {
                                "id": int(p[0].strip()),
                                "name": p[1].strip(),
                                "vendor": "NVIDIA",
                                "util": float(p[2].strip()),
                                "temp": float(p[3].strip()),
                                "mem_used": float(p[4].strip()),
                                "mem_total": float(p[5].strip()),
                                "mem_perc": (
                                    float(p[4].strip()) / float(p[5].strip()) * 100
                                )
                                if float(p[5].strip()) > 0
                                else 0.0,
                                "source": "nvidia-smi",
                            }
                        )
                    except:
                        continue
    except:
        pass
    return gpus


def find_hwmon_temp_input(hwmon_path):
    try:
        tfs = glob.glob(os.path.join(hwmon_path, "temp*_input"))
        if not tfs:
            return None
        for tf in tfs:
            lf = tf.replace("_input", "_label")
            if os.path.exists(lf):
                try:
                    with open(lf, "r") as f:
                        lbl = f.read().strip().lower()
                    if "edge" in lbl or "junction" in lbl:
                        return tf
                except:
                    continue
        return tfs[0]
    except:
        return None


def parse_sys_info():
    gpus = []
    try:
        for cp in glob.glob("/sys/class/drm/card[0-9]*"):
            gi = {
                "source": "sysfs",
                "vendor": "?",
                "name": "GPU",
                "temp": None,
                "mem_used": None,
                "mem_total": None,
                "util": None,
                "mem_perc": None,
            }
            try:
                with open(os.path.join(cp, "device/vendor"), "r") as f:
                    vid = f.read().strip().lower()
                if vid == "0x10de":
                    gi["vendor"] = "NVIDIA"
                elif vid in ["0x1002", "0x1022"]:
                    gi["vendor"] = "AMD"
                elif vid == "0x8086":
                    gi["vendor"] = "Intel"
                else:
                    continue
                try:
                    with open(os.path.join(cp, "device/model"), "r") as f:
                        gi["name"] = f.read().strip()
                except:
                    gi["name"] = f"{gi['vendor']} GPU"
                hps = glob.glob(os.path.join(cp, "device/hwmon/hwmon*"))
                tf = None
                if hps:
                    tf = find_hwmon_temp_input(hps[0])
                if tf and os.path.exists(tf):
                    try:
                        with open(tf, "r") as f:
                            gi["temp"] = float(f.read().strip()) / 1000.0
                    except:
                        pass
                if gi["vendor"] == "AMD":
                    try:
                        mtp = os.path.join(cp, "device/mem_info_vram_total")
                        mup = os.path.join(cp, "device/mem_info_vram_used")
                        if os.path.exists(mtp) and os.path.exists(mup):
                            with open(mtp, "r") as ft, open(mup, "r") as fu:
                                mtb = float(ft.read().strip())
                                mub = float(fu.read().strip())
                                if mtb > 0:
                                    gi["mem_total"] = mtb / (1024 * 1024)
                                    gi["mem_used"] = mub / (1024 * 1024)
                                    gi["mem_perc"] = mub / mtb * 100.0
                    except:
                        pass
                gpus.append(gi)
            except:
                continue
    except:
        pass
    return gpus


def get_gpu_count():
    count = 0
    nv_gpus = []
    try:
        cmd = ["nvidia-smi", "-L"]
        res = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=0.5
        )
        if res.returncode == 0 and res.stdout:
            nv_gpus = res.stdout.strip().splitlines()
            count += len(nv_gpus)
    except:
        pass

    try:
        processed_vendors_in_sys = set()
        if nv_gpus:
            processed_vendors_in_sys.add("0x10de")

        for card_path in glob.glob("/sys/class/drm/card[0-9]*/device/vendor"):
            try:
                with open(card_path, "r") as f:
                    vendor_id = f.read().strip().lower()
                if vendor_id in ["0x1002", "0x1022", "0x8086"] or (
                    vendor_id == "0x10de" and vendor_id not in processed_vendors_in_sys
                ):
                    count += 1
                    processed_vendors_in_sys.add(vendor_id)
            except:
                continue
    except:
        pass
    return count


def draw_gpu_block_content(
    win, key_attr, value_attr, bar_colors, temp_colors, util_colors
):
    h, w = win.getmaxyx()
    draw_box(win, "GPU Info", key_attr)
    current_row = 1
    all_gpus = []
    error_msg = None

    try:
        nv_gpus = parse_nv_smi()
        all_gpus.extend(nv_gpus)
        nv_names = {gpu.get("name") for gpu in nv_gpus}
        sys_gpus = parse_sys_info()
        for gpu in sys_gpus:
            is_duplicate = False
            if gpu["vendor"] == "NVIDIA" and gpu["name"] in nv_names:
                is_duplicate = True
            if not is_duplicate:
                all_gpus.append(gpu)
    except Exception as e:
        error_msg = f"GPU Read Err: {str(e)[:w - 15]}"

    if error_msg:
        if current_row < h - 1:
            addstr_clipped(win, current_row, 1, error_msg, curses.color_pair(4))
    elif not all_gpus:
        if current_row < h - 1:
            addstr_clipped(
                win, current_row, 1, "No GPU Data Available", value_attr | curses.A_DIM
            )
    else:
        all_gpus.sort(
            key=lambda x: 0
            if x["vendor"] == "NVIDIA"
            else 1
            if x["vendor"] == "AMD"
            else 2
        )
        max_gpus_to_show = max(0, (h - 2) // 2)
        gpus_shown = 0
        for i, gpu in enumerate(all_gpus):
            if gpus_shown >= max_gpus_to_show or current_row >= h - 2:
                break
            gpu_name = gpu.get("name", "?")
            gpu_util = gpu.get("util")
            gpu_temp = gpu.get("temp")
            mem_used = gpu.get("mem_used")
            mem_total = gpu.get("mem_total")
            mem_perc = gpu.get("mem_perc")
            d_name = f"{i}:{gpu_name}"[: w - 16]
            t_str = "T:N/A"
            t_attr = value_attr | curses.A_DIM
            if gpu_temp is not None:
                t_str = f"T:{gpu_temp:.0f}\u00B0C"
                t_attr = value_attr
                if gpu_temp > GPU_TEMP_THRESHOLD_HIGH:
                    t_attr = curses.color_pair(temp_colors["high"]) | curses.A_BOLD
                elif gpu_temp > GPU_TEMP_THRESHOLD_MED:
                    t_attr = curses.color_pair(temp_colors["med"]) | curses.A_BOLD
                else:
                    t_attr = curses.color_pair(temp_colors["low"]) | curses.A_BOLD
            addstr_clipped(win, current_row, 1, d_name, key_attr)
            addstr_clipped(win, current_row, w - len(t_str) - 1, t_str, t_attr)
            current_row += 1

            u_lbl = "Ut:"
            u_str = "N/A ".ljust(6)
            u_bar_w = 0
            m_str = "Mem: N/A"
            m_attr = value_attr | curses.A_DIM
            m_len = len("Mem:XXXX/XXXXMB(XXX%)")
            if gpu_util is not None:
                u_str = f"{gpu_util:.0f}%".rjust(5) + " "
                u_bar_w = max(0, w - 2 - len(u_lbl) - 1 - len(u_str) - m_len - 2)
            if mem_perc is not None:
                m_str = f"Mem:{mem_used:.0f}/{mem_total:.0f}MB({mem_perc:.0f}%)"
                m_attr = value_attr
                if gpu_util is not None:
                    u_bar_w = max(
                        0, w - 2 - len(u_lbl) - 1 - len(u_str) - len(m_str) - 2
                    )
            addstr_clipped(win, current_row, 1, u_lbl, key_attr)
            u_attr = value_attr
            if gpu_util is not None:
                if gpu_util > GPU_UTIL_THRESHOLD_HIGH:
                    u_attr = curses.color_pair(util_colors["high"]) | curses.A_BOLD
                elif gpu_util > GPU_UTIL_THRESHOLD_MED:
                    u_attr = curses.color_pair(util_colors["med"]) | curses.A_BOLD
                else:
                    u_attr = curses.color_pair(util_colors["low"]) | curses.A_BOLD
                if u_bar_w > 0:
                    bx = 1 + len(u_lbl) + 1
                    draw_bar(
                        win, current_row, bx, u_bar_w, gpu_util, w, util_colors, False
                    )
                upx = 1 + len(u_lbl) + 1 + (u_bar_w + 2 if u_bar_w > 0 else 0)
                addstr_clipped(win, current_row, upx, u_str, u_attr)
            addstr_clipped(win, w - len(m_str) - 1, m_str, m_attr)
            current_row += 1
            gpus_shown += 1
