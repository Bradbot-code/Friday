from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

from brain.ai import FridayAI
from config.preferences import PreferenceStore, UserPreferences
from memory.conversation_manager import ConversationManager
from memory.memory_manager import MemoryManager
from tools.voice import VoiceService
from tools.gmail_tools import GmailTools
from tools.action_center import ActionCenter


class FridayGUI:
    BG = "#050912"
    PANEL = "#0B1322"
    PANEL_RAISED = "#101C2E"
    INPUT_BG = "#07101E"
    BORDER = "#1D3551"
    TEXT = "#EAF7FF"
    MUTED = "#7890A8"
    ACCENT = "#22D3EE"
    ACCENT_BRIGHT = "#67E8F9"
    FRIDAY_ACCENT = "#A78BFA"
    SUCCESS = "#34D399"
    BUTTON = "#14253A"
    RECORDING = "#E5486D"

    def __init__(
        self,
        root: tk.Tk,
        friday: FridayAI,
        voice_service: VoiceService,
        memory_manager: MemoryManager,
        conversation_manager: ConversationManager,
        gmail_tools: GmailTools,
        action_center: ActionCenter,
    ) -> None:
        self.root = root
        self.friday = friday
        self.voice_service = voice_service
        self.memory_manager = memory_manager
        self.conversation_manager = conversation_manager
        self.gmail_tools = gmail_tools
        self.action_center = action_center
        self.preference_store = PreferenceStore(
            Path("data/friday_preferences.json")
        )
        self.preferences = self.preference_store.load()

        try:
            self.voice_service.set_voice(self.preferences.voice)
        except ValueError:
            self.preferences.voice = self.voice_service.voice

        self.speak_replies_enabled = self.preferences.speak_replies
        self.input_device_by_label: dict[str, int] = {}
        self.output_device_by_label: dict[str, int] = {}
        self.input_device_text = tk.StringVar(master=self.root)
        self.output_device_text = tk.StringVar(master=self.root)
        self.voice_text = tk.StringVar(
            master=self.root,
            value=self.voice_service.voice.title(),
        )

        self.voice_enabled = tk.BooleanVar(
            master=self.root,
            value=self.preferences.speak_replies,
        )
        self.status_text = tk.StringVar(
            master=self.root,
            value="Friday is online",
        )
        self.gmail_status_text = tk.StringVar(
            master=self.root,
            value=self.gmail_tools.get_status().message,
        )

        self._configure_window()
        self._build_interface()
        self._load_existing_conversation()

        self.root.after(
            100,
            self._initialize_voice_setting,
        )

        self.root.after(
            250,
            self._request_batch_action_approval,
        )

        self.root.after(
            500,
            self._update_diagnostics_loop,
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self._on_close,
        )

    def _configure_window(self) -> None:
        self.root.title("F.R.I.D.A.Y. // AI Command Interface")
        self.root.geometry("1180x820")
        self.root.minsize(860, 620)
        self.root.configure(bg=self.BG)
        self._configure_styles()

    def _configure_styles(self) -> None:
        """Give native ttk controls the same visual language as the app."""
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Friday.TCombobox",
            fieldbackground=self.INPUT_BG,
            background=self.BUTTON,
            foreground=self.TEXT,
            arrowcolor=self.ACCENT,
            bordercolor=self.BORDER,
            lightcolor=self.BORDER,
            darkcolor=self.BORDER,
            padding=7,
        )
        style.map(
            "Friday.TCombobox",
            fieldbackground=[("readonly", self.INPUT_BG)],
            foreground=[("readonly", self.TEXT)],
            selectbackground=[("readonly", self.INPUT_BG)],
            selectforeground=[("readonly", self.TEXT)],
        )
        style.configure(
            "Friday.TNotebook",
            background=self.BG,
            borderwidth=0,
            tabmargins=(0, 0, 0, 0),
        )
        style.configure(
            "Friday.TNotebook.Tab",
            background=self.PANEL,
            foreground=self.MUTED,
            padding=(22, 11),
            font=("Segoe UI Semibold", 10),
            borderwidth=0,
        )
        style.map(
            "Friday.TNotebook.Tab",
            background=[("selected", self.PANEL_RAISED)],
            foreground=[("selected", self.ACCENT)],
        )
        style.configure(
            "Friday.Horizontal.TProgressbar",
            troughcolor=self.INPUT_BG,
            background=self.ACCENT,
            bordercolor=self.BORDER,
            lightcolor=self.ACCENT,
            darkcolor=self.ACCENT,
            thickness=8,
        )
        self.root.option_add("*TCombobox*Listbox.background", self.INPUT_BG)
        self.root.option_add("*TCombobox*Listbox.foreground", self.TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", self.BUTTON)
        self.root.option_add("*TCombobox*Listbox.selectForeground", self.ACCENT)

    def _build_interface(self) -> None:
        self._build_header()
        self._build_audio_controls()
        self._build_chat_display()
        self._build_input_panel()
        self._build_status_bar()

        self.message_entry.focus_set()

    def _build_header(self) -> None:
        header = tk.Frame(
            self.root,
            bg=self.PANEL,
            height=92,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )

        header.pack(
            fill=tk.X,
            padx=16,
            pady=(16, 8),
        )

        header.pack_propagate(False)

        core = tk.Canvas(
            header, width=66, height=66, bg=self.PANEL,
            highlightthickness=0,
        )
        core.pack(side=tk.LEFT, padx=(15, 4))
        core.create_oval(7, 7, 59, 59, outline=self.BORDER, width=2)
        core.create_arc(
            12, 12, 54, 54, start=25, extent=118,
            outline=self.FRIDAY_ACCENT, width=3, style=tk.ARC,
        )
        core.create_arc(
            12, 12, 54, 54, start=205, extent=118,
            outline=self.ACCENT, width=3, style=tk.ARC,
        )
        core.create_oval(24, 24, 42, 42, fill=self.ACCENT, outline="")
        core.create_oval(29, 29, 37, 37, fill="#DFFFFF", outline="")

        identity = tk.Frame(header, bg=self.PANEL)
        identity.pack(side=tk.LEFT, padx=(8, 18), pady=13)
        tk.Label(
            identity, text="F.R.I.D.A.Y.", bg=self.PANEL, fg=self.TEXT,
            font=("Segoe UI Semibold", 22),
        ).pack(anchor="w")
        status_row = tk.Frame(identity, bg=self.PANEL)
        status_row.pack(anchor="w")
        tk.Label(
            status_row, text="●", bg=self.PANEL, fg=self.SUCCESS,
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(
            status_row, textvariable=self.status_text, bg=self.PANEL,
            fg=self.MUTED, font=("Consolas", 9),
        ).pack(side=tk.LEFT)

        new_button = self._make_button(
            header,
            "New Chat",
            self._new_chat,
        )

        new_button.pack(
            side=tk.RIGHT,
            padx=(4, 12),
            pady=25,
        )

        settings_button = self._make_button(
            header,
            "Settings",
            self._open_settings_panel,
        )
        settings_button.pack(
            side=tk.RIGHT,
            padx=4,
            pady=25,
        )

        save_button = self._make_button(
            header,
            "Save",
            self._save_session,
        )

        save_button.pack(
            side=tk.RIGHT,
            padx=4,
            pady=25,
        )

        reindex_button = self._make_button(
            header,
            "Reindex",
            self._reindex,
        )

        reindex_button.pack(
            side=tk.RIGHT,
            padx=4,
            pady=25,
        )

        test_voice_button = self._make_button(
            header,
            "Test Voice",
            self._test_voice,
        )

        test_voice_button.pack(
            side=tk.RIGHT,
            padx=4,
            pady=25,
        )

        voice_check = tk.Checkbutton(
            header,
            text="Speak replies",
            variable=self.voice_enabled,
            command=self._toggle_speak_replies,
            bg=self.PANEL,
            fg=self.TEXT,
            activebackground=self.PANEL,
            activeforeground=self.TEXT,
            selectcolor=self.INPUT_BG,
            font=("Segoe UI Semibold", 9),
        )

        voice_check.pack(
            side=tk.RIGHT,
            padx=10,
        )

    def _open_settings_panel(self) -> None:
        existing = getattr(self, "settings_window", None)

        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return

        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Friday Settings and Diagnostics")
        self.settings_window.geometry("820x640")
        self.settings_window.minsize(700, 520)
        self.settings_window.configure(bg=self.BG)

        notebook = ttk.Notebook(
            self.settings_window,
            style="Friday.TNotebook",
        )
        notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        settings_tab = tk.Frame(notebook, bg=self.PANEL)
        diagnostics_tab = tk.Frame(notebook, bg=self.PANEL)
        actions_tab = tk.Frame(notebook, bg=self.PANEL)
        notebook.add(settings_tab, text="Settings")
        notebook.add(actions_tab, text="Action Center")
        notebook.add(diagnostics_tab, text="Diagnostics")

        self._build_settings_tab(settings_tab)
        self._build_diagnostics_tab(diagnostics_tab)
        self._build_action_center_tab(actions_tab)
        self._refresh_audio_devices()
        self._refresh_diagnostics()

    def _build_settings_tab(self, parent: tk.Frame) -> None:
        parent.columnconfigure(1, weight=1)

        rows = (
            ("Microphone", self.input_device_text),
            ("Speakers", self.output_device_text),
            ("Friday voice", self.voice_text),
        )

        for row, (label_text, variable) in enumerate(rows):
            tk.Label(
                parent,
                text=label_text,
                bg=self.PANEL,
                fg=self.TEXT,
                font=("Segoe UI", 10, "bold"),
            ).grid(
                row=row,
                column=0,
                padx=(18, 10),
                pady=(18 if row == 0 else 8, 8),
                sticky="w",
            )

            values = (
                list(self.input_device_by_label)
                if row == 0
                else list(self.output_device_by_label)
                if row == 1
                else [
                    voice.title()
                    for voice in self.voice_service.available_voices
                ]
            )
            combo = ttk.Combobox(
                parent,
                textvariable=variable,
                values=values,
                state="readonly",
                width=58,
                style="Friday.TCombobox",
            )
            combo.grid(
                row=row,
                column=1,
                columnspan=3,
                padx=(0, 18),
                pady=(18 if row == 0 else 8, 8),
                sticky="ew",
            )

            if row == 0:
                self.settings_input_combo = combo
                combo.bind(
                    "<<ComboboxSelected>>",
                    self._on_input_device_selected,
                )
            elif row == 1:
                self.settings_output_combo = combo
                combo.bind(
                    "<<ComboboxSelected>>",
                    self._on_output_device_selected,
                )
            else:
                combo.bind(
                    "<<ComboboxSelected>>",
                    self._on_voice_selected,
                )

        tk.Checkbutton(
            parent,
            text="Speak Friday's replies",
            variable=self.voice_enabled,
            command=self._toggle_speak_replies,
            bg=self.PANEL,
            fg=self.TEXT,
            activebackground=self.PANEL,
            activeforeground=self.TEXT,
            selectcolor=self.INPUT_BG,
            font=("Segoe UI", 10),
        ).grid(
            row=3,
            column=1,
            padx=(0, 18),
            pady=12,
            sticky="w",
        )

        controls = tk.Frame(parent, bg=self.PANEL)
        controls.grid(
            row=4,
            column=0,
            columnspan=4,
            padx=18,
            pady=16,
            sticky="w",
        )

        for text, command in (
            ("Refresh Devices", self._refresh_audio_devices),
            ("Test Microphone", self._test_microphone),
            ("Test Output", self._test_output_device),
            ("Test Voice", self._test_voice),
        ):
            button = self._make_button(controls, text, command)
            button.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(
            parent,
            text=(
                "These choices are saved locally for the next startup. "
                "Batch action approval is intentionally not remembered."
            ),
            bg=self.PANEL,
            fg=self.MUTED,
            wraplength=700,
            justify=tk.LEFT,
            font=("Segoe UI", 9),
        ).grid(
            row=5,
            column=0,
            columnspan=4,
            padx=18,
            pady=(8, 10),
            sticky="w",
        )

        gmail_panel = tk.Frame(
            parent,
            bg=self.PANEL_RAISED,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        gmail_panel.grid(
            row=6,
            column=0,
            columnspan=4,
            padx=18,
            pady=(6, 18),
            sticky="ew",
        )
        gmail_panel.columnconfigure(1, weight=1)
        tk.Label(
            gmail_panel,
            text="GMAIL LINK",
            bg=self.PANEL_RAISED,
            fg=self.ACCENT,
            font=("Consolas", 10, "bold"),
        ).grid(row=0, column=0, padx=(14, 12), pady=(12, 2), sticky="w")
        tk.Label(
            gmail_panel,
            textvariable=self.gmail_status_text,
            bg=self.PANEL_RAISED,
            fg=self.MUTED,
            font=("Segoe UI", 9),
        ).grid(row=0, column=1, padx=8, pady=(12, 2), sticky="w")
        self.gmail_connect_button = self._make_button(
            gmail_panel,
            "Connect Gmail",
            self._connect_gmail,
        )
        self.gmail_connect_button.grid(
            row=0,
            column=2,
            rowspan=2,
            padx=14,
            pady=12,
        )
        tk.Label(
            gmail_panel,
            text=(
                "Search, summaries, sending, replies, and reversible mailbox "
                "management. Delete always means move to Trash."
            ),
            bg=self.PANEL_RAISED,
            fg=self.MUTED,
            font=("Segoe UI", 9),
            wraplength=540,
            justify=tk.LEFT,
        ).grid(row=1, column=0, columnspan=2, padx=14, pady=(2, 12), sticky="w")

    def _build_diagnostics_tab(self, parent: tk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(9, weight=1)
        self.diagnostic_values: dict[str, tk.StringVar] = {}

        diagnostic_rows = (
            ("OpenAI", "api"),
            ("Gmail", "gmail"),
            ("Chat model", "model"),
            ("Obsidian vault", "vault"),
            ("Microphone", "input"),
            ("Speakers", "output"),
            ("TTS", "tts"),
            ("Voice state", "state"),
        )

        for row, (label_text, key) in enumerate(diagnostic_rows):
            tk.Label(
                parent,
                text=label_text,
                bg=self.PANEL,
                fg=self.TEXT,
                font=("Segoe UI", 9, "bold"),
            ).grid(
                row=row,
                column=0,
                padx=(18, 10),
                pady=(14 if row == 0 else 4, 4),
                sticky="nw",
            )
            value = tk.StringVar(master=self.settings_window)
            self.diagnostic_values[key] = value
            tk.Label(
                parent,
                textvariable=value,
                bg=self.PANEL,
                fg=self.MUTED,
                anchor=tk.W,
                justify=tk.LEFT,
                wraplength=610,
                font=("Segoe UI", 9),
            ).grid(
                row=row,
                column=1,
                padx=(0, 18),
                pady=(14 if row == 0 else 4, 4),
                sticky="ew",
            )

        meter_frame = tk.Frame(parent, bg=self.PANEL)
        meter_frame.grid(
            row=8,
            column=0,
            columnspan=2,
            padx=18,
            pady=10,
            sticky="ew",
        )
        tk.Label(
            meter_frame,
            text="Microphone level",
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 10))
        self.microphone_meter = ttk.Progressbar(
            meter_frame,
            maximum=100,
            mode="determinate",
            style="Friday.Horizontal.TProgressbar",
        )
        self.microphone_meter.pack(side=tk.LEFT, fill=tk.X, expand=True)

        log_frame = tk.Frame(parent, bg=self.PANEL)
        log_frame.grid(
            row=9,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 10),
            sticky="nsew",
        )
        log_frame.rowconfigure(1, weight=1)
        log_frame.columnconfigure(0, weight=1)
        tk.Label(
            log_frame,
            text="Recent diagnostics",
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Segoe UI", 9, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.diagnostic_log = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            bg=self.INPUT_BG,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            font=("Consolas", 9),
            state=tk.DISABLED,
        )
        self.diagnostic_log.grid(row=1, column=0, sticky="nsew")

        refresh = self._make_button(
            parent,
            "Refresh Diagnostics",
            self._refresh_diagnostics,
        )
        refresh.grid(
            row=10,
            column=0,
            columnspan=2,
            padx=18,
            pady=(0, 14),
            sticky="w",
        )

    def _build_audio_controls(self) -> None:
        panel = tk.Frame(
            self.root,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        panel.pack(
            fill=tk.X,
            padx=16,
            pady=(0, 8),
        )

        tk.Label(
            panel,
            text="Microphone",
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Segoe UI", 9, "bold"),
        ).grid(row=0, column=0, padx=(12, 6), pady=10)

        self.input_device_combo = ttk.Combobox(
            panel,
            textvariable=self.input_device_text,
            state="readonly",
            width=38,
            style="Friday.TCombobox",
        )
        self.input_device_combo.grid(
            row=0,
            column=1,
            padx=(0, 14),
            pady=10,
            sticky="ew",
        )
        self.input_device_combo.bind(
            "<<ComboboxSelected>>",
            self._on_input_device_selected,
        )

        tk.Label(
            panel,
            text="Speakers",
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Segoe UI", 9, "bold"),
        ).grid(row=0, column=2, padx=(0, 6), pady=10)

        self.output_device_combo = ttk.Combobox(
            panel,
            textvariable=self.output_device_text,
            state="readonly",
            width=38,
            style="Friday.TCombobox",
        )
        self.output_device_combo.grid(
            row=0,
            column=3,
            padx=(0, 8),
            pady=10,
            sticky="ew",
        )
        self.output_device_combo.bind(
            "<<ComboboxSelected>>",
            self._on_output_device_selected,
        )

        refresh_button = self._make_button(
            panel,
            "Refresh",
            self._refresh_audio_devices,
        )
        refresh_button.grid(row=0, column=4, padx=4, pady=8)

        test_button = self._make_button(
            panel,
            "Test Output",
            self._test_output_device,
        )
        test_button.grid(row=0, column=5, padx=(4, 12), pady=8)

        tk.Label(
            panel,
            text="Friday voice",
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Segoe UI", 9, "bold"),
        ).grid(row=1, column=0, padx=(12, 6), pady=(0, 10))

        self.voice_combo = ttk.Combobox(
            panel,
            textvariable=self.voice_text,
            values=[
                voice.title()
                for voice in self.voice_service.available_voices
            ],
            state="readonly",
            width=20,
            style="Friday.TCombobox",
        )
        self.voice_combo.grid(
            row=1,
            column=1,
            padx=(0, 14),
            pady=(0, 10),
            sticky="w",
        )
        self.voice_combo.bind(
            "<<ComboboxSelected>>",
            self._on_voice_selected,
        )

        tk.Label(
            panel,
            text="Choose a voice, then click Test Voice to preview it.",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 9),
        ).grid(
            row=1,
            column=2,
            columnspan=4,
            padx=(0, 12),
            pady=(0, 10),
            sticky="w",
        )

        panel.columnconfigure(1, weight=1)
        panel.columnconfigure(3, weight=1)
        self._refresh_audio_devices()

    def _refresh_audio_devices(self) -> None:
        try:
            input_devices = self.voice_service.list_input_devices()
            output_devices = self.voice_service.list_output_devices()
        except Exception as exc:
            messagebox.showerror("Audio Device Error", str(exc))
            return

        self.input_device_by_label = {
            device.label: device.index
            for device in input_devices
        }
        self.output_device_by_label = {
            device.label: device.index
            for device in output_devices
        }

        input_labels = list(self.input_device_by_label)
        output_labels = list(self.output_device_by_label)
        self.input_device_combo.configure(values=input_labels)
        self.output_device_combo.configure(values=output_labels)

        settings_window = getattr(self, "settings_window", None)
        if (
            settings_window is not None
            and settings_window.winfo_exists()
            and hasattr(self, "settings_input_combo")
        ):
            self.settings_input_combo.configure(values=input_labels)
            self.settings_output_combo.configure(values=output_labels)

        self._select_current_device(
            input_labels,
            self.input_device_by_label,
            self.voice_service.input_device,
            self.input_device_text,
            self.voice_service.set_input_device,
            self.preferences.input_device_label,
        )
        self._select_current_device(
            output_labels,
            self.output_device_by_label,
            self.voice_service.output_device,
            self.output_device_text,
            self.voice_service.set_output_device,
            self.preferences.output_device_label,
        )

        if not input_labels:
            self.input_device_text.set("No input devices found")
        if not output_labels:
            self.output_device_text.set("No output devices found")

    @staticmethod
    def _select_current_device(
        labels: list[str],
        device_map: dict[str, int],
        current_index: int | None,
        target: tk.StringVar,
        setter,
        preferred_label: str,
    ) -> None:
        preferred_match = next(
            (
                label
                for label in labels
                if FridayGUI._device_identity(label)
                == FridayGUI._device_identity(preferred_label)
            ),
            "",
        )
        selected = (
            preferred_match
            if preferred_match
            else next(
                (
                    label
                    for label, index in device_map.items()
                    if index == current_index
                ),
                labels[0] if labels else "",
            )
        )
        target.set(selected)

        if selected and device_map[selected] != current_index:
            setter(device_map[selected])

    @staticmethod
    def _device_identity(label: str) -> str:
        return label.split("] ", 1)[-1].casefold().strip()

    def _on_input_device_selected(self, _event=None) -> None:
        label = self.input_device_text.get()
        device_index = self.input_device_by_label.get(label)

        if device_index is None:
            return

        try:
            self.voice_service.set_input_device(device_index)
            self.status_text.set(f"Microphone selected: {label}")
            self._save_preferences()
        except Exception as exc:
            messagebox.showerror("Microphone Error", str(exc))
            self._refresh_audio_devices()

    def _on_output_device_selected(self, _event=None) -> None:
        label = self.output_device_text.get()
        device_index = self.output_device_by_label.get(label)

        if device_index is None:
            return

        try:
            self.voice_service.set_output_device(device_index)
            self.status_text.set(f"Speakers selected: {label}")
            self._save_preferences()
        except Exception as exc:
            messagebox.showerror("Speaker Error", str(exc))
            self._refresh_audio_devices()

    def _on_voice_selected(self, _event=None) -> None:
        selected_voice = self.voice_text.get().casefold()

        try:
            self.voice_service.set_voice(selected_voice)
            self.status_text.set(
                f"Friday voice selected: {selected_voice.title()}"
            )
            self._save_preferences()
        except Exception as exc:
            messagebox.showerror("Friday Voice Error", str(exc))
            self.voice_text.set(self.voice_service.voice.title())

    def _test_output_device(self) -> None:
        self.status_text.set("Testing selected output device...")
        threading.Thread(
            target=self._test_output_worker,
            daemon=True,
        ).start()

    def _test_output_worker(self) -> None:
        try:
            self.voice_service.test_speaker()
            self.root.after(
                0,
                lambda: self.status_text.set(
                    "Output device test completed"
                ),
            )
        except Exception as exc:
            error = str(exc)
            self.voice_service.log_diagnostic(
                f"Speaker test failed: {error}"
            )
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Speaker Test Error",
                    error,
                ),
            )

    def _test_microphone(self) -> None:
        self.status_text.set("Testing selected microphone...")
        threading.Thread(
            target=self._test_microphone_worker,
            daemon=True,
        ).start()

    def _test_microphone_worker(self) -> None:
        try:
            level = self.voice_service.test_microphone()
            self.root.after(
                0,
                lambda: self.status_text.set(
                    f"Microphone peak level: {level:.0%}"
                ),
            )
        except Exception as exc:
            error = str(exc)
            self.voice_service.log_diagnostic(
                f"Microphone test failed: {error}"
            )
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Microphone Test Error",
                    error,
                ),
            )

    def _connect_gmail(self) -> None:
        self.gmail_status_text.set("Waiting for Google sign-in...")
        self.gmail_connect_button.configure(state=tk.DISABLED)
        self.status_text.set("Connecting Gmail in your browser...")
        threading.Thread(
            target=self._connect_gmail_worker,
            daemon=True,
        ).start()

    def _connect_gmail_worker(self) -> None:
        try:
            status = self.gmail_tools.connect()
            self.root.after(
                0,
                lambda: self._gmail_connection_finished(status.message),
            )
        except Exception as exc:
            error = str(exc)
            self.root.after(
                0,
                lambda: self._gmail_connection_failed(error),
            )

    def _gmail_connection_finished(self, message: str) -> None:
        self.gmail_status_text.set(message)
        self.gmail_connect_button.configure(
            text="Reconnect Gmail",
            state=tk.NORMAL,
        )
        self.status_text.set("Gmail connected with send and manage access")
        self.voice_service.log_diagnostic("Gmail connected (send and manage)")
        self._refresh_diagnostics()

    def _build_action_center_tab(self, parent: tk.Frame) -> None:
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)
        tk.Label(
            parent, text="PENDING ACTIONS", bg=self.PANEL, fg=self.ACCENT,
            font=("Consolas", 11, "bold"),
        ).grid(row=0, column=0, padx=18, pady=(18, 8), sticky="w")
        self.action_tree = ttk.Treeview(
            parent,
            columns=("title", "due", "source"),
            show="headings",
        )
        for key, title, width in (
            ("title", "Action", 430), ("due", "Due", 170), ("source", "Source", 100)
        ):
            self.action_tree.heading(key, text=title)
            self.action_tree.column(key, width=width, anchor="w")
        self.action_tree.grid(row=1, column=0, padx=18, pady=8, sticky="nsew")
        controls = tk.Frame(parent, bg=self.PANEL)
        controls.grid(row=2, column=0, padx=18, pady=(4, 18), sticky="w")
        for text, command in (
            ("Refresh", self._refresh_action_center),
            ("Complete", lambda: self._update_selected_action("complete")),
            ("Dismiss", lambda: self._update_selected_action("dismiss")),
        ):
            self._make_button(controls, text, command).pack(side=tk.LEFT, padx=(0, 8))
        self._refresh_action_center()

    def _refresh_action_center(self) -> None:
        if not hasattr(self, "action_tree"):
            return
        for item in self.action_tree.get_children():
            self.action_tree.delete(item)
        for action in self.action_center.list_actions():
            self.action_tree.insert(
                "", tk.END, iid=str(action["id"]),
                values=(action["title"], action["due_at"], action["source"]),
            )

    def _update_selected_action(self, operation: str) -> None:
        selection = self.action_tree.selection()
        if not selection:
            messagebox.showinfo("Action Center", "Select an action first.")
            return
        action_id = int(selection[0])
        if operation == "complete":
            self.action_center.complete_action(action_id)
        else:
            self.action_center.dismiss_action(action_id)
        self._refresh_action_center()

    def _gmail_connection_failed(self, error: str) -> None:
        self.gmail_status_text.set("Connection failed")
        self.gmail_connect_button.configure(state=tk.NORMAL)
        self.status_text.set("Gmail connection failed")
        self.voice_service.log_diagnostic(
            f"Gmail connection failed: {error}"
        )
        messagebox.showerror("Gmail Connection Error", error)

    def _refresh_diagnostics(self) -> None:
        window = getattr(self, "settings_window", None)

        if window is None or not window.winfo_exists():
            return

        settings = self.friday.settings
        vault_path = self.memory_manager.vault.vault_path
        gmail_status = self.gmail_tools.get_status()
        self.gmail_status_text.set(gmail_status.message)
        if hasattr(self, "gmail_connect_button"):
            self.gmail_connect_button.configure(
                text="Reconnect Gmail" if gmail_status.connected else "Connect Gmail"
            )
        values = {
            "api": "Configured" if settings.openai_api_key else "Missing API key",
            "gmail": gmail_status.message,
            "model": settings.openai_model,
            "vault": (
                f"Ready: {vault_path}"
                if vault_path.exists()
                else f"Not found: {vault_path}"
            ),
            "input": self.input_device_text.get(),
            "output": self.output_device_text.get(),
            "tts": (
                f"{self.voice_service.tts_model} / "
                f"{self.voice_service.voice.title()}"
            ),
            "state": (
                "Recording"
                if self.voice_service.is_recording
                else "Speaking"
                if self.voice_service.is_speaking
                else "Idle"
            ),
        }

        for key, value in values.items():
            self.diagnostic_values[key].set(value)

        self.diagnostic_log.configure(state=tk.NORMAL)
        self.diagnostic_log.delete("1.0", tk.END)
        self.diagnostic_log.insert(
            "1.0",
            "\n".join(self.voice_service.get_diagnostic_messages()),
        )
        self.diagnostic_log.configure(state=tk.DISABLED)
        self.diagnostic_log.see(tk.END)

    def _update_diagnostics_loop(self) -> None:
        window = getattr(self, "settings_window", None)

        if window is not None and window.winfo_exists():
            self.microphone_meter["value"] = (
                self.voice_service.microphone_level * 100
            )
            self._refresh_diagnostics()

        self.root.after(500, self._update_diagnostics_loop)

    def _save_preferences(self) -> None:
        self.preferences = UserPreferences(
            voice=self.voice_service.voice,
            input_device_label=self.input_device_text.get(),
            output_device_label=self.output_device_text.get(),
            speak_replies=bool(self.voice_enabled.get()),
        )

        try:
            self.preference_store.save(self.preferences)
        except OSError as exc:
            self.voice_service.log_diagnostic(
                f"Could not save preferences: {exc}"
            )

    def _toggle_speak_replies(self) -> None:
        self.speak_replies_enabled = bool(
            self.voice_enabled.get()
        )
        self._save_preferences()

        if self.speak_replies_enabled:
            self.status_text.set(
                "Spoken replies enabled"
            )
        else:
            self.voice_service.stop_speaking()

            self.status_text.set(
                "Spoken replies disabled"
            )

    def _build_chat_display(self) -> None:
        chat_shell = tk.Frame(
            self.root,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )
        chat_shell.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        chat_header = tk.Frame(chat_shell, bg=self.PANEL_RAISED, height=36)
        chat_header.pack(fill=tk.X)
        chat_header.pack_propagate(False)
        tk.Label(
            chat_header, text="  ◈  NEURAL LINK / ACTIVE SESSION",
            bg=self.PANEL_RAISED, fg=self.ACCENT,
            font=("Consolas", 9, "bold"),
        ).pack(side=tk.LEFT, padx=10, pady=8)
        tk.Label(
            chat_header, text="ENCRYPTED  •  MEMORY ONLINE  ",
            bg=self.PANEL_RAISED, fg=self.MUTED,
            font=("Consolas", 8),
        ).pack(side=tk.RIGHT, padx=10)

        self.chat_display = scrolledtext.ScrolledText(
            chat_shell,
            wrap=tk.WORD,
            bg=self.INPUT_BG,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            selectbackground=self.ACCENT,
            relief=tk.FLAT,
            borderwidth=0,
            font=("Segoe UI", 11),
            padx=24,
            pady=20,
            state=tk.DISABLED,
        )

        self.chat_display.pack(
            fill=tk.BOTH,
            expand=True,
            padx=0,
            pady=0,
        )

        self.chat_display.tag_configure(
            "user_name",
            foreground=self.ACCENT,
            font=("Consolas", 10, "bold"),
            spacing1=6,
            spacing3=4,
        )

        self.chat_display.tag_configure(
            "friday_name",
            foreground=self.FRIDAY_ACCENT,
            font=("Consolas", 10, "bold"),
            spacing1=6,
            spacing3=4,
        )

        self.chat_display.tag_configure(
            "message",
            foreground=self.TEXT,
            lmargin1=10,
            lmargin2=10,
            spacing3=18,
        )

    def _build_input_panel(self) -> None:
        input_panel = tk.Frame(
            self.root,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )

        input_panel.pack(
            fill=tk.X,
            padx=16,
            pady=(6, 8),
        )

        self.message_entry = tk.Text(
            input_panel,
            height=3,
            wrap=tk.WORD,
            bg=self.INPUT_BG,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            relief=tk.FLAT,
            borderwidth=0,
            font=("Segoe UI", 11),
            padx=15,
            pady=12,
            highlightbackground=self.BORDER,
            highlightcolor=self.ACCENT,
            highlightthickness=1,
        )

        self.message_entry.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True,
            padx=(10, 6),
            pady=10,
        )

        self.message_entry.bind(
            "<Return>",
            self._handle_enter,
        )

        button_panel = tk.Frame(
            input_panel,
            bg=self.PANEL,
        )

        button_panel.pack(
            side=tk.RIGHT,
            padx=(4, 10),
            pady=10,
        )

        self.talk_button = tk.Button(
            button_panel,
            text="◉  VOICE LINK",
            command=self._toggle_recording,
            bg=self.BUTTON,
            fg=self.TEXT,
            activebackground=self.ACCENT,
            activeforeground=self.BG,
            disabledforeground=self.MUTED,
            relief=tk.FLAT,
            width=15,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
        )

        self.talk_button.pack(
            fill=tk.X,
            pady=(0, 6),
        )

        self.send_button = tk.Button(
            button_panel,
            text="TRANSMIT  ›",
            command=self._send_typed_message,
            bg=self.ACCENT,
            fg=self.BG,
            activebackground=self.ACCENT_BRIGHT,
            activeforeground=self.BG,
            disabledforeground=self.MUTED,
            relief=tk.FLAT,
            width=15,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
        )

        self.send_button.pack(fill=tk.X)

    def _build_status_bar(self) -> None:
        status_bar = tk.Label(
            self.root,
            text=(
                "SYSTEM READY   |   ENTER TO TRANSMIT   |   "
                "SHIFT+ENTER FOR NEW LINE   |   VOICE LINK AVAILABLE"
            ),
            bg=self.BG,
            fg=self.MUTED,
            anchor=tk.W,
            font=("Consolas", 8),
        )

        status_bar.pack(
            fill=tk.X,
            padx=20,
            pady=(2, 12),
        )

    def _make_button(
        self,
        parent: tk.Widget,
        text: str,
        command,
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=self.BUTTON,
            fg=self.TEXT,
            activebackground=self.ACCENT,
            activeforeground=self.BG,
            relief=tk.FLAT,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
            padx=12,
            pady=4,
            highlightbackground=self.BORDER,
            highlightthickness=1,
        )

    def _handle_enter(self, event) -> str | None:
        shift_pressed = bool(event.state & 0x0001)

        if shift_pressed:
            return None

        self._send_typed_message()
        return "break"

    def _send_typed_message(self) -> None:
        text = self.message_entry.get(
            "1.0",
            tk.END,
        ).strip()

        if not text:
            return

        self.message_entry.delete(
            "1.0",
            tk.END,
        )

        self._submit_message(text)

    def _submit_message(self, text: str) -> None:
        self._append_message(
            "Brad",
            text,
            "user_name",
        )

        self._set_busy(True)
        self.status_text.set("Friday is thinking...")

        threading.Thread(
            target=self._process_message,
            args=(text,),
            daemon=True,
        ).start()

    def _process_message(self, text: str) -> None:
        try:
            response = self.friday.chat(text)

            self.root.after(
                0,
                lambda: self._show_response(
                    text,
                    response,
                ),
            )

        except Exception as exc:
            error_message = str(exc)

            self.root.after(
                0,
                lambda: self._show_error(
                    error_message
                ),
            )

    def _show_response(
        self,
        user_message: str,
        response: str,
    ) -> None:
        self._append_message(
            "Friday",
            response,
            "friday_name",
        )

        self._set_busy(False)
        self.status_text.set("Friday is online")

        if self.speak_replies_enabled:
            self._speak_response(response)

        threading.Thread(
            target=self._check_memory_proposal,
            args=(user_message, response),
            daemon=True,
        ).start()

    def _speak_response(self, response: str) -> None:
        self.status_text.set("Friday is speaking...")

        try:
            self.voice_service.speak(
                response,
                on_finished=lambda: self.root.after(
                    0,
                    self._speech_finished,
                ),
            )

        except Exception as exc:
            self.status_text.set("Voice playback failed")

            messagebox.showerror(
                "Friday Voice Error",
                str(exc),
            )

    def _speech_finished(self) -> None:
        self.status_text.set("Friday is online")

    def _test_voice(self) -> None:
        if self.voice_service.is_recording:
            messagebox.showwarning(
                "Friday Voice",
                "Stop recording before testing the voice.",
            )
            return

        self.status_text.set("Testing Friday's voice...")

        try:
            self.voice_service.speak(
                (
                    "Hello Brad. Friday's voice system "
                    "is online and working."
                ),
                on_finished=lambda: self.root.after(
                    0,
                    self._voice_test_finished,
                ),
            )

        except Exception as exc:
            self.status_text.set("Voice test failed")

            messagebox.showerror(
                "Friday Voice Error",
                str(exc),
            )

    def _voice_test_finished(self) -> None:
        self.status_text.set("Friday is online")

    def _check_memory_proposal(
        self,
        user_message: str,
        response: str,
    ) -> None:
        try:
            proposal = self.friday.propose_memory(
                user_message=user_message,
                assistant_response=response,
            )

        except Exception:
            return

        if proposal is None:
            return

        self.root.after(
            0,
            lambda: self._request_memory_approval(
                proposal
            ),
        )

    def _request_memory_approval(
        self,
        proposal,
    ) -> None:
        if not self.friday.batch_actions_approved:
            self.status_text.set(
                "Memory not saved: batch actions were not approved"
            )
            return

        try:
            saved_path = (
                self.memory_manager.save_proposal(
                    proposal
                )
            )

            relative_path = saved_path.relative_to(
                self.memory_manager.vault.vault_path
            )

            self.status_text.set(
                f"Memory saved: {relative_path}"
            )

        except Exception as exc:
            messagebox.showerror(
                "Memory Error",
                str(exc),
            )

    def _toggle_recording(self) -> None:
        if self.voice_service.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        try:
            self.voice_service.stop_speaking()
            self.voice_service.start_recording()

            self.talk_button.configure(
                text="STOP CAPTURE",
                bg=self.RECORDING,
            )

            self.status_text.set("Listening...")

        except Exception as exc:
            self.talk_button.configure(
                text="◉  VOICE LINK",
                bg=self.BUTTON,
            )

            messagebox.showerror(
                "Microphone Error",
                str(exc),
            )

    def _stop_recording(self) -> None:
        self.talk_button.configure(
            text="DECODING...",
            state=tk.DISABLED,
            bg=self.BUTTON,
        )

        self.status_text.set(
            "Transcribing your voice..."
        )

        threading.Thread(
            target=self._transcribe_recording,
            daemon=True,
        ).start()

    def _transcribe_recording(self) -> None:
        try:
            transcript = (
                self.voice_service
                .stop_recording_and_transcribe()
            )

            self.root.after(
                0,
                lambda: self._handle_transcript(
                    transcript
                ),
            )

        except Exception as exc:
            error_message = str(exc)

            self.root.after(
                0,
                lambda: self._show_microphone_error(
                    error_message
                ),
            )

    def _handle_transcript(
        self,
        transcript: str,
    ) -> None:
        self.talk_button.configure(
            text="◉  VOICE LINK",
            state=tk.NORMAL,
            bg=self.BUTTON,
        )

        if not transcript:
            self.status_text.set(
                "No speech was detected"
            )
            return

        self.message_entry.delete(
            "1.0",
            tk.END,
        )

        self.message_entry.insert(
            "1.0",
            transcript,
        )

        self.status_text.set("Speech transcribed")
        self._send_typed_message()

    def _show_microphone_error(
        self,
        error: str,
    ) -> None:
        self.talk_button.configure(
            text="◉  VOICE LINK",
            state=tk.NORMAL,
            bg=self.BUTTON,
        )

        self.status_text.set("Microphone error")

        messagebox.showerror(
            "Voice Error",
            error,
        )

    def _append_message(
        self,
        speaker: str,
        message: str,
        name_tag: str,
    ) -> None:
        self.chat_display.configure(
            state=tk.NORMAL
        )

        self.chat_display.insert(
            tk.END,
            f"{speaker}\n",
            name_tag,
        )

        self.chat_display.insert(
            tk.END,
            f"{message}\n\n",
            "message",
        )

        self.chat_display.configure(
            state=tk.DISABLED
        )

        self.chat_display.see(tk.END)

    def _set_busy(self, busy: bool) -> None:
        state = (
            tk.DISABLED
            if busy
            else tk.NORMAL
        )

        self.send_button.configure(state=state)
        self.message_entry.configure(state=state)

        if not self.voice_service.is_recording:
            self.talk_button.configure(state=state)

        if not busy:
            self.message_entry.focus_set()

    def _load_existing_conversation(self) -> None:
        messages = (
            self.conversation_manager
            .current_session
            .messages
        )

        for message in messages:
            role = message.get("role")
            content = message.get("content", "")

            if role == "user":
                self._append_message(
                    "Brad",
                    content,
                    "user_name",
                )

            elif role == "assistant":
                self._append_message(
                    "Friday",
                    content,
                    "friday_name",
                )

    def _new_chat(self) -> None:
        approved = messagebox.askyesno(
            "New Conversation",
            "Save the current conversation and start a new one?",
        )

        if not approved:
            return

        try:
            self.conversation_manager.save_current_session()
            self.friday.start_new_session()

            self.chat_display.configure(
                state=tk.NORMAL
            )

            self.chat_display.delete(
                "1.0",
                tk.END,
            )

            self.chat_display.configure(
                state=tk.DISABLED
            )

            self.status_text.set(
                "New conversation started"
            )

            self.message_entry.focus_set()

        except Exception as exc:
            messagebox.showerror(
                "New Conversation Error",
                str(exc),
            )

    def _save_session(self) -> None:
        try:
            path = (
                self.conversation_manager
                .save_current_session()
            )

            self.status_text.set(
                f"Conversation saved: {path.name}"
            )

        except Exception as exc:
            messagebox.showerror(
                "Save Error",
                str(exc),
            )

    def _reindex(self) -> None:
        self.status_text.set(
            "Reindexing Obsidian..."
        )

        threading.Thread(
            target=self._reindex_worker,
            daemon=True,
        ).start()

    def _reindex_worker(self) -> None:
        try:
            count = self.memory_manager.rebuild_index()

            self.root.after(
                0,
                lambda: self.status_text.set(
                    f"Indexed {count} Obsidian notes"
                ),
            )

        except Exception as exc:
            error_message = str(exc)

            self.root.after(
                0,
                lambda: self._show_reindex_error(
                    error_message
                ),
            )

    def _show_reindex_error(
        self,
        error: str,
    ) -> None:
        self.status_text.set("Reindex failed")
        self.voice_service.log_diagnostic(
            f"Obsidian reindex failed: {error}"
        )

        messagebox.showerror(
            "Index Error",
            error,
        )

    def _show_error(self, error: str) -> None:
        self._set_busy(False)
        self.voice_service.log_diagnostic(
            f"Friday request failed: {error}"
        )
        self.status_text.set(
            "Friday encountered an error"
        )

        messagebox.showerror(
            "Friday Error",
            error,
        )

    def _initialize_voice_setting(self) -> None:
        self.voice_enabled.set(self.preferences.speak_replies)
        self.speak_replies_enabled = self.preferences.speak_replies

    def _request_batch_action_approval(self) -> None:
        approved = messagebox.askyesno(
            "Friday Batch Approval",
            (
                "Allow Friday to perform protected actions for this "
                "app session?\n\n"
                "This batch approval covers creating, updating, moving, "
                "renaming, merging, archiving, and deleting Obsidian "
                "notes and folders, including approved memory saves. It also "
                "covers creating drafts, sending or replying to email, and "
                "changing Gmail read, archive, or Trash state.\n\n"
                "Friday will continue to run read-only actions either way. "
                "Choose No to block all protected actions for this session."
            ),
        )

        self.friday.set_batch_actions_approved(approved)

        if approved:
            self.status_text.set(
                "Batch actions approved for this session"
            )
        else:
            self.status_text.set(
                "Protected actions blocked for this session"
            )

    def _on_close(self) -> None:
        try:
            self._save_preferences()
            self.voice_service.stop_speaking()

            if self.voice_service.is_recording:
                try:
                    self.voice_service.stop_recording_and_transcribe()
                except Exception:
                    pass

            self.conversation_manager.save_current_session()

        finally:
            self.root.destroy()
