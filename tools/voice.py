from __future__ import annotations

import os
import tempfile
import threading
import time
import wave
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd
from openai import OpenAI


@dataclass(frozen=True)
class AudioDevice:
    index: int
    name: str
    host_api: str

    @property
    def label(self) -> str:
        return f"[{self.index}] {self.name} ({self.host_api})"


class VoiceService:
    SAMPLE_RATE = 16_000
    CHANNELS = 1
    SAMPLE_WIDTH = 2
    SUPPORTED_VOICES = (
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "nova",
        "onyx",
        "sage",
        "shimmer",
        "verse",
        "marin",
        "cedar",
    )

    def __init__(self, client: OpenAI) -> None:
        self.client = client

        self.transcription_model = os.getenv(
            "OPENAI_TRANSCRIPTION_MODEL",
            "gpt-4o-mini-transcribe",
        )

        self.tts_model = os.getenv(
            "OPENAI_TTS_MODEL",
            "gpt-4o-mini-tts",
        )

        configured_voice = os.getenv(
            "FRIDAY_VOICE",
            "coral",
        ).casefold().strip()
        self.voice = (
            configured_voice
            if configured_voice in self.SUPPORTED_VOICES
            else "coral"
        )

        self._stream: sd.InputStream | None = None
        self._recorded_chunks: list[np.ndarray] = []
        self._recording_lock = threading.Lock()
        self._is_recording = False
        self._is_speaking = False
        self._microphone_level = 0.0
        self._diagnostic_messages: deque[str] = deque(maxlen=200)
        self._input_device = self._default_device_index(0)
        self._output_device = self._default_device_index(1)

        self._audio_folder = (
            Path(tempfile.gettempdir())
            / "friday_voice"
        )

        self._audio_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.log_diagnostic(
            "Voice service initialized with "
            f"input={self._input_device}, output={self._output_device}, "
            f"voice={self.voice}."
        )

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def microphone_level(self) -> float:
        return self._microphone_level

    def get_diagnostic_messages(self) -> list[str]:
        return list(self._diagnostic_messages)

    def log_diagnostic(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._diagnostic_messages.append(
            f"[{timestamp}] {message.strip()}"
        )

    @property
    def available_voices(self) -> tuple[str, ...]:
        return self.SUPPORTED_VOICES

    def set_voice(self, voice: str) -> None:
        clean_voice = voice.casefold().strip()

        if clean_voice not in self.SUPPORTED_VOICES:
            raise ValueError(f"Unsupported Friday voice: {voice}")

        if self._is_speaking:
            raise RuntimeError(
                "Stop playback before changing Friday's voice."
            )

        self.voice = clean_voice
        self.log_diagnostic(
            f"TTS voice changed to {clean_voice}."
        )

    @property
    def input_device(self) -> int | None:
        return self._input_device

    @property
    def output_device(self) -> int | None:
        return self._output_device

    def list_input_devices(self) -> list[AudioDevice]:
        return self._list_devices(channel_kind="input")

    def list_output_devices(self) -> list[AudioDevice]:
        return self._list_devices(channel_kind="output")

    def set_input_device(self, device_index: int) -> None:
        if self._is_recording:
            raise RuntimeError(
                "Stop recording before changing the input device."
            )

        device = sd.query_devices(device_index)

        if int(device["max_input_channels"]) < 1:
            raise ValueError(
                "The selected device does not provide an audio input."
            )

        sd.check_input_settings(
            device=device_index,
            channels=self.CHANNELS,
            samplerate=self.SAMPLE_RATE,
            dtype="int16",
        )
        self._input_device = device_index
        self.log_diagnostic(
            f"Input device changed to [{device_index}] {device['name']}."
        )

    def set_output_device(self, device_index: int) -> None:
        if self._is_speaking:
            raise RuntimeError(
                "Stop playback before changing the output device."
            )

        device = sd.query_devices(device_index)

        if int(device["max_output_channels"]) < 1:
            raise ValueError(
                "The selected device does not provide an audio output."
            )

        sd.check_output_settings(
            device=device_index,
            channels=1,
        )
        self._output_device = device_index
        self.log_diagnostic(
            f"Output device changed to [{device_index}] {device['name']}."
        )

    def start_recording(self) -> None:
        if self._is_recording:
            return

        self.stop_speaking()

        with self._recording_lock:
            self._recorded_chunks.clear()

        self._is_recording = True

        try:
            self._stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype="int16",
                device=self._input_device,
                callback=self._audio_callback,
            )

            self._stream.start()
            self.log_diagnostic(
                f"Recording started on input device {self._input_device}."
            )

        except Exception:
            self._is_recording = False
            self._stream = None
            raise

    def stop_recording_and_transcribe(self) -> str:
        if not self._is_recording:
            return ""

        self._is_recording = False

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        self.log_diagnostic("Recording stopped; starting transcription.")

        audio_path = self._save_recording()

        if audio_path is None:
            return ""

        try:
            return self.transcribe(audio_path)

        finally:
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                pass

    def transcribe(self, audio_path: Path) -> str:
        with audio_path.open("rb") as audio_file:
            transcription = (
                self.client.audio.transcriptions.create(
                    model=self.transcription_model,
                    file=audio_file,
                    response_format="text",
                    prompt=(
                        "The speaker is Brad. The conversation may "
                        "include controls engineering, PLCs, conveyor "
                        "automation, Obsidian, RV systems, CAN bus, "
                        "SkySentinel, and an AI assistant named Friday."
                    ),
                )
            )

        if isinstance(transcription, str):
            return transcription.strip()

        text = getattr(transcription, "text", "")
        return str(text).strip()

    def speak(
        self,
        text: str,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        cleaned_text = text.strip()

        if not cleaned_text:
            if on_finished:
                on_finished()

            return

        self.stop_speaking()

        thread = threading.Thread(
            target=self._speak_worker,
            args=(cleaned_text, on_finished),
            daemon=True,
        )

        thread.start()

    def stop_speaking(self) -> None:
        try:
            sd.stop()
        except Exception:
            pass

        self._is_speaking = False

    def test_microphone(self, duration: float = 0.75) -> float:
        if self._is_recording:
            raise RuntimeError(
                "Stop recording before testing the microphone."
            )

        sample_count = int(self.SAMPLE_RATE * duration)
        audio = sd.rec(
            sample_count,
            samplerate=self.SAMPLE_RATE,
            channels=self.CHANNELS,
            dtype="float32",
            device=self._input_device,
        )
        sd.wait()
        level = self._calculate_level(audio, full_scale=1.0)
        self._microphone_level = level
        self.log_diagnostic(
            f"Microphone test completed at {level:.0%} peak level."
        )
        return level

    def test_speaker(self) -> None:
        """
        Plays a short locally generated tone.

        This does not use OpenAI. If this tone is silent,
        the issue is the selected Windows output device.
        """
        duration = 0.5
        sample_rate = 44_100
        frequency = 440

        times = np.linspace(
            0,
            duration,
            int(sample_rate * duration),
            endpoint=False,
        )

        tone = (
            0.2
            * np.sin(2 * np.pi * frequency * times)
        ).astype(np.float32)

        sd.play(
            tone,
            samplerate=sample_rate,
            device=self._output_device,
        )

        sd.wait()

    def _speak_worker(
        self,
        text: str,
        on_finished: Callable[[], None] | None,
    ) -> None:
        timestamp = int(time.time() * 1000)

        output_path = (
            self._audio_folder
            / f"friday_response_{timestamp}.wav"
        )

        self._is_speaking = True

        try:
            self.log_diagnostic(
                f"Generating speech with voice {self.voice}."
            )

            with (
                self.client.audio.speech
                .with_streaming_response.create(
                    model=self.tts_model,
                    voice=self.voice,
                    input=text,
                    instructions=(
                        "Speak as Friday, a polished, intelligent, "
                        "confident female personal assistant. "
                        "Sound natural, conversational, warm, and "
                        "slightly witty. Do not sound theatrical."
                    ),
                    response_format="wav",
                )
            ) as response:
                response.stream_to_file(output_path)

            if not output_path.exists():
                raise RuntimeError(
                    "The speech audio file was not created."
                )

            file_size = output_path.stat().st_size

            self.log_diagnostic(
                f"Speech file created ({file_size} bytes)."
            )

            if file_size < 100:
                raise RuntimeError(
                    "The generated speech file is empty or invalid."
                )

            self._play_wav(output_path)

        except Exception as exc:
            self.log_diagnostic(
                f"Voice playback failed: {exc}"
            )

        finally:
            self._is_speaking = False

            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass

            if on_finished:
                on_finished()

    def _play_wav(self, audio_path: Path) -> None:
        with wave.open(
            str(audio_path),
            "rb",
        ) as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()

            raw_audio = wav_file.readframes(
                frame_count
            )

        if sample_width == 1:
            dtype = np.uint8

        elif sample_width == 2:
            dtype = np.int16

        elif sample_width == 4:
            dtype = np.int32

        else:
            raise RuntimeError(
                "Unsupported WAV sample width: "
                f"{sample_width} bytes"
            )

        audio_data = np.frombuffer(
            raw_audio,
            dtype=dtype,
        )

        if channels > 1:
            audio_data = audio_data.reshape(
                -1,
                channels,
            )

        self.log_diagnostic(
            f"Playing audio through device {self._output_device}."
        )

        sd.play(
            audio_data,
            samplerate=sample_rate,
            device=self._output_device,
        )

        sd.wait()

    @staticmethod
    def _default_device_index(position: int) -> int | None:
        try:
            defaults = sd.default.device

            try:
                value = defaults[position]
            except (IndexError, TypeError):
                value = defaults

            index = int(value)
            return index if index >= 0 else None
        except (IndexError, TypeError, ValueError):
            return None

    @staticmethod
    def _list_devices(channel_kind: str) -> list[AudioDevice]:
        channel_key = (
            "max_input_channels"
            if channel_kind == "input"
            else "max_output_channels"
        )
        host_apis = sd.query_hostapis()
        devices: list[AudioDevice] = []

        for index, device in enumerate(sd.query_devices()):
            if int(device[channel_key]) < 1:
                continue

            host_api_index = int(device["hostapi"])
            host_api_name = str(host_apis[host_api_index]["name"])
            devices.append(
                AudioDevice(
                    index=index,
                    name=str(device["name"]),
                    host_api=host_api_name,
                )
            )

        return devices

    def _audio_callback(
        self,
        input_data: np.ndarray,
        frames: int,
        time_info,
        status,
    ) -> None:
        if status:
            self.log_diagnostic(f"Microphone status: {status}")

        if not self._is_recording:
            return

        self._microphone_level = self._calculate_level(
            input_data,
            full_scale=32768.0,
        )

        with self._recording_lock:
            self._recorded_chunks.append(
                input_data.copy()
            )

    @staticmethod
    def _calculate_level(
        audio_data: np.ndarray,
        full_scale: float,
    ) -> float:
        if audio_data.size == 0:
            return 0.0

        peak = float(
            np.max(np.abs(audio_data.astype(np.float32)))
        )
        return max(0.0, min(1.0, peak / full_scale))

    def _save_recording(self) -> Path | None:
        with self._recording_lock:
            if not self._recorded_chunks:
                return None

            audio_data = np.concatenate(
                self._recorded_chunks,
                axis=0,
            )

            self._recorded_chunks.clear()

        output_path = (
            self._audio_folder
            / "brad_recording.wav"
        )

        with wave.open(
            str(output_path),
            "wb",
        ) as wav_file:
            wav_file.setnchannels(
                self.CHANNELS
            )

            wav_file.setsampwidth(
                self.SAMPLE_WIDTH
            )

            wav_file.setframerate(
                self.SAMPLE_RATE
            )

            wav_file.writeframes(
                audio_data.tobytes()
            )

        return output_path
