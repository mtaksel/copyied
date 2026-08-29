from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox


MAX_HISTORY = 10
MAX_FAVORITES = 10
POLL_MS = 850
URL_RE = re.compile(r"https?://[^\s<>'\"]+|www\.[^\s<>'\"]+", re.IGNORECASE)

if sys.platform == "darwin":
    APP_DIR = Path.home() / "Library" / "Application Support" / "Copyied"
elif os.name == "nt":
    APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "ClipboardHistoryTool"
else:
    APP_DIR = Path(os.getenv("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "Copyied"
STORE_FILE = APP_DIR / "store.json"

DEFAULT_SETTINGS = {
    "dark_mode": True,
    "always_on_top": False,
}

_SINGLE_INSTANCE_HANDLE: int | None = None


def ensure_single_instance() -> None:
    global _SINGLE_INSTANCE_HANDLE
    if os.getenv("COPYIED_TEST_INSTANCE") == "1":
        return
    if os.name != "nt" or _SINGLE_INSTANCE_HANDLE:
        return
    try:
        import ctypes
    except ImportError:
        return

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, "CopyiedClipboardHistoryTool")
    if handle and kernel32.GetLastError() == 183:
        sys.exit(0)
    _SINGLE_INSTANCE_HANDLE = handle


def now_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def short_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%H:%M")
    except ValueError:
        return value


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_link(value: str) -> str:
    value = value.strip()
    if value.lower().startswith("www."):
        return f"https://{value}"
    return value


def extract_first_link(value: str) -> str | None:
    match = URL_RE.search(value)
    if not match:
        return None
    return normalize_link(match.group(0).rstrip(".,);]"))


def preview_text(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1]}..."


@dataclass
class ClipboardRead:
    kind: str
    content: str
    fingerprint: str


