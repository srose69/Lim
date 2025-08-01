#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import curses
import curses.textpad
import json
import os
import sys
from pathlib import Path

# --- Constants ---
CONFIG_DIR = Path.home() / ".config/lim"
JSON_CACHE_FILE = CONFIG_DIR / "docker_cache.json"
BOOKMARKS_FILE = CONFIG_DIR / "bookmarks.json"
GO_SCRIPT_NAME = 'l.sh'
RETURN_SCRIPT_NAME = 'b.sh'

# --- Data Loading ---

def load_docker_cache():
    """Loads Docker containers from the cache."""
    if not JSON_CACHE_FILE.is_file(): return []
    try:
        with JSON_CACHE_FILE.open('r', encoding='utf-8') as f:
            data = json.load(f)
        return list(data.get('containers', {}).values())
    except (json.JSONDecodeError, OSError):
        return []

def load_bookmarks():
    """Loads directory bookmarks from their file."""
    if not BOOKMARKS_FILE.is_file(): return {}
    try:
        with BOOKMARKS_FILE.open('r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def save_bookmarks(bookmarks):
    """Saves bookmarks to their file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with BOOKMARKS_FILE.open('w', encoding='utf-8') as f:
        json.dump(bookmarks, f, indent=4)

# --- Core TUI Logic ---

class TuiApp:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.init_curses()
        self.current_row_idx = 0
        self.scroll_offset = 0
        self.status_message = ""
        self.status_type = "info"
        self.combined_list = []

    def init_curses(self):
        """Initialize curses settings and colors."""
        curses.curs_set(0)
        self.stdscr.keypad(True)
        curses.set_escdelay(25)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_RED, -1)
            curses.init_pair(5, curses.COLOR_WHITE, -1)
            curses.init_pair(6, curses.COLOR_MAGENTA, -1) # For bookmarks
            curses.init_pair(7, curses.A_REVERSE, -1) # Selection
    
    def get_style(self, pair_index, bold=False):
        """Get curses style attribute."""
        style = curses.color_pair(pair_index) if curses.has_colors() else 0
        if bold: style |= curses.A_BOLD
        return style

    def safe_addstr(self, win, y, x, text, attr=0):
        """Safely add a string to a curses window."""
        try:
            h, w = win.getmaxyx()
            if y >= 0 and y < h and x >= 0:
                available_width = w - x
                if available_width > 0:
                    win.addstr(y, x, text[:available_width], attr)
        except curses.error:
            pass

    def draw_window_layout(self):
        """Draw the main window layout and return content sub-windows."""
        h, w = self.stdscr.getmaxyx()
        self.stdscr.erase()
        
        title_text = "--- Limbo Navigator (Docker & Bookmarks) ---"
        self.safe_addstr(self.stdscr, 0, (w - len(title_text)) // 2, title_text, self.get_style(3, bold=True))

        list_h, status_h, instruct_h = h - 5, 3, 1
        
        # List Window
        list_win_border = curses.newwin(list_h, w, 1, 0)
        list_win_border.border()
        self.safe_addstr(list_win_border, 0, 2, " Items ", self.get_style(1, bold=True))
        list_win = list_win_border.derwin(list_h - 2, w - 2, 1, 1)

        # Status Window
        status_win_border = curses.newwin(status_h, w, 1 + list_h, 0)
        status_win_border.border()
        self.safe_addstr(status_win_border, 0, 2, " Status ", self.get_style(1, bold=True))
        status_win = status_win_border.derwin(status_h - 2, w - 2, 1, 1)

        # Instructions Window
        instruct_win = curses.newwin(instruct_h, w, h - 1, 0)

        self.stdscr.noutrefresh()
        list_win_border.noutrefresh()
        status_win_border.noutrefresh()

        return list_win, status_win, instruct_win

    def update_data(self):
        """Load and merge Docker and bookmark data."""
        self.combined_list = []
        
        # Add bookmarks
        bookmarks = load_bookmarks()
        for name, path in sorted(bookmarks.items()):
            self.combined_list.append({
                'type': 'bookmark', 'name': name, 'path': path, 'status': 'Bookmark'
            })

        # Add Docker containers
        containers = load_docker_cache()
        for c in sorted(containers, key=lambda i: i.get('name', '')):
            self.combined_list.append({
                'type': 'docker', 'name': c.get('name', 'N/A'), 'path': c.get('compose_path', 'N/A'),
                'status': c.get('status', 'N/A'), 'id': c.get('id', 'N/A')
            })
    
    def draw_list(self, win):
        """Draw the combined list of items."""
        win.erase()
        h, w = win.getmaxyx()
        
        type_w, name_w, status_w = 10, w // 3, 15
        
        for i in range(h):
            idx = self.scroll_offset + i
            if idx >= len(self.combined_list): break
            
            item = self.combined_list[idx]
            is_selected = (idx == self.current_row_idx)
            
            # Styles based on type and selection
            if item['type'] == 'docker':
                style = self.get_style(2) # Green for docker
            else: # bookmark
                style = self.get_style(6) # Magenta for bookmark
            
            if is_selected: style = self.get_style(7)
            
            path_style = style
            if not item.get('path') or item.get('path') == 'N/A':
                path_style = style | curses.A_DIM
            
            line_parts = [
                f" {item['type']:<{type_w}}",
                f" {item['name']:<{name_w}}",
                f" {item['status']:<{status_w}}",
                f" {item.get('path', 'N/A')}"
            ]
            self.safe_addstr(win, i, 0, "".join(line_parts), style)

    def draw_status(self, win):
        """Draw the status message."""
        win.erase()
        color = 3 if self.status_type == 'info' else 4
        self.safe_addstr(win, 0, 0, self.status_message, self.get_style(color, bold=True))

    def draw_instructions(self, win):
        """Draw the keybinding instructions."""
        win.erase()
        h, w = win.getmaxyx()
        instruct = "↑/↓: Nav | g/Enter: Go | i: Inspect | a: Add Bookmark | d: Del Bookmark | q: Quit"
        self.safe_addstr(win, 0, 0, instruct.ljust(w), self.get_style(7))
    
    def get_input_from_popup(self, prompt):
        """Display a popup to get text input from the user."""
        h, w = self.stdscr.getmaxyx()
        popup_h, popup_w = 3, w // 2
        popup_y, popup_x = (h - popup_h) // 2, (w - popup_w) // 2
        
        popup_border = curses.newwin(popup_h, popup_w, popup_y, popup_x)
        popup_border.border()
        self.safe_addstr(popup_border, 0, 2, f" {prompt} ", self.get_style(3, bold=True))
        popup_border.refresh()
        
        curses.echo()
        curses.curs_set(1)
        
        edit_win = popup_border.derwin(1, popup_w - 2, 1, 1)
        edit_win.keypad(True)
        
        box = curses.textpad.Textbox(edit_win)
        box.edit()
        
        curses.noecho()
        curses.curs_set(0)
        
        return box.gather().strip()

    def handle_add_bookmark(self):
        """Handle the UI flow for adding a new bookmark."""
        name = self.get_input_from_popup("Enter Bookmark Name")
        if not name:
            self.set_status("Add bookmark cancelled.", "warn")
            return
            
        path = self.get_input_from_popup(f"Enter Path (for '{name}')")
        if not path:
            path = os.getcwd() # Default to current dir

        bookmarks = load_bookmarks()
        bookmarks[name] = str(Path(path).resolve())
        save_bookmarks(bookmarks)
        self.set_status(f"Bookmark '{name}' added.", "info")
        self.update_data()
        
    def handle_delete_bookmark(self):
        """Handle deleting the selected bookmark."""
        if self.current_row_idx < len(self.combined_list):
            item = self.combined_list[self.current_row_idx]
            if item['type'] != 'bookmark':
                self.set_status("Cannot delete a Docker entry.", "warn")
                return

            name_to_del = item['name']
            bookmarks = load_bookmarks()
            if name_to_del in bookmarks:
                del bookmarks[name_to_del]
                save_bookmarks(bookmarks)
                self.set_status(f"Bookmark '{name_to_del}' deleted.", "info")
                self.update_data()
                self.current_row_idx = max(0, self.current_row_idx - 1)
            else:
                self.set_status(f"Bookmark '{name_to_del}' not found.", "warn")
        
    def set_status(self, msg, type="info"):
        self.status_message = msg
        self.status_type = type

    def run(self):
        """Main application loop."""
        self.update_data()
        
        while True:
            list_win, status_win, instruct_win = self.draw_window_layout()
            
            # Adjust scrolling and selection
            list_h = list_win.getmaxyx()[0]
            if self.current_row_idx < self.scroll_offset:
                self.scroll_offset = self.current_row_idx
            if self.current_row_idx >= self.scroll_offset + list_h:
                self.scroll_offset = self.current_row_idx - list_h + 1
            
            self.draw_list(list_win)
            self.draw_status(status_win)
            self.draw_instructions(instruct_win)
            
            curses.doupdate()
            
            key = self.stdscr.getch()
            self.set_status("") # Clear status on new keypress
            
            num_items = len(self.combined_list)
            
            if key in (ord('q'), 27): # q or Esc
                break
            elif key == curses.KEY_UP:
                if num_items > 0: self.current_row_idx = (self.current_row_idx - 1 + num_items) % num_items
            elif key == curses.KEY_DOWN:
                if num_items > 0: self.current_row_idx = (self.current_row_idx + 1) % num_items
            elif key == curses.KEY_RESIZE:
                continue
            elif key in (ord('g'), curses.KEY_ENTER, 10, 13):
                if self.current_row_idx < num_items:
                    path = self.combined_list[self.current_row_idx]['path']
                    return {'action': 'go', 'path': path}
            elif key == ord('i'):
                if self.current_row_idx < num_items and self.combined_list[self.current_row_idx]['type'] == 'docker':
                    return {'action': 'inspect', 'id': self.combined_list[self.current_row_idx]['id']}
                else:
                    self.set_status("Inspect is only for Docker containers.", "warn")
            elif key == ord('a'):
                self.handle_add_bookmark()
            elif key == ord('d'):
                self.handle_delete_bookmark()
        
        return None # Exit without action

# --- Standalone Execution ---

if __name__ == '__main__':
    action_details = None
    try:
        action_details = curses.wrapper(lambda stdscr: TuiApp(stdscr).run())
    except curses.error as e:
        print(f"Ошибка Curses: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nВыход из TUI.", file=sys.stdout)
        sys.exit(0)
    except Exception as e:
        print(f"\nНеожиданная ошибка в TUI: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    if action_details:
        action = action_details.get('action')
        if action == 'go':
            create_navigation_scripts(action_details.get('path'))
        elif action == 'inspect':
            container_id = action_details.get('id')
            if container_id:
                print(f"Запуск 'docker inspect' для {container_id[:12]}...")
                os.system(f"docker inspect {container_id}")