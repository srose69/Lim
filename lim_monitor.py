#!/usr/bin/env python3
# py_monitor_main.py
import curses
import time
import sys
import os
from math import ceil, floor
import signal
import subprocess
import json
import psutil
import datetime
import re   # Импорт re
import textwrap  # Для обтекания текста в help

# Импорты блоков (с проверками)
try:
    import cpu_block
except ImportError:
    cpu_block = None
try:
    import memory_block
except ImportError:
    memory_block = None
try:
    import gpu_block
except ImportError:
    gpu_block = None
try:
    import misc_block
except ImportError:
    misc_block = None
try:
    import process_block
except ImportError:
    process_block = None
    print("ERROR: process_block.py not found!", file=sys.stderr)
    sys.exit(1)
try:
    import utils
except ImportError:
    utils = None
    print("ERROR: utils.py not found!", file=sys.stderr)
    sys.exit(1)
try:
    import help_content
except ImportError:
    help_content = None
    print("ERROR: help_content.py not found!", file=sys.stderr)
    sys.exit(1)

# --- Основные настройки, Константы, init_gradient_colors ---
UPDATE_INTERVAL = 1.0
PROC_WIN_WIDTH_PERCENT = 0.60
MIN_TERM_ROWS = 26
MIN_TERM_COLS = 90
GRADIENT_COLOR_START_ID = 20
GRADIENT_COLOR_COUNT = 20
PROC_BORDER_ROW = 0
PROC_HEADER_ROW = 1
PROC_CONTENT_START_ROW = 2

def init_gradient_colors(start_pair_id, count):
    gradient_pairs = []
    default_fallback = ([8] * 10 + [9] * 5 + [10] * 5)
    if not curses.has_colors():
        return default_fallback
    try:
        can_change = curses.can_change_color()
        colors_available = curses.COLORS
        if can_change and colors_available >= 256 and count > 0:
            for i in range(count):
                color_id = start_pair_id + i
                pair_id = start_pair_id + i
                ratio = i / (count - 1) if count > 1 else 0.5
                if ratio <= 0.5:
                    r = int(2 * ratio * 1000)
                    g = 1000
                    b = 0
                else:
                    r = 1000
                    g = int((1.0 - (ratio - 0.5) * 2) * 1000)
                    b = 0
                r = max(0, min(1000, r))
                g = max(0, min(1000, g))
                b = max(0, min(1000, b))
                try:
                    curses.init_color(color_id, r, g, b)
                    curses.init_pair(pair_id, color_id, -1)
                    gradient_pairs.append(pair_id)
                except curses.error:
                    return default_fallback
            return gradient_pairs if len(gradient_pairs) == count else default_fallback
        else:
            return default_fallback
    except Exception:
        return default_fallback

# --- Функция отрисовки текстовой разметки ---
def addstr_colored_markup(win, y, x, text, default_attr, tag_map):
    """
    Рендерит строку с in-line разметкой тегов (например, <c1>…</c1>, <b5>…</b5>).
    Теги не выводятся на экран — они лишь изменяют атрибут.
    Любой закрывающий тег (начинающийся с "</") сбрасывает атрибут до default_attr.
    """
    import re
    if "<" not in text:
        try:
            win.addstr(y, x, text, default_attr)
        except curses.error:
            pass
        return

    # Ищем теги вида <tag> или </tag>
    pattern = r"(<\w+>|</\w+>)"
    pos = 0
    cur_attr = default_attr

    for m in re.finditer(pattern, text):
        start, end = m.span()
        # Вывод сегмента текста до тега
        if start > pos:
            segment = text[pos:start]
            try:
                win.addstr(y, x, segment, cur_attr)
            except curses.error:
                pass
            x += len(segment)
        tag = m.group()
        if tag.startswith("</"):
            cur_attr = default_attr  # Закрывающий тег: сброс
        elif tag in tag_map:
            cur_attr = tag_map[tag]
        pos = end

    if pos < len(text):
        segment = text[pos:]
        try:
            win.addstr(y, x, segment, cur_attr)
        except curses.error:
            pass

