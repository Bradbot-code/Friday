from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from brain.ai import FridayAI
from memory.conversation_manager import ConversationManager
from memory.memory_manager import MemoryManager
from tools.voice import VoiceService


class FridayGUI:
    BG = "#101419"
    PANEL = "#182028"
    INPUT_BG = "#202A34"
    TEXT = "#E8EEF3"
    MUTED = "#8FA1B3"
    ACCENT = "#59C7FF"
    FRIDAY_ACCENT = "#BCA7FF"
    BUTTON = "#263542"
    RECORDING = "#A83232"

    def __init__(
        self,
        root: tk.Tk,
        friday: FridayAI,
        voice_service: VoiceService,
        memory_manager: MemoryManager,
        conversation_manager: ConversationManager,
    ) -> None:
        self.root = root
        self.friday = friday
        self.voice_service = voice_service
        self.memory_manager = memory_manager
        self.conversation_manager = conversation_manager

        self.speak_replies_enabled = True
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
            value=True,
        )
        self.status_text = tk.StringVar(
            master=self.root,
            value="Friday is online",
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

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self._on_close,
        )

    def _configure_window(self) -> None:
        self.root.title("Friday")
        self.root.geometry("1050x790")
        self.root.minsize(760, 560)
        self.root.configure(bg=self.BG)

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
            height=72,
        )

        header.pack(
            fill=tk.X,
            padx=12,
            pady=(12, 6),
        )

        header.pack_propagate(False)

        title = tk.Label(
            header,
            text="FRIDAY",
            bg=self.PANEL,
            fg=self.ACCENT,
            font=("Segoe UI", 21, "bold"),
        )

        title.pack(
            side=tk.LEFT,
            padx=(18, 14),
        )

        subtitle = tk.Label(
            header,
            textvariable=self.status_text,
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Segoe UI", 10),
        )

        subtitle.pack(
            side=tk.LEFT,
            padx=(0, 10),
        )

        new_button = self._make_button(
            header,
            "New Chat",
            self._new_chat,
        )

        new_button.pack(
            side=tk.RIGHT,
            padx=(4, 12),
            pady=16,
        )

        save_button = self._make_button(
            header,
            "Save",
            self._save_session,
        )

        save_button.pack(
            side=tk.RIGHT,
            padx=4,
            pady=16,
        )

        reindex_button = self._make_button(
            header,
            "Reindex",
            self._reindex,
        )

        reindex_button.pack(
            side=tk.RIGHT,
            padx=4,
            pady=16,
        )

        test_voice_button = self._make_button(
            header,
            "Test Voice",
            self._test_voice,
        )

        test_voice_button.pack(
            side=tk.RIGHT,
            padx=4,
            pady=16,
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
            font=("Segoe UI", 10),
        )

        voice_check.pack(
            side=tk.RIGHT,
            padx=12,
        )

        voice_check.select()

    def _build_audio_controls(self) -> None:
        panel = tk.Frame(
            self.root,
            bg=self.PANEL,
        )
        panel.pack(
            fill=tk.X,
            padx=12,
            pady=(0, 6),
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

        self._select_current_device(
            input_labels,
            self.input_device_by_label,
            self.voice_service.input_device,
            self.input_device_text,
            self.voice_service.set_input_device,
        )
        self._select_current_device(
            output_labels,
            self.output_device_by_label,
            self.voice_service.output_device,
            self.output_device_text,
            self.voice_service.set_output_device,
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
    ) -> None:
        selected = next(
            (
                label
                for label, index in device_map.items()
                if index == current_index
            ),
            labels[0] if labels else "",
        )
        target.set(selected)

        if selected and current_index is None:
            setter(device_map[selected])

    def _on_input_device_selected(self, _event=None) -> None:
        label = self.input_device_text.get()
        device_index = self.input_device_by_label.get(label)

        if device_index is None:
            return

        try:
            self.voice_service.set_input_device(device_index)
            self.status_text.set(f"Microphone selected: {label}")
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
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Speaker Test Error",
                    error,
                ),
            )

    def _toggle_speak_replies(self) -> None:
        self.speak_replies_enabled = bool(
            self.voice_enabled.get()
        )

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
        self.chat_display = scrolledtext.ScrolledText(
            self.root,
            wrap=tk.WORD,
            bg=self.BG,
            fg=self.TEXT,
            insertbackground=self.TEXT,
            selectbackground=self.ACCENT,
            relief=tk.FLAT,
            borderwidth=0,
            font=("Segoe UI", 11),
            padx=18,
            pady=18,
            state=tk.DISABLED,
        )

        self.chat_display.pack(
            fill=tk.BOTH,
            expand=True,
            padx=12,
            pady=6,
        )

        self.chat_display.tag_configure(
            "user_name",
            foreground=self.ACCENT,
            font=("Segoe UI", 11, "bold"),
        )

        self.chat_display.tag_configure(
            "friday_name",
            foreground=self.FRIDAY_ACCENT,
            font=("Segoe UI", 11, "bold"),
        )

        self.chat_display.tag_configure(
            "message",
            foreground=self.TEXT,
            spacing3=14,
        )

    def _build_input_panel(self) -> None:
        input_panel = tk.Frame(
            self.root,
            bg=self.PANEL,
        )

        input_panel.pack(
            fill=tk.X,
            padx=12,
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
            padx=12,
            pady=10,
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
            text="Start Talking",
            command=self._toggle_recording,
            bg=self.BUTTON,
            fg=self.TEXT,
            activebackground=self.ACCENT,
            activeforeground=self.BG,
            disabledforeground=self.MUTED,
            relief=tk.FLAT,
            width=15,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        )

        self.talk_button.pack(
            fill=tk.X,
            pady=(0, 6),
        )

        self.send_button = tk.Button(
            button_panel,
            text="Send",
            command=self._send_typed_message,
            bg=self.ACCENT,
            fg=self.BG,
            activebackground="#8DDAFF",
            activeforeground=self.BG,
            disabledforeground=self.MUTED,
            relief=tk.FLAT,
            width=15,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        )

        self.send_button.pack(fill=tk.X)

    def _build_status_bar(self) -> None:
        status_bar = tk.Label(
            self.root,
            text=(
                "Enter sends • Shift+Enter creates a new line • "
                "Start Talking begins recording"
            ),
            bg=self.BG,
            fg=self.MUTED,
            anchor=tk.W,
            font=("Segoe UI", 9),
        )

        status_bar.pack(
            fill=tk.X,
            padx=18,
            pady=(0, 10),
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
            font=("Segoe UI", 9, "bold"),
            padx=10,
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
                text="Stop Recording",
                bg=self.RECORDING,
            )

            self.status_text.set("Listening...")

        except Exception as exc:
            self.talk_button.configure(
                text="Start Talking",
                bg=self.BUTTON,
            )

            messagebox.showerror(
                "Microphone Error",
                str(exc),
            )

    def _stop_recording(self) -> None:
        self.talk_button.configure(
            text="Transcribing...",
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
            text="Start Talking",
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
            text="Start Talking",
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

        messagebox.showerror(
            "Index Error",
            error,
        )

    def _show_error(self, error: str) -> None:
        self._set_busy(False)
        self.status_text.set(
            "Friday encountered an error"
        )

        messagebox.showerror(
            "Friday Error",
            error,
        )

    def _initialize_voice_setting(self) -> None:
        self.voice_enabled.set(True)
        self.speak_replies_enabled = True

    def _request_batch_action_approval(self) -> None:
        approved = messagebox.askyesno(
            "Friday Batch Approval",
            (
                "Allow Friday to perform protected actions for this "
                "app session?\n\n"
                "This batch approval covers creating, updating, moving, "
                "renaming, merging, archiving, and deleting Obsidian "
                "notes and folders, including approved memory saves.\n\n"
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
            self.voice_service.stop_speaking()

            if self.voice_service.is_recording:
                try:
                    self.voice_service.stop_recording_and_transcribe()
                except Exception:
                    pass

            self.conversation_manager.save_current_session()

        finally:
            self.root.destroy()
