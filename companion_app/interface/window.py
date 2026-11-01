"""Tkinter window and thread-safe UI update helpers."""

import tkinter as tk
from tkinter import scrolledtext


class CompanionWindow:
    """Owns the desktop widgets and marshals updates onto Tk's event loop."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Companion")
        self.root.geometry("560x650")
        self.root.minsize(450, 500)
        self.root.configure(bg="#17131b")

        title = tk.Label(
            self.root,
            text="Companion",
            font=("Segoe UI", 18, "bold"),
            bg="#17131b",
            fg="#f5d9ee",
        )
        title.pack(pady=(14, 5))

        self.status = tk.Label(
            self.root,
            text="Companion is ready.",
            font=("Segoe UI", 9),
            bg="#17131b",
            fg="#a999aa",
        )
        self.status.pack(pady=(0, 8))

        self.chat = scrolledtext.ScrolledText(
            self.root,
            wrap=tk.WORD,
            font=("Segoe UI", 11),
            bg="#211c26",
            fg="#eee7ef",
            insertbackground="white",
            relief=tk.FLAT,
            padx=12,
            pady=12,
        )
        self.chat.pack(
            fill=tk.BOTH,
            expand=True,
            padx=12,
            pady=8,
        )
        self.chat.configure(state=tk.DISABLED)

        entry_frame = tk.Frame(self.root, bg="#17131b")
        entry_frame.pack(
            fill=tk.X,
            padx=12,
            pady=(0, 12),
        )

        self.entry = tk.Entry(
            entry_frame,
            font=("Segoe UI", 11),
            bg="#211c26",
            fg="#eee7ef",
            insertbackground="white",
            relief=tk.FLAT,
        )
        self.entry.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
            ipady=9,
        )

        self.send_button = tk.Button(
            entry_frame,
            text="Send",
            font=("Segoe UI", 10, "bold"),
            bg="#35263a",
            fg="#f5d9ee",
            activebackground="#4a3150",
            activeforeground="white",
            relief=tk.FLAT,
            padx=16,
        )
        self.send_button.pack(
            side=tk.RIGHT,
            padx=(8, 0),
            ipady=5,
        )

        self.cancel_button = tk.Button(
            entry_frame,
            text="Cancel",
            font=("Segoe UI", 10, "bold"),
            bg="#4a2525",
            fg="#ffdede",
            activebackground="#633030",
            activeforeground="white",
            relief=tk.FLAT,
            padx=16,
        )
        self.cancel_button.pack(
            side=tk.RIGHT,
            ipady=5,
        )

    def bind_actions(self, send_callback, cancel_callback):
        """Connect application actions after their handlers are defined."""
        self.send_button.configure(command=send_callback)
        self.cancel_button.configure(command=cancel_callback)
        self.entry.bind("<Return>", send_callback)

    def add_message(self, speaker, message):
        """Append a chat message on Tk's owning thread."""
        def update():
            self.chat.configure(state=tk.NORMAL)
            self.chat.insert(
                tk.END,
                f"{speaker}: {message}\n\n",
            )
            self.chat.see(tk.END)
            self.chat.configure(state=tk.DISABLED)

        try:
            self.root.after(0, update)
        except tk.TclError:
            # A worker may finish while the window is closing.
            return

    def set_status(self, message):
        """Update the status label on Tk's owning thread."""
        try:
            self.root.after(
                0,
                lambda: self.status.config(text=message),
            )
        except tk.TclError:
            # Ignore late worker updates after the root is destroyed.
            return

    def run(self):
        self.root.mainloop()