def addstr_clipped(win, y, x, text, attr=0):
    """Безопасно вставляет строку в окно, обрезая текст под ширину."""
    try:
        if not win:
            return
        h, w = win.getmaxyx()
        if y >= h or y < 0 or x < 0:
            return
        available_width = w - x
        if available_width <= 0:
            return
        safe_text = "".join(c if c.isprintable() else '?' for c in str(text))
        display_text = safe_text[:available_width]
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
    """Рисует рамку для окна с заголовком."""
    try:
        if not win:
            return
        win.erase()
        win.border()
        if title:
            h, w = win.getmaxyx()
            trimmed_title = title.strip()
            title_len = len(trimmed_title)
            title_x = max(1, min(w - title_len - 3, (w - (title_len + 2)) // 2))
            if title_x + title_len + 2 < w:
                addstr_clipped(win, 0, title_x, f" {trimmed_title} ", title_attr)
    except curses.error:
        pass
    except Exception:
        pass

def show_popup(stdscr, title, content_lines, border_color_pair=1, text_color_pair=5):
    """Отображает popup с текстом, рамкой и поддержкой разметки."""
    has_colors = curses.has_colors()
    if not has_colors:
        border_color_pair = 0
        text_color_pair = 0

    rows, cols = stdscr.getmaxyx()
    content_h = len(content_lines)
    popup_h = min(content_h + 3, rows - 2)
    popup_h = max(4, popup_h)
    max_content_width = 0
    if content_lines:
        try:
            plain_lines = [re.sub(r'</?\w+>', '', str(l)) for l in content_lines]
            drawable_content_lines = popup_h - 3
            max_content_width = max(len(l) for l in plain_lines[:max(0, drawable_content_lines)])
        except ValueError:
            pass
    popup_w = min(max(len(title) + 2, max_content_width) + 4, cols - 4)
    popup_w = max(25, popup_w)
    popup_y = max(0, (rows - popup_h) // 2)
    popup_x = max(0, (cols - popup_w) // 2)

    popup = None
    try:
        popup = curses.newwin(popup_h, popup_w, popup_y, popup_x)
        popup.keypad(True)
        popup.timeout(-1)
        title_attr = curses.color_pair(border_color_pair) | curses.A_BOLD if has_colors else curses.A_BOLD
        utils.draw_box(popup, title, title_attr=title_attr)
        default_attr = curses.color_pair(text_color_pair) if has_colors else 0
        if has_colors:
            tag_map = {
                '<c1>': curses.color_pair(1) | curses.A_BOLD,
                '<c2>': curses.color_pair(2) | curses.A_BOLD,
                '<c3>': curses.color_pair(3) | curses.A_BOLD,
                '<c4>': curses.color_pair(4) | curses.A_BOLD,
                '<b5>': curses.color_pair(5) | curses.A_BOLD
            }
        else:
            tag_map = {
                '<c1>': curses.A_BOLD,
                '<c2>': curses.A_BOLD,
                '<c3>': curses.A_BOLD,
                '<c4>': curses.A_REVERSE,
                '<b5>': curses.A_BOLD
            }
        content_start_y = 1
        content_max_y = popup_h - 3
        for i, line in enumerate(content_lines):
            line_y = content_start_y + i
            if line_y > content_max_y:
                break
            utils.addstr_colored_markup(popup, line_y, 1, line, default_attr, tag_map)
        exit_msg = "[Press q or Enter to close]"
        if popup_h > 2:
            exit_y = popup_h - 2
            exit_x = max(1, (popup_w - len(exit_msg)) // 2)
            if exit_y >= content_start_y:
                utils.addstr_clipped(popup, exit_y, exit_x, exit_msg, curses.A_DIM)
        popup.refresh()
        while True:
            key = popup.getch()
            if key in (ord('q'), ord('\n'), curses.KEY_ENTER, 27):
                break
            elif key == curses.KEY_RESIZE:
                break
    except curses.error:
        pass
    except Exception:
        pass
    finally:
        if popup:
            del popup
        if stdscr:
            stdscr.clear()
            stdscr.refresh()

def show_help_fullscreen(stdscr):
    """
    Отображает помощь на полный экран двумя столбцами:
      • левый столбец – информация для монитора (из HELP_MONITOR_TEXT),
      • правый столбец – информация для CLI и прочего (из HELP_CLI_TEXT).
    Подсказка: при нажатии клавиши «m» открывается дополнительное окно с подробностями CLI-команд.
    """
    import re
    has_colors = curses.has_colors()
    rows, cols = stdscr.getmaxyx()
    stdscr.clear()
    title = help_content.HELP_TITLE if hasattr(help_content, "HELP_TITLE") else "Help"
    title_attr = curses.color_pair(1) | curses.A_BOLD if has_colors else curses.A_BOLD
    utils.draw_box(stdscr, title, title_attr=title_attr)
    inner_y, inner_x = 1, 1
    inner_h, inner_w = rows - 2, cols - 2
    monitor_lines = help_content.HELP_MONITOR_TEXT if hasattr(help_content, "HELP_MONITOR_TEXT") else ["Нет информации для монитора."]
    cli_lines     = help_content.HELP_CLI_TEXT     if hasattr(help_content, "HELP_CLI_TEXT")     else ["Нет информации для CLI."]
    def wrap_markup(text, width):
        """
        Разбивает строку с разметкой (например, "<c2>Text</c2> ...")
        по заданной ширине, не разрывая теги.
        Теги не учитываются при подсчёте длины.
        """
        tokens = re.split(r'(<\s*/?\s*\w+\s*>)', text)
        lines = []
        current_line = ""
        current_length = 0
        for token in tokens:
            if not token:
                continue
            token_norm = token.strip()
            if re.fullmatch(r'</?\w+>', token_norm):
                current_line += token_norm
                continue
            words = token.split(" ")
            for word in words:
                if word == "":
                    current_line += " "
                    current_length += 1
                    continue
                add_space = 1 if current_line and not current_line.endswith(" ") else 0
                if current_length + add_space + len(word) > width:
                    if current_line:
                        lines.append(current_line)
                    current_line = ""
                    current_length = 0
                    add_space = 0
                if current_line:
                    current_line += " " + word
                    current_length += add_space + len(word)
                else:
                    current_line = word
                    current_length = len(word)
        if current_line:
            lines.append(current_line)
        return lines
    col_width = inner_w // 2 - 1
    wrapped_monitor = []
    for line in monitor_lines:
        wrapped_monitor.extend(wrap_markup(line, col_width))
    wrapped_cli = []
    for line in cli_lines:
        wrapped_cli.extend(wrap_markup(line, col_width))
    default_attr = curses.color_pair(5) if has_colors else 0
    if has_colors:
        tag_map = {
            '<c1>': curses.color_pair(1) | curses.A_BOLD,
            '<c2>': curses.color_pair(2) | curses.A_BOLD,
            '<c3>': curses.color_pair(3) | curses.A_BOLD,
            '<c4>': curses.color_pair(4) | curses.A_BOLD,
            '<b5>': curses.color_pair(5) | curses.A_BOLD,
        }
    else:
        tag_map = {
            '<c1>': curses.A_BOLD,
            '<c2>': curses.A_BOLD,
            '<c3>': curses.A_BOLD,
            '<c4>': curses.A_REVERSE,
            '<b5>': curses.A_BOLD,
        }
    for i in range(inner_h):
        if i < len(wrapped_monitor):
            try:
                utils.addstr_colored_markup(stdscr, inner_y + i, inner_x,
                                             wrapped_monitor[i].ljust(col_width)[:col_width],
                                             default_attr, tag_map)
            except curses.error:
                pass
        if i < len(wrapped_cli):
            try:
                utils.addstr_colored_markup(stdscr, inner_y + i, inner_x + col_width + 1,
                                             wrapped_cli[i].ljust(col_width)[:col_width],
                                             default_attr, tag_map)
            except curses.error:
                pass
    exit_msg = "[Press any key to return, m for CLI details]"
    try:
        stdscr.addstr(rows - 1, max((cols - len(exit_msg)) // 2, 0), exit_msg, curses.A_DIM)
    except curses.error:
        pass
    stdscr.refresh()
    stdscr.timeout(-1)
    key = stdscr.getch()
    if key in (ord('m'), ord('M')):
        show_cli_details(stdscr)
    stdscr.clear()
    stdscr.refresh()

def show_cli_details(stdscr):
    """
    Отображает подробное описание CLI-команд (текст из HELP_CLI_DETAILED).
    """
    has_colors = curses.has_colors()
    rows, cols = stdscr.getmaxyx()
    stdscr.clear()
    title = "CLI Commands Details"
    if hasattr(help_content, "HELP_CLI_DETAILED_TITLE"):
        title = help_content.HELP_CLI_DETAILED_TITLE
    title_attr = curses.color_pair(1) | curses.A_BOLD if has_colors else curses.A_BOLD
    utils.draw_box(stdscr, title, title_attr=title_attr)
    inner_y, inner_x = 1, 1
    inner_h, inner_w = rows - 2, cols - 2
    if hasattr(help_content, "HELP_CLI_DETAILED"):
        detailed_lines = help_content.HELP_CLI_DETAILED
    else:
        detailed_lines = ["Нет подробной информации для CLI."]
    wrapped_lines = []
    for line in detailed_lines:
        wrapped = textwrap.wrap(line, width=inner_w) or [""]
        wrapped_lines.extend(wrapped)
    y_offset = inner_y
    for line in wrapped_lines:
        if y_offset >= inner_y + inner_h:
            break
        try:
            stdscr.addstr(y_offset, inner_x, line[:inner_w])
        except curses.error:
            pass
        y_offset += 1
    exit_msg = "[Press any key to return]"
    try:
        stdscr.addstr(rows - 1, max((cols - len(exit_msg)) // 2, 0), exit_msg, curses.A_DIM)
    except curses.error:
        pass
    stdscr.refresh()
    stdscr.timeout(-1)
    stdscr.getch()
    stdscr.clear()
    stdscr.refresh()

def show_process_details(stdscr, pinfo):
    if not pinfo:
        return
    pid = pinfo.get('pid', 'N/A')
    name = pinfo.get('display_name', 'N/A')
    lines = []
    lines.append(f"PID       : {pid}")
    lines.append(f"Name      : {name}")
    lines.append(f"User      : {pinfo.get('username', 'N/A')}")
    lines.append(f"CPU %     : {pinfo.get('cpu_percent', 0.0):.1f}")
    lines.append(f"Memory %  : {pinfo.get('memory_percent', 0.0):.1f}")
    lines.append(f"RSS       : {pinfo.get('rss_mb', 0.0):.1f} MB")
    lines.append(f"VMS       : {pinfo.get('vms_mb', 0.0):.1f} MB")
    try:
        if isinstance(pid, int) and pid > 0:
            proc = psutil.Process(pid)
            lines.append(f"Status    : {proc.status()}")
            lines.append(f"Started   : {datetime.datetime.fromtimestamp(proc.create_time()).strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Threads   : {proc.num_threads()}")
            cmd = ' '.join(proc.cmdline() or [])
            lines.append(f"Cmdline   : {cmd[:120]}{'...' if len(cmd) > 120 else ''}")
            try:
                lines.append(f"Open Files: {len(proc.open_files())}")
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                lines.append("Open Files: N/A")
            try:
                lines.append(f"Connections: {len(proc.net_connections())}")
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                lines.append("Connections: N/A")
        else:
            lines.append("Cannot get details: Invalid PID")
    except psutil.NoSuchProcess:
        lines.append("Error: Process not found.")
    except psutil.AccessDenied:
        lines.append("Error: Access denied.")
    except Exception as e:
        lines.append(f"Error getting details: {type(e).__name__}")
    show_popup(stdscr, f"Process Details (PID: {pid})", lines, border_color_pair=1, text_color_pair=5)

def _show_docker_inspect(stdscr, pinfo):
    if not pinfo:
        return
    pid = pinfo.get('pid')
    container_id_short = pinfo.get('docker_info', None)
    if not container_id_short:
        show_popup(stdscr, "Container Info", ["Not a container process?"], 4)
        return
    lines = [f"Host PID: {pid}", f"Container: {container_id_short}"]
    inspect_output = None
    error_msg = None
    try:
        cmd = ["docker", "inspect", container_id_short]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
        if result.returncode == 0:
            inspect_output = result.stdout
        else:
            error_msg = f"Inspect Error:\n{result.stderr[:200]}"
    except FileNotFoundError:
        error_msg = "'docker' command not found."
    except subprocess.TimeoutExpired:
        error_msg = "'docker inspect' timed out."
    except Exception as e:
        error_msg = f"Error: {e}"
    lines.append("-" * 20)
    if inspect_output:
        try:
            data = json.loads(inspect_output)
            if isinstance(data, list):
                data = data[0]
            state = data.get('State', {})
            config = data.get('Config', {})
            network = data.get('NetworkSettings', {}).get('Networks', {})
            mounts = data.get('Mounts', [])
            lines.append(f"Full ID : {data.get('Id', '')[:12]}...")
            lines.append(f"Image   : {config.get('Image', 'N/A')}")
            lines.append(f"Status  : {state.get('Status', 'N/A')}")
            lines.append(f"Started : {state.get('StartedAt', 'N/A')}")
            lines.append(f"Command : {' '.join(config.get('Cmd', []))[:60]}...")
            net_info = [f"{n}={d.get('IPAddress')}" for n, d in network.items() if d.get('IPAddress')]
            lines.append(f"Network : {', '.join(net_info)}")
            lines.append(f"Mounts ({len(mounts)}):")
            for m in mounts[:3]:
                lines.append(f"  - {m.get('Source', '?')}->{m.get('Destination', '?')} ({'RW' if m.get('RW') else 'RO'})")
            if len(mounts) > 3:
                lines.append("    ...")
        except Exception as e:
            lines.append(f"Error parsing data: {e}")
    elif error_msg:
        lines.extend(error_msg.splitlines())
    show_popup(stdscr, f"Container Inspect ({container_id_short})", lines, border_color_pair=1, text_color_pair=5)

def handle_docker_action(stdscr, pinfo):
    if not pinfo:
        return 'cancelled'
    pid = pinfo.get('pid')
    container_id_short = pinfo.get('docker_info', None)
    if not container_id_short:
        show_popup(stdscr, "Docker Action", ["Not a container process?"], 4)
        return 'cancelled'
    has_colors = curses.has_colors()
    rows, cols = stdscr.getmaxyx()
    height = 6
    q_text = f"Action for '{container_id_short}' (Host PID: {pid})?"
    width = max(55, len(q_text) + 4)
    width = min(width, cols - 4)
    y = max(0, (rows - height) // 2)
    x = max(0, (cols - width) // 2)
    win = None
    result = 'cancelled'
    try:
        win = curses.newwin(height, width, y, x)
        text_color = curses.color_pair(18) if has_colors else 0
        border_color = curses.color_pair(1) | curses.A_BOLD if has_colors else curses.A_REVERSE
        utils.draw_box(win, title="", title_attr=border_color)
        utils.addstr_clipped(win, 1, 2, q_text[:width - 4], text_color | curses.A_BOLD)
        o_line1 = "[I]nspect  [R]estart"
        o_line2 = "[S]hell    [C]ancel"
        o_line1_x = max(1, (width - len(o_line1)) // 2)
        o_line2_x = max(1, (width - len(o_line2)) // 2)
        utils.addstr_clipped(win, 2, o_line1_x, o_line1, text_color)
        utils.addstr_clipped(win, 3, o_line2_x, o_line2, text_color)
        win.refresh()
        win.keypad(True)
        win.timeout(-1)
        action_result_lines = []
        while True:
            key = win.getch()
            action_performed = False
            close_dialog = False
            if key in (ord('c'), ord('C'), ord('q'), ord('Q'), 27):
                result = 'cancelled'
                close_dialog = True
            elif key == curses.KEY_RESIZE:
                result = 'cancelled'
                close_dialog = True
            elif key in (ord('i'), ord('I')):
                result = 'inspect'
                close_dialog = True
            elif key in (ord('r'), ord('R')):
                try:
                    cmd = ["docker", "restart", container_id_short]
                    run_res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
                    if run_res.returncode == 0:
                        action_result_lines = [f"Restart command sent."]
                    else:
                        action_result_lines = [f"Error restarting:", f"{run_res.stderr[:150]}"]
                except Exception as e:
                    action_result_lines = [f"Failed to run restart: {e}"]
                result = 'restarted'
                action_performed = True
                close_dialog = True
            elif key in (ord('s'), ord('S')):
                cmd_to_show = f"docker exec -it {container_id_short} /bin/bash"
                action_result_lines = ["To open a shell, run:", cmd_to_show]
                result = 'shell_info'
                action_performed = True
                close_dialog = False
            if action_result_lines:
                win.move(2, 1)
                win.clrtoeol()
                win.move(3, 1)
                win.clrtoeol()
                max_res_lines = height - 3
                for idx, line in enumerate(action_result_lines):
                    if idx >= max_res_lines:
                        break
                    utils.addstr_clipped(win, 2 + idx, 2, line, text_color)
                if result == 'shell_info':
                    exit_msg_shell = "[Press C/Q/Esc to Cancel]"
                    if height > 4 and len(exit_msg_shell) < width - 2:
                        utils.addstr_clipped(win, height - 2, max(1, (width - len(exit_msg_shell)) // 2), exit_msg_shell, curses.A_DIM)
                win.refresh()
                action_result_lines = []
                if result != 'shell_info':
                    time.sleep(1.5)
                    close_dialog = True
            if close_dialog:
                break
    except curses.error:
        pass
    except Exception as e:
        result = f'error_dialog: {e}'
    finally:
        if win:
            del win
        if result != 'inspect' and stdscr:
            stdscr.clear()
            stdscr.refresh()
        return result

def handle_kill_confirmation(stdscr, pinfo):
    if not pinfo:
        return 'cancelled'
    pid = pinfo.get('pid')
    name = pinfo.get('display_name', 'Unknown')
    if not pid:
        return 'cancelled'
    has_colors = curses.has_colors()
    rows, cols = stdscr.getmaxyx()
    height = 5
    q_text = f"How do you want to signal '{name}' ({pid})?"
    width = max(55, len(q_text) + 4)
    width = min(width, cols - 4)
    y = max(0, (rows - height) // 2)
    x = max(0, (cols - width) // 2)
    win = None
    result = 'cancelled'
    try:
        win = curses.newwin(height, width, y, x)
        text_color = curses.color_pair(18) if has_colors else 0
        border_color = curses.color_pair(19) | curses.A_BOLD if has_colors else curses.A_REVERSE
        utils.draw_box(win, title="", title_attr=border_color)
        utils.addstr_clipped(win, 1, 2, q_text[:width - 4], text_color | curses.A_BOLD)
        o_line = "[S]igTERM  [K]ill (-9)  [C]ancel "
        o_line_x = max(1, (width - len(o_line)) // 2)
        utils.addstr_clipped(win, 2, o_line_x, o_line, text_color)
        win.refresh()
        win.keypad(True)
        win.timeout(-1)
        while True:
            key = win.getch()
            signal_to_send = None
            result_status = 'cancelled'
            if key in (ord('c'), ord('C'), ord('q'), ord('Q'), 27):
                result_status = 'cancelled'
                break
            elif key in (ord('s'), ord('S')):
                signal_to_send = signal.SIGTERM
                result_status = 'killed_term'
            elif key in (ord('k'), ord('K')):
                signal_to_send = signal.SIGKILL
                result_status = 'killed_kill'
            elif key == curses.KEY_RESIZE:
                result_status = 'cancelled'
                break
            if signal_to_send is not None:
                try:
                    os.kill(pid, signal_to_send)
                    result = result_status
                except ProcessLookupError:
                    result = 'not_found'
                except PermissionError:
                    result = 'permission_denied'
                except Exception as e:
                    result = f'error: {e}'
                break
    except curses.error:
        pass
    except Exception as e:
        result = f'error_dialog: {e}'
    finally:
        if win:
            del win
        if stdscr:
            stdscr.clear()
            stdscr.refresh()
        return result

def main(stdscr):
    # --- Инициализация и цвета ---
    has_colors = False
    try:
        curses.start_color()
        curses.use_default_colors()
        if curses.has_colors():
            has_colors = True
    except:
        pass
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)
    curses.noecho()
    try:
        curses.mousemask(curses.BUTTON1_CLICKED | curses.REPORT_MOUSE_POSITION)
        curses.mouseinterval(100)
    except:
        pass
    if has_colors:
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_RED, -1)
        curses.init_pair(5, curses.COLOR_WHITE, -1)
        curses.init_pair(6, curses.COLOR_RED, -1)
        curses.init_pair(8, curses.COLOR_GREEN, -1)
        curses.init_pair(9, curses.COLOR_YELLOW, -1)
        curses.init_pair(10, curses.COLOR_RED, -1)
        curses.init_pair(11, curses.COLOR_MAGENTA, -1)
        curses.init_pair(12, curses.COLOR_RED, -1)
        curses.init_pair(13, curses.COLOR_GREEN, -1)
        curses.init_pair(14, curses.COLOR_YELLOW, -1)
        curses.init_pair(15, curses.COLOR_RED, -1)
        curses.init_pair(16, curses.COLOR_BLUE, -1)
        curses.init_pair(17, curses.COLOR_RED, -1)
        curses.init_pair(18, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(19, curses.COLOR_RED, curses.COLOR_BLACK)
        cpu_gradient_colors = init_gradient_colors(GRADIENT_COLOR_START_ID, GRADIENT_COLOR_COUNT)
    else:
        for i in range(1, 20):
            curses.init_pair(i, 0, 0)
        cpu_gradient_colors = [0] * GRADIENT_COLOR_COUNT
    key_attr = curses.A_BOLD | curses.color_pair(1)
    value_attr = curses.color_pair(5)
    cmd_attr = curses.color_pair(1)
    user_attrs = {'root': curses.A_BOLD | curses.color_pair(6), 'normal': curses.color_pair(5)}
    rss_color_map = {'high': 4, 'med': 3, 'low': 2, 'default': 2}
    bar_colors = {'high': 10, 'med': 9, 'low': 8}
    gpu_util_colors = {'high': 15, 'med': 14, 'low': 13}
    gpu_temp_colors = {'high': 15, 'med': 14, 'low': 13}
    cpu_high_attr = curses.A_BOLD | curses.color_pair(10)
    disk_high_attr = curses.A_BOLD | curses.color_pair(12)
    net_attr = curses.color_pair(11)
    load_colors = {'high': 10, 'med': 9, 'low': 8}
    docker_attr = value_attr
    docker_container_attr = key_attr | curses.A_BOLD
    killer_attr = curses.color_pair(4)
    current_sort_key = 'rss'
    possible_sort_keys = ['rss', 'cpu', 'mem', 'pid', 'vms', 'name']
    win_proc, win_cpu, win_mem, win_gpu, win_misc = None, None, None, None, None
    last_rows, last_cols = -1, -1
    current_mode = 'normal'
    selected_line_abs = 0
    scroll_offset = 0
    process_list_cache = []
    total_processes_in_list = 0
    is_selecting = False
    term_resized = True

    try:
        while True:
            loop_start_time = time.time()
            if term_resized:
                rows, cols = stdscr.getmaxyx()
                if rows < MIN_TERM_ROWS or cols < MIN_TERM_COLS:
                    stdscr.erase()
                    msg = f"Terminal too small! (>= {MIN_TERM_COLS}x{MIN_TERM_ROWS})"
                    err_attr = curses.color_pair(4) | curses.A_BOLD if has_colors else curses.A_REVERSE
                    try:
                        stdscr.addstr(0, 0, msg[:cols - 1], err_attr)
                    except curses.error:
                        pass
                    stdscr.refresh()
                    last_rows, last_cols = rows, cols
                    time.sleep(0.5)
                    term_resized = True
                    input_key = stdscr.getch()
                    if input_key == ord('q'):
                        raise StopIteration
                    continue
            try:
                gpu_count = gpu_block.get_gpu_count() if gpu_block else 0
            except:
                gpu_count = 0
            proc_w = int(cols * PROC_WIN_WIDTH_PERCENT)
            proc_h = rows
            proc_x = 0
            proc_y = 0
            right_col_x = proc_w
            right_col_w = cols - proc_w
            min_cpu_h = 4 + (cpu_block.H_GRAPH_HEIGHT if cpu_block else 4)
            min_mem_h = 10
            min_gpu_h = 3 if gpu_count == 0 else (2 + gpu_count * 2)
            min_misc_h = 10
            cpu_h_pct, mem_h_pct, gpu_h_pct = 0.28, 0.32, (0.10 if gpu_count > 0 else 0.03)
            misc_h_pct = max(0, 1.0 - cpu_h_pct - mem_h_pct - gpu_h_pct)
            cpu_h = max(min_cpu_h, ceil(rows * cpu_h_pct))
            mem_h = max(min_mem_h, ceil(rows * mem_h_pct))
            gpu_h = max(min_gpu_h, ceil(rows * gpu_h_pct))
            misc_h = max(min_misc_h, rows - cpu_h - mem_h - gpu_h)
            total_h = cpu_h + mem_h + gpu_h + misc_h
            if total_h != rows:
                misc_h += (rows - total_h)
            misc_h = max(min_misc_h, misc_h)
            if cpu_h + mem_h + gpu_h + misc_h > rows:
                misc_h = max(0, rows - (cpu_h + mem_h + gpu_h))
            cpu_y = 0
            mem_y = cpu_h
            gpu_y = mem_y + mem_h
            misc_y = gpu_y + gpu_h
            if term_resized:
                stdscr.clear()
                for win in [win_proc, win_cpu, win_mem, win_gpu, win_misc]:
                    if win:
                        del win
                win_proc, win_cpu, win_mem, win_gpu, win_misc = None, None, None, None, None
                def safe_newwin(h, w, y, x, name):
                    if h > 0 and w > 0 and y >= 0 and y + h <= rows and x >= 0 and x + w <= cols:
                        try:
                            return curses.newwin(h, w, y, x)
                        except curses.error:
                            return None
                    else:
                        return None
                win_proc = safe_newwin(proc_h, proc_w, proc_y, proc_x, "proc")
                win_cpu = safe_newwin(cpu_h, right_col_w, cpu_y, right_col_x, "cpu")
                win_mem = safe_newwin(mem_h, right_col_w, mem_y, right_col_x, "mem")
                win_gpu = safe_newwin(gpu_h, right_col_w, gpu_y, right_col_x, "gpu")
                win_misc = safe_newwin(misc_h, right_col_w, misc_y, right_col_x, "misc")
                last_rows, last_cols = rows, cols
                selected_line_abs = 0
                scroll_offset = 0
                is_selecting = False
                term_resized = False
                stdscr.refresh()
            visible_proc_height = win_proc.getmaxyx()[0] - (PROC_CONTENT_START_ROW + 1) if win_proc else 0
            visible_proc_height = max(0, visible_proc_height)
            if is_selecting or current_mode == 'killer':
                if not process_list_cache:
                    process_list_cache = process_block.get_processes(current_sort_key) if process_block else []
                    if current_mode == 'docker':
                        process_list_cache = [p for p in process_list_cache if p.get('docker_info')]
                    total_processes_in_list = len(process_list_cache)
                processes_to_use = process_list_cache
            else:
                process_list_cache = []
                processes_to_use = process_block.get_processes(current_sort_key) if process_block else []
                if current_mode == 'docker':
                    processes_to_use = [p for p in processes_to_use if p.get('docker_info')]
                total_processes_in_list = len(processes_to_use)
            selected_line_abs = max(0, min(total_processes_in_list - 1, selected_line_abs)) if total_processes_in_list > 0 else 0
            if selected_line_abs < scroll_offset:
                scroll_offset = selected_line_abs
            if selected_line_abs >= scroll_offset + visible_proc_height:
                scroll_offset = selected_line_abs - visible_proc_height + 1
            max_scroll = total_processes_in_list - visible_proc_height
            scroll_offset = max(0, min(scroll_offset, max_scroll)) if total_processes_in_list > visible_proc_height else 0
            selected_line_rel = selected_line_abs - scroll_offset
            processes_to_display = processes_to_use[scroll_offset: scroll_offset + visible_proc_height]
            if win_cpu and cpu_block:
                cpu_block.draw_cpu_block_content(win_cpu, key_attr, value_attr, cpu_gradient_colors, UPDATE_INTERVAL)
            if win_mem and memory_block:
                memory_block.draw_memory_block_content(win_mem, key_attr, value_attr, bar_colors)
            if win_gpu and gpu_block:
                gpu_block.draw_gpu_block_content(win_gpu, key_attr, value_attr, bar_colors, gpu_temp_colors, gpu_util_colors)
            if win_misc and misc_block:
                misc_block.draw_misc_block_content(win_misc, key_attr, value_attr, disk_high_attr, net_attr, load_colors)
            if win_proc and process_block:
                actual_procs_shown = process_block.draw_process_block_content(
                    win_proc, key_attr, value_attr, cmd_attr, user_attrs, rss_color_map, cpu_high_attr,
                    sort_key=current_sort_key, mode=current_mode, selected_line=selected_line_rel,
                    process_list=processes_to_display, docker_attr=docker_attr, docker_container_attr=docker_container_attr,
                    killer_attr=killer_attr, is_selecting=is_selecting
                )
            for win in [win_proc, win_cpu, win_mem, win_gpu, win_misc]:
                if win:
                    try:
                        win.noutrefresh()
                    except curses.error:
                        pass
            try:
                curses.doupdate()
            except curses.error:
                pass
            input_key = -1
            redraw_needed = False
            time_now = time.time()
            remaining_time = (loop_start_time + UPDATE_INTERVAL) - time_now
            timeout_ms = max(1, int(remaining_time * 1000)) if remaining_time > 0 else 1
            stdscr.timeout(timeout_ms)
            input_key = stdscr.getch()
            if input_key != -1:
                redraw_needed = True
                if input_key == ord('q'):
                    raise StopIteration
                elif input_key == ord('h'):
                    show_help_fullscreen(stdscr)
                    redraw_needed = True
                elif input_key == ord('d'):
                    current_mode = 'normal' if current_mode == 'docker' else 'docker'
                    selected_line_abs = 0
                    scroll_offset = 0
                    is_selecting = False
                    process_list_cache = []
                elif input_key == ord('k'):
                    if current_mode == 'killer':
                        current_mode = 'normal'
                        is_selecting = False
                    else:
                        current_mode = 'killer'
                        is_selecting = True
                    selected_line_abs = 0
                    scroll_offset = 0
                    process_list_cache = []
                elif input_key in [ord('m'), ord('c'), ord('p'), ord('r'), ord('v'), ord('n'), ord('\t'), curses.KEY_BTAB]:
                    prev_sort_key = current_sort_key
                    new_sort_key = current_sort_key
                    if input_key == ord('\t') or input_key == curses.KEY_BTAB:
                        shift = 1 if input_key == ord('\t') else -1
                        current_index = possible_sort_keys.index(current_sort_key)
                        new_index = (current_index + shift) % len(possible_sort_keys)
                        new_sort_key = possible_sort_keys[new_index]
                    elif input_key == ord('m'):
                        new_sort_key = 'mem'
                    elif input_key == ord('c'):
                        new_sort_key = 'cpu'
                    elif input_key == ord('p'):
                        new_sort_key = 'pid'
                    elif input_key == ord('r'):
                        new_sort_key = 'rss'
                    elif input_key == ord('v'):
                        new_sort_key = 'vms'
                    elif input_key == ord('n'):
                        new_sort_key = 'name'
                    if prev_sort_key != new_sort_key:
                        current_sort_key = new_sort_key
                        selected_line_abs = 0
                        scroll_offset = 0
                        process_list_cache = []
                        is_selecting = False
                elif input_key == curses.KEY_UP:
                    selected_line_abs = max(0, selected_line_abs - 1)
                    is_selecting = True
                elif input_key == curses.KEY_DOWN:
                    selected_line_abs = min(total_processes_in_list - 1, selected_line_abs + 1) if total_processes_in_list > 0 else 0
                    is_selecting = True
                elif input_key == curses.KEY_PPAGE:
                    selected_line_abs = max(0, selected_line_abs - visible_proc_height)
                    is_selecting = True
                elif input_key == curses.KEY_NPAGE:
                    selected_line_abs = min(total_processes_in_list - 1, selected_line_abs + visible_proc_height) if total_processes_in_list > 0 else 0
                    is_selecting = True
                elif input_key == curses.KEY_HOME:
                    selected_line_abs = 0
                    is_selecting = True
                elif input_key == curses.KEY_END:
                    selected_line_abs = total_processes_in_list - 1 if total_processes_in_list > 0 else 0
                    is_selecting = True
                elif input_key == curses.KEY_MOUSE:
                    try:
                        m_id, m_x, m_y, m_z, m_bstate = curses.getmouse()
                        if win_proc and (m_bstate & curses.BUTTON1_CLICKED):
                            w_y, w_x = win_proc.getbegyx()
                            w_h, w_w = win_proc.getmaxyx()
                            if w_y <= m_y < w_y + w_h and w_x <= m_x < w_x + w_w:
                                clicked_row = m_y - w_y - PROC_CONTENT_START_ROW
                                if 0 <= clicked_row < visible_proc_height:
                                    new_selected_line_abs = scroll_offset + clicked_row
                                    if 0 <= new_selected_line_abs < total_processes_in_list:
                                        if is_selecting and new_selected_line_abs == selected_line_abs:
                                            input_key = ord('\n')
                                            redraw_needed = False
                                        else:
                                            selected_line_abs = new_selected_line_abs
                                            is_selecting = True
                                            redraw_needed = True
                    except curses.error:
                        pass
                if input_key in (ord('\n'), curses.KEY_ENTER):
                    if is_selecting and process_list_cache and 0 <= selected_line_abs < len(process_list_cache):
                        selected_pinfo = process_list_cache[selected_line_abs]
                        action_taken = False
                        if current_mode == 'killer':
                            kill_result = handle_kill_confirmation(stdscr, selected_pinfo)
                            current_mode = 'normal'
                            is_selecting = False
                            action_taken = True
                        elif current_mode == 'docker':
                            docker_action_result = handle_docker_action(stdscr, selected_pinfo)
                            if docker_action_result == 'inspect':
                                _show_docker_inspect(stdscr, selected_pinfo)
                            if docker_action_result not in ['cancelled', 'shell_info']:
                                is_selecting = False
                            action_taken = True
                        else:
                            show_process_details(stdscr, selected_pinfo)
                            is_selecting = False
                            action_taken = True
                        if action_taken:
                            process_list_cache = []
                            selected_line_abs = 0
                            scroll_offset = 0
                            redraw_needed = True
                    else:
                        is_selecting = False
                        redraw_needed = True
                elif input_key == curses.KEY_RESIZE:
                    term_resized = True
                    is_selecting = False
                    process_list_cache = []
                    redraw_needed = False
                else:
                    redraw_needed = False
    except StopIteration:
        pass
    except KeyboardInterrupt:
        pass
    except Exception as e:
        try:
            if 'stdscr' in locals() and stdscr and not curses.isendwin():
                curses.nocbreak()
                stdscr.keypad(False)
                curses.echo()
                curses.mousemask(0)
                curses.endwin()
        except:
            pass
        print(f"\n--- UNEXPECTED ERROR ---", file=sys.stderr)
        import traceback
        traceback.print_exc()
        print(f"------------------------\nError: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if 'stdscr' in locals() and stdscr and not curses.isendwin():
            try:
                curses.nocbreak()
                stdscr.keypad(False)
                curses.echo()
                curses.mousemask(0)
                curses.endwin()
            except:
                pass

if __name__ == "__main__":
    original_stderr = sys.stderr
    log_file_path = "/tmp/py_monitor_errors.log"
    try:
        with open(log_file_path, "a") as log_file:
            log_file.write(f"\n--- Session started at {datetime.datetime.now().isoformat()} ---\n")
            sys.stderr = log_file
            if not utils or not process_block or not help_content:
                print("Error: Missing required files (utils.py, process_block.py or help_content.py).", file=original_stderr)
                sys.exit(1)
            try:
                import psutil
            except ImportError:
                print("Error: psutil not found. Install: `pip install psutil`", file=original_stderr)
                sys.exit(1)
            curses.wrapper(main)
    except curses.error as e:
        sys.stderr = original_stderr
        print(f"Curses initialization error: {e}", file=sys.stderr)
        print(f"Term size? (>= {MIN_TERM_COLS}x{MIN_TERM_ROWS}) Colors?", file=sys.stderr)
        print(f"(Check {log_file_path} for errors)", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        sys.stderr = original_stderr
        print(f"\n--- UNEXPECTED ERROR during startup ---", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(f"------------------------\nError: {e}", file=sys.stderr)
        print(f"(Check {log_file_path} for errors)", file=sys.stderr)
        sys.exit(1)
    finally:
        sys.stderr = original_stderr