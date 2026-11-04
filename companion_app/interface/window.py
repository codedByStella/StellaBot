"""Polished Tkinter desktop chat interface for StellaBot Companion."""

import tkinter as tk


class CompanionWindow:
    """Owns the desktop widgets and marshals updates onto Tk's event loop."""

    COLORS = {
        "background": "#10131B",
        "surface": "#171C27",
        "surface_alt": "#1D2432",
        "surface_user": "#292B43",
        "border": "#2A3343",
        "text": "#F1F3F8",
        "muted": "#9AA6B8",
        "subtle": "#8290A4",
        "accent": "#D6A6E8",
        "accent_bright": "#E8C4F2",
        "teal": "#8BD8CC",
        "danger": "#E5A0A8",
    }

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("StellaBot | Desktop Companion")
        self.root.geometry("1040x760")
        self.root.minsize(780, 620)
        self.root.configure(bg=self.COLORS["background"])
        self.root.option_add("*Font", ("Segoe UI", 10))

        self._build_header()
        self._build_conversation()
        self._build_composer()

    def _build_header(self):
        header = tk.Frame(
            self.root,
            bg=self.COLORS["background"],
            padx=28,
            pady=22,
        )
        header.pack(fill=tk.X)

        brand = tk.Frame(header, bg=self.COLORS["background"])
        brand.pack(side=tk.LEFT, fill=tk.Y)

        mark = tk.Canvas(
            brand,
            width=48,
            height=48,
            bg=self.COLORS["background"],
            highlightthickness=0,
        )
        mark.pack(side=tk.LEFT, padx=(0, 13))
        mark.create_oval(2, 2, 46, 46, fill="#30263B", outline="#755887", width=1)
        mark.create_oval(8, 8, 40, 40, fill="#493653", outline="")
        mark.create_text(
            24,
            24,
            text="✦",
            fill=self.COLORS["accent_bright"],
            font=("Segoe UI Symbol", 20, "bold"),
        )

        titles = tk.Frame(brand, bg=self.COLORS["background"])
        titles.pack(side=tk.LEFT, pady=(2, 0), anchor=tk.CENTER)

        tk.Label(
            titles,
            text="STELLABOT",
            bg=self.COLORS["background"],
            fg=self.COLORS["text"],
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=tk.W)

        tk.Label(
            titles,
            text="YOUR DESKTOP COMPANION",
            bg=self.COLORS["background"],
            fg=self.COLORS["muted"],
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor=tk.W, pady=(2, 0))

        status_group = tk.Frame(header, bg=self.COLORS["background"])
        status_group.pack(side=tk.RIGHT, anchor=tk.CENTER, pady=7)

        self.status_dot = tk.Canvas(
            status_group,
            width=10,
            height=10,
            bg=self.COLORS["background"],
            highlightthickness=0,
        )
        self.status_dot.pack(side=tk.LEFT, padx=(0, 8))
        self.status_dot.create_oval(
            1, 1, 9, 9,
            fill=self.COLORS["teal"],
            outline="",
            tags=("status",),
        )

        self.status = tk.Label(
            status_group,
            text="Companion is ready.",
            bg=self.COLORS["background"],
            fg=self.COLORS["teal"],
            font=("Segoe UI", 9, "bold"),
        )
        self.status.pack(side=tk.LEFT)

        divider = tk.Frame(self.root, height=1, bg=self.COLORS["border"])
        divider.pack(fill=tk.X, padx=28)

    def _build_conversation(self):
        section = tk.Frame(
            self.root,
            bg=self.COLORS["background"],
            padx=28,
            pady=20,
        )
        section.pack(fill=tk.BOTH, expand=True)

        section_heading = tk.Frame(section, bg=self.COLORS["background"])
        section_heading.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            section_heading,
            text="CONVERSATION",
            bg=self.COLORS["background"],
            fg=self.COLORS["muted"],
            font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.LEFT)

        tk.Label(
            section_heading,
            text="MEMORY  ·  VISUAL CONTEXT",
            bg=self.COLORS["background"],
            fg=self.COLORS["subtle"],
            font=("Segoe UI", 8, "bold"),
        ).pack(side=tk.RIGHT)

        chat_panel = tk.Frame(
            section,
            bg=self.COLORS["surface"],
            highlightthickness=1,
            highlightbackground=self.COLORS["border"],
        )
        chat_panel.pack(fill=tk.BOTH, expand=True)

        self.chat_canvas = tk.Canvas(
            chat_panel,
            bg=self.COLORS["surface"],
            highlightthickness=0,
            bd=0,
        )
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(
            chat_panel,
            orient=tk.VERTICAL,
            command=self.chat_canvas.yview,
            bg=self.COLORS["surface_alt"],
            troughcolor=self.COLORS["surface"],
            activebackground=self.COLORS["subtle"],
            relief=tk.FLAT,
            bd=0,
            width=10,
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 3), pady=4)
        self.chat_canvas.configure(yscrollcommand=scrollbar.set)

        self.message_list = tk.Frame(
            self.chat_canvas,
            bg=self.COLORS["surface"],
        )
        self.message_window = self.chat_canvas.create_window(
            (0, 0),
            window=self.message_list,
            anchor="nw",
        )

        self.message_list.bind("<Configure>", self._sync_scroll_region)
        self._message_labels = []
        self.chat_canvas.bind("<Configure>", self._sync_message_width)
        self.chat_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _build_composer(self):
        footer = tk.Frame(
            self.root,
            bg=self.COLORS["background"],
            padx=28,
        )
        footer.pack(fill=tk.X, pady=(0, 22))

        composer = tk.Frame(
            footer,
            bg=self.COLORS["surface_alt"],
            highlightthickness=1,
            highlightbackground=self.COLORS["border"],
            padx=10,
            pady=9,
        )
        composer.pack(fill=tk.X)

        self.entry = tk.Entry(
            composer,
            font=("Segoe UI", 11),
            bg=self.COLORS["surface_alt"],
            fg=self.COLORS["text"],
            insertbackground=self.COLORS["accent_bright"],
            selectbackground="#51415E",
            relief=tk.FLAT,
            bd=0,
        )
        self.entry.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
            padx=(8, 12),
            ipady=8,
        )

        self.cancel_button = tk.Button(
            composer,
            text="Cancel",
            font=("Segoe UI", 9, "bold"),
            bg="#35252E",
            fg=self.COLORS["danger"],
            activebackground="#4A303B",
            activeforeground="#FFE8EA",
            relief=tk.FLAT,
            bd=0,
            padx=15,
            pady=9,
            cursor="hand2",
            takefocus=True,
        )
        self.cancel_button.pack(side=tk.RIGHT, padx=(6, 0))

        self.send_button = tk.Button(
            composer,
            text="Send  ↗",
            font=("Segoe UI", 9, "bold"),
            bg="#5A4268",
            fg="#FFFFFF",
            activebackground="#745487",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            bd=0,
            padx=18,
            pady=9,
            cursor="hand2",
            takefocus=True,
        )
        self.send_button.pack(side=tk.RIGHT)

        tk.Label(
            footer,
            text="ENTER TO SEND",
            bg=self.COLORS["background"],
            fg=self.COLORS["subtle"],
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor=tk.E, pady=(8, 0))

    def _sync_scroll_region(self, _event=None):
        self.chat_canvas.configure(
            scrollregion=self.chat_canvas.bbox("all"),
        )

    def _sync_message_width(self, event):
        self.chat_canvas.itemconfigure(
            self.message_window,
            width=event.width,
        )
        wraplength = max(280, min(660, event.width - 150))
        for label in self._message_labels:
            label.configure(wraplength=wraplength)
        self._sync_scroll_region()

    def _on_mousewheel(self, event):
        if self.chat_canvas.winfo_exists():
            self.chat_canvas.yview_scroll(
                int(-1 * (event.delta / 120)),
                "units",
            )

    def bind_actions(self, send_callback, cancel_callback):
        """Connect application actions after their handlers are defined."""
        self.send_button.configure(command=send_callback)
        self.cancel_button.configure(command=cancel_callback)
        self.entry.bind("<Return>", send_callback)

    def add_message(self, speaker, message):
        """Append a styled message card on Tk's owning thread."""
        def update():
            is_user = str(speaker).strip().lower() in {"user", "you"}
            accent = self.COLORS["accent_bright"] if is_user else self.COLORS["teal"]
            bubble_color = (
                self.COLORS["surface_user"]
                if is_user
                else self.COLORS["surface_alt"]
            )
            alignment = tk.RIGHT if is_user else tk.LEFT
            label = "YOU" if is_user else "STELLABOT"

            row = tk.Frame(
                self.message_list,
                bg=self.COLORS["surface"],
            )
            row.pack(fill=tk.X, padx=22, pady=(13, 3))

            bubble = tk.Frame(
                row,
                bg=bubble_color,
                highlightthickness=1,
                highlightbackground=(
                    "#45425F" if is_user else self.COLORS["border"]
                ),
                padx=16,
                pady=11,
            )
            bubble.pack(side=alignment, anchor=tk.E if is_user else tk.W)

            tk.Label(
                bubble,
                text=label,
                bg=bubble_color,
                fg=accent,
                font=("Segoe UI", 8, "bold"),
            ).pack(anchor=tk.W, pady=(0, 5))

            message_label = tk.Label(
                bubble,
                text=str(message),
                bg=bubble_color,
                fg=self.COLORS["text"],
                font=("Segoe UI", 10),
                justify=tk.LEFT,
                anchor=tk.W,
                wraplength=max(
                    280,
                    min(660, self.chat_canvas.winfo_width() - 150),
                ),
            )
            message_label.pack(anchor=tk.W)
            self._message_labels.append(message_label)

            self.root.after_idle(
                lambda: self.chat_canvas.yview_moveto(1.0)
            )

        try:
            self.root.after(0, update)
        except tk.TclError:
            # A worker may finish while the window is closing.
            return

    def set_status(self, message):
        """Update the status label on Tk's owning thread."""
        def update():
            text = str(message)
            lowered = text.lower()
            color = (
                self.COLORS["danger"]
                if any(word in lowered for word in ("error", "failed", "cancel"))
                else self.COLORS["teal"]
            )
            self.status.configure(text=text, fg=color)
            self.status_dot.itemconfigure("status", fill=color)

        try:
            self.root.after(0, update)
        except tk.TclError:
            # Ignore late worker updates after the root is destroyed.
            return

    def run(self):
        self.root.mainloop()