class ClipboardStore:
    def __init__(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, Any] = {
            "history": [],
            "favorites": [],
            "settings": dict(DEFAULT_SETTINGS),
        }
        self.load()

    def load(self) -> None:
        if not STORE_FILE.exists():
            return
        try:
            loaded = json.loads(STORE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        self.data["history"] = self.text_items_only(loaded.get("history", []))[:MAX_HISTORY]
        self.data["favorites"] = self.text_items_only(loaded.get("favorites", []))[:MAX_FAVORITES]
        self.data["settings"] = {**DEFAULT_SETTINGS, **loaded.get("settings", {})}

    def text_items_only(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        for item in items:
            kind = item.get("kind", "text")
            if kind == "image":
                continue
            content = item.get("content", "")
            if not isinstance(content, str) or not content.strip():
                continue
            item["kind"] = "link" if extract_first_link(content) else "text"
            cleaned.append(item)
        return cleaned

    def save(self) -> None:
        STORE_FILE.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def setting(self, key: str) -> Any:
        return self.data["settings"].get(key, DEFAULT_SETTINGS.get(key))

    def set_setting(self, key: str, value: Any) -> None:
        self.data["settings"][key] = value
        self.save()

    def add_history(self, read: ClipboardRead) -> bool:
        if not read.fingerprint:
            return False

        existing_index = next(
            (i for i, item in enumerate(self.data["history"]) if item.get("fingerprint") == read.fingerprint),
            None,
        )
        if existing_index is not None:
            if existing_index == 0:
                return False
            item = self.data["history"].pop(existing_index)
            item["created_at"] = now_stamp()
            self.data["history"].insert(0, item)
            self.save()
            return True

        self.data["history"].insert(
            0,
            {
                "id": str(uuid.uuid4()),
                "kind": read.kind,
                "content": read.content,
                "fingerprint": read.fingerprint,
                "created_at": now_stamp(),
            },
        )
        self.data["history"] = self.data["history"][:MAX_HISTORY]
        self.save()
        return True

    def add_favorite(self, item: dict[str, Any]) -> tuple[bool, str]:
        if any(fav.get("fingerprint") == item.get("fingerprint") for fav in self.data["favorites"]):
            return False, "Already in favorites"
        if len(self.data["favorites"]) >= MAX_FAVORITES:
            return False, "Favorite limit reached"

        self.data["favorites"].insert(
            0,
            {
                "id": str(uuid.uuid4()),
                "kind": item.get("kind", "text"),
                "content": item.get("content", ""),
                "fingerprint": item.get("fingerprint"),
                "created_at": now_stamp(),
            },
        )
        self.data["favorites"] = self.data["favorites"][:MAX_FAVORITES]
        self.save()
        return True, "Added to favorites"

    def remove_favorite_by_fingerprint(self, fingerprint: str | None) -> bool:
        if not fingerprint:
            return False
        before = len(self.data["favorites"])
        self.data["favorites"] = [
            item for item in self.data["favorites"] if item.get("fingerprint") != fingerprint
        ]
        removed = len(self.data["favorites"]) != before
        if removed:
            self.save()
        return removed

    def remove_item(self, item_id: str) -> None:
        self.data["history"] = [item for item in self.data["history"] if item.get("id") != item_id]
        self.data["favorites"] = [item for item in self.data["favorites"] if item.get("id") != item_id]
        self.save()

    def clear_history(self) -> None:
        self.data["history"] = []
        self.save()


class ClipboardReader:
    def __init__(self, root: ctk.CTk) -> None:
        self.root = root

    def read(self) -> ClipboardRead | None:
        try:
            value = self.root.clipboard_get()
        except tk.TclError:
            return None
        if not value or not value.strip():
            return None

        content = value.strip()
        kind = "link" if extract_first_link(content) else "text"
        return ClipboardRead(kind=kind, content=content, fingerprint=sha256_text(f"{kind}:{content}"))


class LinkClipWidget(ctk.CTk):
    light = {
        "rose": "#BD9391",
        "gray": "#ADBABD",
        "blue_gray": "#91B7C7",
        "sky": "#6EB4D1",
        "bright": "#6CBEED",
        "surface": "#E8EEF2",
        "panel": "#F7FAFC",
        "card": "#FFFFFF",
        "line": "#CBD8DF",
        "ink": "#111A24",
        "muted": "#65727F",
        "soft": "#E3EDF3",
        "selected": "#D7ECF8",
    }
    dark = {
        "rose": "#BD9391",
        "gray": "#ADBABD",
        "blue_gray": "#91B7C7",
        "sky": "#6EB4D1",
        "bright": "#6CBEED",
        "surface": "#030912",
        "panel": "#0A111B",
        "card": "#0E1722",
        "line": "#253343",
        "ink": "#F3F8FC",
        "muted": "#95A1AD",
        "soft": "#151F2B",
        "selected": "#1D4572",
    }

    def __init__(self) -> None:
        ensure_single_instance()
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.store = ClipboardStore()
        self.colors = self.dark if self.store.setting("dark_mode") else self.light
        ctk.set_appearance_mode("dark" if self.store.setting("dark_mode") else "light")

        self.title("Copyied")
        self.geometry("560x540")
        self.minsize(500, 480)
        self.overrideredirect(True)
        self.attributes("-topmost", bool(self.store.setting("always_on_top")))

        self.reader = ClipboardReader(self)
        self.monitoring = True
        self.active_tab = "recent"
        self.type_filter = "all"
        self.selected_id: str | None = None
        self.last_clipboard_fingerprint = self.store.data["history"][0].get("fingerprint") if self.store.data["history"] else ""
        self.last_render_key = ""

        self.search_var = ctk.StringVar(value="")
        self.status_var = ctk.StringVar(value="Watching text clipboard")
        self.dark_mode_var = ctk.BooleanVar(value=bool(self.store.setting("dark_mode")))
        self.always_on_top_var = ctk.BooleanVar(value=bool(self.store.setting("always_on_top")))

        self.build_ui()
        self.apply_theme()
        self.bind_drag_targets(self, self.shell, self.header, self.tabs_card)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.search_entry.bind("<KeyRelease>", lambda _event: self.render(force=True))
        self.render(force=True)
        self.after(0, lambda: self.geometry("560x540"))
        self.after(POLL_MS, self.poll_clipboard)

    def build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.shell = ctk.CTkFrame(self, corner_radius=20, border_width=1)
        self.shell.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.shell.grid_columnconfigure(0, weight=1)
        self.shell.grid_rowconfigure(2, weight=1)

        self.header = ctk.CTkFrame(self.shell, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 12))
        self.header.grid_columnconfigure(2, weight=1)

        self.logo = ctk.CTkLabel(
            self.header,
            text="C",
            width=30,
            height=30,
            corner_radius=9,
            fg_color=self.colors["selected"],
            text_color=self.colors["bright"],
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
        )
        self.logo.grid(row=0, column=0, padx=(0, 9))

        self.brand_label = ctk.CTkLabel(
            self.header,
            text="Copyied",
            text_color=self.colors["ink"],
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
        )
        self.brand_label.grid(row=0, column=1, padx=(0, 16))

        self.search_shell = ctk.CTkFrame(self.header, height=36, corner_radius=11, border_width=1)
        self.search_shell.grid(row=0, column=2, sticky="ew")
        self.search_shell.grid_columnconfigure(1, weight=1)
        self.search_shell.grid_propagate(False)

        self.search_icon = ctk.CTkLabel(
            self.search_shell,
            text="Q",
            width=28,
            text_color=self.colors["muted"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        )
        self.search_icon.grid(row=0, column=0, sticky="ns", padx=(7, 0))

        self.search_entry = ctk.CTkEntry(
            self.search_shell,
            placeholder_text="Start typing to search...",
            height=30,
            corner_radius=8,
            border_width=0,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self.search_entry.grid(row=0, column=1, sticky="ew", pady=3)

        self.search_kbd = ctk.CTkLabel(
            self.search_shell,
            text="Ctrl K",
            width=44,
            height=22,
            corner_radius=7,
            text_color=self.colors["muted"],
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        )
        self.search_kbd.grid(row=0, column=2, sticky="e", padx=(6, 7))

        self.pin_button = ctk.CTkButton(
            self.header,
            text="Pin",
            width=42,
            height=34,
            corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self.toggle_always_on_top_from_header,
        )
        self.pin_button.grid(row=0, column=3, padx=(8, 0))

        self.settings_button = ctk.CTkButton(
            self.header,
            text="Set",
            width=42,
            height=34,
            corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=lambda: self.set_tab("Settings"),
        )
        self.settings_button.grid(row=0, column=4, padx=(6, 0))

        self.tabs_card = ctk.CTkFrame(self.shell, corner_radius=12, border_width=1)
        self.tabs_card.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))
        self.tabs_card.grid_columnconfigure(0, weight=1)

        self.tabs = ctk.CTkSegmentedButton(
            self.tabs_card,
            values=["Recent", "Favorites"],
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.set_tab,
        )
        self.tabs.grid(row=0, column=0, sticky="ew", padx=3, pady=3)
        self.tabs.set("Recent")

        self.list_frame = ctk.CTkFrame(self.shell, corner_radius=14, border_width=1)
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 10))
        self.list_frame.grid_columnconfigure(0, weight=1)

        self.footer = ctk.CTkFrame(self.shell, fg_color="transparent")
        self.footer.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 14))
        self.footer.grid_columnconfigure((0, 1, 2), weight=1)
        for column, text in enumerate(("Up/Down Select", "Enter Paste", "Ctrl K Search")):
            ctk.CTkLabel(
                self.footer,
                text=text,
                text_color=self.colors["muted"],
                font=ctk.CTkFont(family="Segoe UI", size=11),
            ).grid(row=0, column=column, sticky="ew")

    def toggle_always_on_top_from_header(self) -> None:
        self.always_on_top_var.set(not bool(self.always_on_top_var.get()))
        self.toggle_always_on_top()

    def paint_action_button(self, button: ctk.CTkButton, active: bool = False) -> None:
        c = self.colors
        button.configure(
            fg_color=c["selected"] if active else "transparent",
            hover_color=c["soft"],
            text_color=c["bright"] if active else c["muted"],
        )

    def bind_drag_targets(self, *widgets: Any) -> None:
        for widget in widgets:
            widget.bind("<ButtonPress-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag_window)

    def start_drag(self, event: tk.Event) -> None:
        self._drag_offset_x = event.x_root - self.winfo_x()
        self._drag_offset_y = event.y_root - self.winfo_y()

    def drag_window(self, event: tk.Event) -> None:
        x = event.x_root - getattr(self, "_drag_offset_x", 0)
        y = event.y_root - getattr(self, "_drag_offset_y", 0)
        self.geometry(f"+{x}+{y}")

    def apply_theme(self) -> None:
        c = self.colors
        self.configure(fg_color=c["surface"])
        self.shell.configure(fg_color=c["panel"], border_color=c["line"])
        self.tabs_card.configure(fg_color=c["soft"], border_color=c["line"])
        self.brand_label.configure(text_color=c["ink"])
        self.logo.configure(fg_color=c["selected"], text_color=c["bright"])
        self.search_shell.configure(fg_color=c["soft"], border_color=c["line"])
        self.search_icon.configure(text_color=c["muted"])
        self.search_kbd.configure(fg_color=c["card"], text_color=c["muted"])
        self.paint_action_button(self.pin_button, bool(self.store.setting("always_on_top")))
        self.paint_action_button(self.settings_button, self.active_tab == "settings")
        self.tabs.configure(
            selected_color=c["selected"],
            selected_hover_color=c["selected"],
            unselected_color=c["soft"],
            unselected_hover_color=c["card"],
            text_color=c["ink"],
        )
        self.search_entry.configure(
            fg_color=c["soft"],
            border_color=c["soft"],
            text_color=c["ink"],
            placeholder_text_color=c["gray"],
        )
        self.list_frame.configure(
            fg_color=c["card"],
            border_color=c["line"],
        )
        for child in self.footer.winfo_children():
            child.configure(text_color=c["muted"])

    def set_tab(self, value: str) -> None:
        self.active_tab = value.lower()
        self.selected_id = None
        self.apply_theme()
        self.render(force=True)

    def toggle_monitoring(self) -> None:
        self.monitoring = not self.monitoring
        self.status_var.set("Watching text clipboard" if self.monitoring else "Paused")
        self.apply_theme()

    def toggle_dark_mode(self) -> None:
        enabled = bool(self.dark_mode_var.get())
        self.store.set_setting("dark_mode", enabled)
        ctk.set_appearance_mode("dark" if enabled else "light")
        self.colors = self.dark if enabled else self.light
        self.apply_theme()
        self.render(force=True)

    def toggle_always_on_top(self) -> None:
        enabled = bool(self.always_on_top_var.get())
        self.store.set_setting("always_on_top", enabled)
        self.attributes("-topmost", enabled)
        self.status_var.set("Always on top enabled" if enabled else "Always on top disabled")
        self.apply_theme()
        self.render(force=True)

    def poll_clipboard(self) -> None:
        if self.monitoring:
            read = self.reader.read()
            if read and read.fingerprint != self.last_clipboard_fingerprint:
                self.last_clipboard_fingerprint = read.fingerprint
                if self.store.add_history(read):
                    self.status_var.set(f"Saved {self.kind_label(read.kind).lower()}")
                    self.render(force=True)
        self.after(POLL_MS, self.poll_clipboard)

    def render(self, force: bool = False) -> None:
        items = self.visible_items()
        limit = MAX_FAVORITES if self.active_tab == "favorites" else MAX_HISTORY
        render_key = json.dumps(
            {
                "tab": self.active_tab,
                "query": self.current_query(),
                "ids": [item.get("id") for item in items],
                "fav": [item.get("fingerprint") for item in self.store.data["favorites"]],
                "settings": self.store.data["settings"],
            },
            sort_keys=True,
        )
        if not force and render_key == self.last_render_key:
            return
        self.last_render_key = render_key

        for child in self.list_frame.winfo_children():
            child.destroy()

        self.search_entry.configure(state="disabled" if self.active_tab == "settings" else "normal")

        if self.active_tab == "settings":
            self.render_settings()
            return

        if not items:
            self.render_empty()
            return

        visible = items[:limit]
        for index, item in enumerate(visible):
            self.render_row(item, index, index == len(visible) - 1)

    def visible_items(self) -> list[dict[str, Any]]:
        if self.active_tab == "settings":
            return []

        items = self.store.data["favorites"] if self.active_tab == "favorites" else self.store.data["history"]
        query = self.current_query().strip().lower()
        if query:
            items = [
                item
                for item in items
                if query in item.get("content", "").lower()
            ]
        return items

    def render_empty(self) -> None:
        c = self.colors
        card = ctk.CTkFrame(self.list_frame, fg_color=c["card"], corner_radius=10, border_width=0)
        card.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        ctk.CTkLabel(
            card,
            text="Nothing here yet",
            text_color=c["ink"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(12, 2))
        ctk.CTkLabel(
            card,
            text="Copy something to start.",
            text_color=c["muted"],
            wraplength=285,
            justify="left",
            font=ctk.CTkFont(family="Segoe UI", size=12),
        ).pack(anchor="w", padx=12, pady=(0, 12))

    def render_settings(self) -> None:
        self.render_switch_row(0, "Dark mode", "Use the darker palette.", self.dark_mode_var, self.toggle_dark_mode)
        self.render_switch_row(
            1,
            "Always on top",
            "Keep Copyied above other windows.",
            self.always_on_top_var,
            self.toggle_always_on_top,
        )
        self.render_info_row(2, "History limit", str(MAX_HISTORY))
        self.render_info_row(3, "Favorite limit", str(MAX_FAVORITES))
        self.render_info_row(4, "Data file", str(STORE_FILE))

        ctk.CTkButton(
            self.list_frame,
            text="Clear recent history",
            height=36,
            corner_radius=8,
            fg_color=self.colors["rose"],
            hover_color="#A87F7D",
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.clear_history,
        ).grid(row=5, column=0, sticky="ew", padx=8, pady=10)

        ctk.CTkButton(
            self.list_frame,
            text="Quit Copyied",
            height=34,
            corner_radius=8,
            fg_color=self.colors["soft"],
            hover_color="#D9F0F9" if self.colors is self.light else "#284A58",
            text_color=self.colors["ink"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self.destroy,
        ).grid(row=6, column=0, sticky="ew", padx=8, pady=(0, 10))

    def render_switch_row(
        self,
        row_index: int,
        title: str,
        subtitle: str,
        variable: ctk.BooleanVar,
        command: Any,
    ) -> None:
        c = self.colors
        row = ctk.CTkFrame(self.list_frame, fg_color=c["card"], corner_radius=10, border_width=0)
        row.grid(row=row_index, column=0, sticky="ew", padx=0, pady=(0 if row_index == 0 else 6, 0))
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            row,
            text=title,
            text_color=c["ink"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        ctk.CTkLabel(
            row,
            text=subtitle,
            text_color=c["muted"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))
        ctk.CTkSwitch(
            row,
            text="",
            variable=variable,
            command=command,
            width=44,
            button_color="#FFFFFF",
            button_hover_color="#FFFFFF",
            progress_color=c["bright"],
            fg_color=c["gray"],
        ).grid(row=0, column=1, rowspan=2, padx=12, pady=10)

    def render_info_row(self, row_index: int, title: str, value: str) -> None:
        c = self.colors
        row = ctk.CTkFrame(self.list_frame, fg_color=c["card"], corner_radius=10, border_width=0)
        row.grid(row=row_index, column=0, sticky="ew", padx=0, pady=(6, 0))
        row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            row,
            text=title,
            text_color=c["ink"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=10)
        ctk.CTkLabel(
            row,
            text=value,
            text_color=c["muted"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
            wraplength=185,
            justify="right",
        ).grid(row=0, column=1, sticky="e", padx=12, pady=10)

    def render_row(self, item: dict[str, Any], index: int, is_last: bool = False) -> None:
        c = self.colors
        row = ctk.CTkFrame(
            self.list_frame,
            fg_color="transparent",
            corner_radius=0,
            border_width=0,
        )
        row.grid(row=index * 2, column=0, sticky="ew", padx=0, pady=0)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row,
            text=self.item_badge(item),
            width=28,
            height=28,
            corner_radius=8,
            fg_color=c["soft"],
            text_color=c["bright"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        ).grid(row=0, column=0, padx=(14, 4), pady=9)

        content = ctk.CTkLabel(
            row,
            text=self.item_content(item),
            text_color=c["ink"],
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        content.grid(row=0, column=1, sticky="ew", padx=(8, 6), pady=10)

        ctk.CTkButton(
            row,
            text="♥" if self.is_favorite(item) else "♡",
            width=28,
            height=26,
            corner_radius=8,
            fg_color="transparent",
            hover_color="#F0E7E6" if c is self.light else "#3B2D34",
            text_color=c["rose"] if self.is_favorite(item) else c["gray"],
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            command=lambda item_id=item.get("id"): self.favorite_item(item_id),
        ).grid(row=0, column=2, padx=(0, 2), pady=8)

        ctk.CTkButton(
            row,
            text="⧉",
            width=44,
            height=26,
            corner_radius=8,
            fg_color="transparent",
            hover_color="#D9F0F9" if c is self.light else "#284A58",
            text_color=c["sky"],
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            command=lambda item_id=item.get("id"): self.copy_item(item_id),
        ).grid(row=0, column=3, padx=(0, 8), pady=8)

        action = ctk.CTkFrame(row, width=58, height=28, corner_radius=8, fg_color="transparent")
        action.grid(row=0, column=4, sticky="e", padx=(0, 14), pady=8)
        action.grid_propagate(False)

        time_label = ctk.CTkLabel(
            action,
            text=short_time(item.get("created_at", "")),
            width=58,
            height=28,
            text_color=c["muted"],
            font=ctk.CTkFont(family="Consolas", size=10),
        )
        time_label.place(x=0, y=0)

        delete_button = ctk.CTkButton(
            action,
            text="Delete",
            width=58,
            height=28,
            corner_radius=8,
            fg_color=c["rose"],
            hover_color="#A87F7D" if c is self.light else "#A87F7D",
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            command=lambda item_id=item.get("id"): self.delete_item(item_id),
        )
        delete_button.place(x=58, y=0)

        for widget in (action, time_label, delete_button):
            widget.bind("<Enter>", lambda _event, a=action, b=delete_button: self.show_delete_button(a, b))
            widget.bind("<Leave>", lambda _event, a=action, b=delete_button: self.queue_hide_delete_button(a, b))

        for widget in (row, content):
            widget.bind("<Button-1>", lambda _event, item_id=item.get("id"): self.select_item(item_id))
            widget.bind("<Double-Button-1>", lambda _event, item_id=item.get("id"): self.open_item(item_id))

        if not is_last:
            divider = ctk.CTkFrame(self.list_frame, height=1, fg_color=c["line"], corner_radius=0)
            divider.grid(row=index * 2 + 1, column=0, sticky="ew", padx=14, pady=0)

    def show_delete_button(self, action: ctk.CTkFrame, delete_button: ctk.CTkButton) -> None:
        self.slide_delete_button(action, delete_button, target_x=0)

    def queue_hide_delete_button(self, action: ctk.CTkFrame, delete_button: ctk.CTkButton) -> None:
        if not action.winfo_exists():
            return
        hide_job = getattr(action, "_delete_hide_job", None)
        if hide_job:
            action.after_cancel(hide_job)
        action._delete_hide_job = action.after(90, lambda: self.hide_delete_button_if_outside(action, delete_button))

    def hide_delete_button_if_outside(self, action: ctk.CTkFrame, delete_button: ctk.CTkButton) -> None:
        if not action.winfo_exists() or not delete_button.winfo_exists():
            return
        px = action.winfo_pointerx()
        py = action.winfo_pointery()
        inside = (
            action.winfo_rootx() <= px <= action.winfo_rootx() + action.winfo_width()
            and action.winfo_rooty() <= py <= action.winfo_rooty() + action.winfo_height()
        )
        if not inside:
            self.slide_delete_button(action, delete_button, target_x=58)

    def slide_delete_button(self, action: ctk.CTkFrame, delete_button: ctk.CTkButton, target_x: int) -> None:
        if not action.winfo_exists() or not delete_button.winfo_exists():
            return
        hide_job = getattr(action, "_delete_hide_job", None)
        if hide_job:
            action.after_cancel(hide_job)
            action._delete_hide_job = None
        slide_job = getattr(action, "_delete_slide_job", None)
        if slide_job:
            action.after_cancel(slide_job)

        try:
            current_x = int(float(delete_button.place_info().get("x", 58)))
        except (TypeError, ValueError):
            current_x = 58
        if current_x == target_x:
            return

        step = -8 if target_x < current_x else 8
        next_x = current_x + step
        if step < 0:
            next_x = max(target_x, next_x)
        else:
            next_x = min(target_x, next_x)
        delete_button.place_configure(x=next_x)
        action._delete_slide_job = action.after(
            22,
            lambda: self.slide_delete_button(action, delete_button, target_x),
        )

    def clear_history(self) -> None:
        if not self.store.data["history"]:
            self.status_var.set("Recent history is already empty")
            return
        if not messagebox.askyesno("Clear history", "Delete the 10 recent items? Favorites stay saved."):
            return
        self.store.clear_history()
        self.selected_id = None
        self.last_clipboard_fingerprint = ""
        self.status_var.set("Recent history cleared")
        self.render(force=True)

    def select_item(self, item_id: str | None) -> None:
        self.selected_id = item_id
        item = self.find_item_by_id(item_id)
        if item:
            self.status_var.set(f"{self.kind_label(item.get('kind', 'text'))} selected")

    def copy_item(self, item_id: str | None) -> None:
        self.selected_id = item_id
        item = self.find_item_by_id(item_id)
        if not item:
            return
        self.clipboard_clear()
        self.clipboard_append(item.get("content", ""))
        self.last_clipboard_fingerprint = item.get("fingerprint", "")
        self.status_var.set("Copied")

    def delete_item(self, item_id: str | None) -> None:
        if not item_id:
            return
        self.store.remove_item(item_id)
        if self.selected_id == item_id:
            self.selected_id = None
        self.status_var.set("Deleted")
        self.render(force=True)

    def favorite_item(self, item_id: str | None) -> None:
        item = self.find_item_by_id(item_id)
        if not item:
            return
        if self.is_favorite(item):
            self.store.remove_favorite_by_fingerprint(item.get("fingerprint"))
            self.status_var.set("Removed from favorites")
            self.render(force=True)
            return
        ok, message = self.store.add_favorite(item)
        self.status_var.set(message)
        if ok:
            self.render(force=True)

    def open_item(self, item_id: str | None) -> None:
        item = self.find_item_by_id(item_id)
        if not item:
            return
        link = extract_first_link(item.get("content", ""))
        if link:
            webbrowser.open(link)

    def find_item_by_id(self, item_id: str | None) -> dict[str, Any] | None:
        if not item_id:
            return None
        for bucket in (self.store.data["history"], self.store.data["favorites"]):
            for item in bucket:
                if item.get("id") == item_id:
                    return item
        return None

    def item_content(self, item: dict[str, Any]) -> str:
        return preview_text(item.get("content", ""), 64)

    def current_query(self) -> str:
        if not hasattr(self, "search_entry"):
            return ""
        try:
            return self.search_entry.get()
        except tk.TclError:
            return ""

    def item_badge(self, item: dict[str, Any]) -> str:
        content = item.get("content", "").strip()
        link = extract_first_link(content)
        if link:
            host = re.sub(r"^https?://", "", link, flags=re.IGNORECASE).split("/", 1)[0]
            host = host[4:] if host.lower().startswith("www.") else host
            return host[:1].upper() or "@"
        if re.match(r"^#[0-9a-f]{3,8}$", content, re.IGNORECASE):
            return "#"
        if re.match(r"^[A-Za-z]:\\", content):
            return "F"
        return "T"

    def is_favorite(self, item: dict[str, Any]) -> bool:
        return any(fav.get("fingerprint") == item.get("fingerprint") for fav in self.store.data["favorites"])

    def kind_label(self, kind: str) -> str:
        return {"link": "Link", "text": "Text"}.get(kind, kind.title())


if __name__ == "__main__":
    LinkClipWidget().mainloop()
