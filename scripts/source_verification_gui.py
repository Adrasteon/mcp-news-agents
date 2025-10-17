#!/usr/bin/env python3
"""Tkinter desktop app to review news sources with quick categorisation."""

from __future__ import annotations

import argparse
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from source_review_data import (
    DEFAULT_OUTPUT,
    STATUS_DESCRIPTIONS,
    build_result_row,
    fetch_sources,
    filter_sources,
    label_for,
    load_existing_results,
    write_result,
)

STATUS_ORDER = ["ok", "paywall", "cookie", "modal", "non_news"]
HOTKEYS = {
    "o": "ok",
    "p": "paywall",
    "c": "cookie",
    "m": "modal",
    "n": "non_news",
    "s": "skip",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open each source in a browser and record whether it is usable."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV file to append results (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--start-id",
        type=int,
        help="Skip any sources with an id lower than this value.",
    )
    parser.add_argument(
        "--recheck",
        action="store_true",
        help="Re-review even if the source already has a logged result.",
    )
    parser.add_argument(
        "--reviewer",
        help="Optional reviewer name or initials saved with each result.",
    )
    return parser.parse_args()


class ReviewApp:
    def __init__(self, root: tk.Tk, args: argparse.Namespace) -> None:
        self.root = root
        self.args = args
        self.output = args.output
        self.reviewer = args.reviewer or ""

        all_sources = fetch_sources()
        self.existing = load_existing_results(self.output)
        self.sources = filter_sources(all_sources, args.start_id, self.existing, args.recheck)

        self.total_all = len(all_sources)
        self.total_pending = len(self.sources)
        self.index = 0
        self.selected_statuses: set[str] = set()

        self.root.title("Source Verification")
        self.root.geometry("720x480")

        self.title_label = ttk.Label(root, text="", font=("Helvetica", 16, "bold"))
        self.title_label.pack(pady=(16, 8))

        self.url_button = ttk.Button(root, text="Open in browser", command=self.open_current)
        self.url_button.pack()

        self.url_label = ttk.Label(root, text="", foreground="#1a0dab", cursor="hand2")
        self.url_label.pack(pady=(4, 12))
        self.url_label.bind("<Button-1>", lambda _event: self.open_current())

        self.progress_label = ttk.Label(root, text="")
        self.progress_label.pack()

        self.hotkey_label = ttk.Label(
            root,
            text=(
                "Shortcuts: o=Toggle OK, p=Toggle Paywall, c=Toggle Cookie, m=Toggle Modal, "
                "n=Toggle Non-news, s=Skip, Ctrl+Enter=Submit"
            ),
        )
        self.hotkey_label.pack(pady=(8, 12))

        notes_frame = ttk.Frame(root)
        notes_frame.pack(fill=tk.BOTH, expand=True, padx=16)
        ttk.Label(notes_frame, text="Notes (optional):").pack(anchor=tk.W)
        self.notes_text = tk.Text(notes_frame, height=6, wrap=tk.WORD)
        self.notes_text.pack(fill=tk.BOTH, expand=True, pady=(2, 12))

        buttons_frame = ttk.Frame(root)
        buttons_frame.pack(pady=8)

        self.status_vars: dict[str, tk.BooleanVar] = {}
        self.status_buttons: dict[str, tk.Checkbutton] = {}
        self._button_bg = root.cget("bg")
        for status in STATUS_ORDER:
            var = tk.BooleanVar(value=False)
            self.status_vars[status] = var
            btn = tk.Checkbutton(
                buttons_frame,
                text=STATUS_DESCRIPTIONS[status],
                variable=var,
                command=lambda s=status: self.toggle_status(s),
                indicatoron=False,
                width=18,
                selectcolor="#1f6feb",
                bg=self._button_bg,
                activebackground=self._button_bg,
            )
            btn.pack(side=tk.LEFT, padx=4)
            self.status_buttons[status] = btn

        self.skip_button = ttk.Button(buttons_frame, text="Skip", command=self.skip_current, width=10)
        self.skip_button.pack(side=tk.LEFT, padx=4)

        self.submit_button = ttk.Button(
            buttons_frame,
            text="Submit",
            command=self.submit_current,
            width=10,
            state=tk.DISABLED,
        )
        self.submit_button.pack(side=tk.LEFT, padx=4)

        self.selection_label = ttk.Label(root, text="Selected statuses: (none)")
        self.selection_label.pack()

        self.root.bind_all("<Return>", lambda _e: self.open_current())
        for key, status in HOTKEYS.items():
            self.root.bind_all(f"<{key}>", lambda _e, s=status: self._on_hotkey(s))
        self.root.bind_all("<Control-Return>", lambda _e: self.submit_current())

        if not self.sources:
            messagebox.showinfo("Source Verification", "No sources to review with the current filters.")
            self.disable_inputs()
        else:
            self.update_view()

    def current_source(self) -> dict:
        return self.sources[self.index]

    def open_current(self) -> None:
        if not self.sources or self.index >= len(self.sources):
            return
        source = self.current_source()
        webbrowser.open_new_tab(source["url"])

    def submit_current(self) -> None:
        if not self.sources or self.index >= len(self.sources):
            return
        if not self.selected_statuses:
            messagebox.showwarning("Source Verification", "Select at least one status before submitting.")
            return

        source = self.current_source()
        notes = self.notes_text.get("1.0", tk.END).strip()
        statuses = [status for status in STATUS_ORDER if status in self.selected_statuses]
        row = build_result_row(
            source_id=source["id"],
            label=label_for(source),
            url=source["url"],
            status=";".join(statuses),
            notes=notes,
            reviewer=self.reviewer,
        )
        write_result(self.output, row)
        self.existing[source["id"]] = row
        self.advance()

    def skip_current(self) -> None:
        self.advance()

    def advance(self) -> None:
        if not self.sources:
            return
        self.index += 1
        self.notes_text.delete("1.0", tk.END)
        if self.index >= len(self.sources):
            messagebox.showinfo("Source Verification", "All selected sources have been processed.")
            self.disable_inputs()
        else:
            self.update_view()

    def update_view(self) -> None:
        self.reset_selection()
        source = self.current_source()
        label = label_for(source)
        self.title_label.config(text=f"#{source['id']} — {label}")
        self.url_label.config(text=source["url"])
        self.progress_label.config(
            text=f"Reviewing {self.index + 1} of {self.total_pending} (out of {self.total_all} total)"
        )
        self.notes_text.delete("1.0", tk.END)

    def disable_inputs(self) -> None:
        self.url_button.config(state=tk.DISABLED)
        self.url_label.config(cursor="arrow")
        for btn in self.status_buttons.values():
            btn.config(state=tk.DISABLED)
        self.submit_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
        self.notes_text.config(state=tk.DISABLED)
        self.progress_label.config(text="Review complete")
        self.title_label.config(text="All sources processed")
        self.url_label.config(text="")
        self.root.unbind_all("<Return>")
        for key in HOTKEYS:
            self.root.unbind_all(f"<{key}>")
        self.root.unbind_all("<Control-Return>")

    def _on_hotkey(self, status: str) -> None:
        if self.notes_text.focus_get() is self.notes_text:
            return
        if status == "skip":
            self.skip_current()
        else:
            var = self.status_vars[status]
            var.set(not var.get())
            self.toggle_status(status)

    def toggle_status(self, status: str) -> None:
        if not self.sources or self.index >= len(self.sources):
            self.status_vars[status].set(False)
            return

        if self.status_vars[status].get():
            self.selected_statuses.add(status)
        else:
            self.selected_statuses.discard(status)

        self.update_selection_label()
        self.update_submit_state()

    def reset_selection(self) -> None:
        for status, var in self.status_vars.items():
            var.set(False)
        self.selected_statuses.clear()
        self.update_selection_label()
        self.update_submit_state()

    def update_selection_label(self) -> None:
        if self.selected_statuses:
            labels = [STATUS_DESCRIPTIONS[status] for status in STATUS_ORDER if status in self.selected_statuses]
            self.selection_label.config(text=f"Selected statuses: {', '.join(labels)}")
        else:
            self.selection_label.config(text="Selected statuses: (none)")

    def update_submit_state(self) -> None:
        if self.selected_statuses:
            self.submit_button.config(state=tk.NORMAL)
        else:
            self.submit_button.config(state=tk.DISABLED)


def main() -> None:
    args = parse_args()
    root = tk.Tk()
    ReviewApp(root, args)
    root.mainloop()


if __name__ == "__main__":
    main()