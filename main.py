"""
Voice to Text - Speech Recognition Desktop App
Converts spoken words to text using Google Web Speech API.
Supports both real-time microphone input and audio file upload.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import speech_recognition as sr
import threading
import datetime
import os
import sys
import tempfile
import time
import subprocess

# Set up ffmpeg path (bundled via imageio-ffmpeg for .exe)
import imageio_ffmpeg
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()


class VoiceToTextApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice to Text")
        self.root.geometry("780x680")
        self.root.minsize(560, 520)

        self.is_listening = False
        self.is_processing = False
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 0.8
        self.recognizer.energy_threshold = 300

        # Timer state
        self._process_start_time = None
        self._timer_id = None
        self._total_chunks = 0
        self._current_chunk = 0
        self._chunk_times = []  # track per-chunk processing times

        # Style
        style = ttk.Style()
        style.configure("TFrame", padding=10)
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 11))
        style.configure("Big.TButton", font=("Segoe UI", 12, "bold"))
        style.configure("Progress.TLabel", font=("Consolas", 11, "bold"))
        style.configure("Detail.TLabel", font=("Consolas", 9))

        self._build_ui()

    # ──────────────────────────── UI ────────────────────────────

    def _build_ui(self):
        # Header
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=15, pady=(15, 5))
        ttk.Label(header, text="Voice to Text", style="Title.TLabel").pack(side="left")

        # Language selector
        lang_frame = ttk.Frame(self.root)
        lang_frame.pack(fill="x", padx=15, pady=(0, 5))
        ttk.Label(lang_frame, text="Language:").pack(side="left")
        self.lang_var = tk.StringVar(value="English (US)")
        self.lang_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.lang_var,
            values=["English (US)", "English (UK)", "Chinese", "Spanish",
                    "French", "German", "Japanese", "Korean"],
            state="readonly",
            width=15,
        )
        self.lang_combo.pack(side="left", padx=(5, 0))

        # Button row
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=15, pady=5)

        self.listen_btn = ttk.Button(
            btn_frame, text="Start Listening", style="Big.TButton", command=self.toggle_listening
        )
        self.listen_btn.pack(side="left", ipadx=15, ipady=8)

        self.upload_btn = ttk.Button(
            btn_frame, text="Upload File", style="Big.TButton", command=self.upload_file
        )
        self.upload_btn.pack(side="left", padx=(10, 0), ipadx=15, ipady=8)

        ttk.Button(btn_frame, text="Clear", command=self.clear_text).pack(side="left", padx=(10, 0), ipady=8)
        ttk.Button(btn_frame, text="Save to File", command=self.save_text).pack(side="left", padx=(10, 0), ipady=8)
        ttk.Button(btn_frame, text="Copy", command=self.copy_text).pack(side="left", padx=(10, 0), ipady=8)

        # Status
        self.status_var = tk.StringVar(value="Ready. Click 'Start Listening' or 'Upload File' to begin.")
        self.status_label = ttk.Label(self.root, textvariable=self.status_var, style="Status.TLabel", foreground="gray")
        self.status_label.pack(fill="x", padx=15, pady=(5, 2))

        # ── Progress panel (hidden by default) ──
        self.progress_frame = ttk.Frame(self.root)

        # Row 1: progress bar + percentage
        bar_row = ttk.Frame(self.progress_frame)
        bar_row.pack(fill="x", padx=0, pady=(0, 2))

        self.progress = ttk.Progressbar(bar_row, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True)

        self.percent_var = tk.StringVar(value="")
        ttk.Label(bar_row, textvariable=self.percent_var, style="Progress.TLabel", width=8).pack(side="left", padx=(8, 0))

        # Row 2: chunk info + timer + ETA
        info_row = ttk.Frame(self.progress_frame)
        info_row.pack(fill="x", padx=0, pady=(0, 4))

        self.chunk_var = tk.StringVar(value="")
        ttk.Label(info_row, textvariable=self.chunk_var, style="Detail.TLabel", foreground="#555").pack(side="left")

        self.timer_var = tk.StringVar(value="")
        ttk.Label(info_row, textvariable=self.timer_var, style="Detail.TLabel", foreground="#555").pack(side="right")

        self.eta_var = tk.StringVar(value="")
        ttk.Label(info_row, textvariable=self.eta_var, style="Detail.TLabel", foreground="#888").pack(side="right", padx=(15, 0))

        # Row 3: detail log (scrollable, small)
        log_frame = ttk.Frame(self.progress_frame)
        log_frame.pack(fill="x", padx=0, pady=(0, 2))

        self.log_text = tk.Text(
            log_frame,
            height=4,
            wrap="word",
            font=("Consolas", 9),
            foreground="#444",
            background="#f5f5f5",
            relief="flat",
            padx=6,
            pady=4,
        )
        self.log_text.pack(fill="x")
        self.log_text.config(state="disabled")

        # ── Text area with scrollbar ──
        text_frame = ttk.Frame(self.root)
        text_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        self.text_area = tk.Text(
            text_frame,
            wrap="word",
            font=("Consolas", 12),
            yscrollcommand=scrollbar.set,
            padx=10,
            pady=10,
        )
        self.text_area.pack(fill="both", expand=True)
        scrollbar.config(command=self.text_area.yview)

        # Insert placeholder
        self.text_area.insert("1.0", "Recognized text will appear here...")
        self.text_area.config(foreground="gray")
        self.text_area.bind("<FocusIn>", self._clear_placeholder)

    # ──────────────────────────── Helpers ────────────────────────────

    def _clear_placeholder(self, event=None):
        current = self.text_area.get("1.0", "end-1c")
        if current == "Recognized text will appear here...":
            self.text_area.delete("1.0", "end")
            self.text_area.config(foreground="black")

    def _get_lang_code(self):
        mapping = {
            "English (US)": "en-US",
            "English (UK)": "en-GB",
            "Chinese": "zh-CN",
            "Spanish": "es-ES",
            "French": "fr-FR",
            "German": "de-DE",
            "Japanese": "ja-JP",
            "Korean": "ko-KR",
        }
        return mapping.get(self.lang_var.get(), "en-US")

    def _set_buttons_state(self, state):
        self.listen_btn.config(state=state)
        self.upload_btn.config(state=state)
        self.lang_combo.config(state=state if state == "normal" else "disabled")

    def _safe_status(self, msg, color="gray"):
        self.root.after(0, lambda: (self.status_var.set(msg), self.status_label.config(foreground=color)))

    def _safe_stop(self):
        self.root.after(0, self._stop_listening)

    def _stop_listening(self):
        self.is_listening = False
        self.listen_btn.config(text="Start Listening")
        self._set_buttons_state("normal")

    def _safe_messagebox(self, title, msg):
        self.root.after(0, lambda: messagebox.showerror(title, msg))

    def _insert_text(self, text):
        def _do():
            self.text_area.config(foreground="black")
            self.text_area.insert("end", text)
            self.text_area.see("end")
        self.root.after(0, _do)

    def _log(self, msg):
        """Append a timestamped line to the detail log panel."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        def _do():
            self.log_text.config(state="normal")
            self.log_text.insert("end", line)
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.root.after(0, _do)

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    # ──────────────────────────── Timer ────────────────────────────

    def _start_timer(self):
        self._process_start_time = time.time()
        self._tick_timer()

    def _tick_timer(self):
        if self._process_start_time is None:
            return
        elapsed = time.time() - self._process_start_time
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        self.timer_var.set(f"⏱ {mins:02d}:{secs:02d}")

        # ETA calculation
        if self._total_chunks > 0 and self._current_chunk > 0:
            avg_per_chunk = elapsed / self._current_chunk
            remaining = (self._total_chunks - self._current_chunk) * avg_per_chunk
            r_min = int(remaining // 60)
            r_sec = int(remaining % 60)
            self.eta_var.set(f"ETA ~{r_min:02d}:{r_sec:02d}")
        else:
            self.eta_var.set("ETA --:--")

        self._timer_id = self.root.after(500, self._tick_timer)

    def _stop_timer(self):
        if self._timer_id:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None

    # ──────────────────────────── Microphone Listening ────────────────────────────

    def toggle_listening(self):
        if self.is_processing:
            return
        if not self.is_listening:
            self._clear_placeholder()
            self.is_listening = True
            self.listen_btn.config(text="Stop Listening")
            self.status_var.set("Listening... Speak now.")
            self.status_label.config(foreground="red")
            self.upload_btn.config(state="disabled")
            self.lang_combo.config(state="disabled")

            thread = threading.Thread(target=self._listen_loop, daemon=True)
            thread.start()
        else:
            self.is_listening = False
            self.listen_btn.config(text="Start Listening")
            self.status_var.set("Stopped.")
            self.status_label.config(foreground="gray")
            self._set_buttons_state("normal")

    def _listen_loop(self):
        lang_code = self._get_lang_code()
        while self.is_listening:
            try:
                with sr.Microphone() as source:
                    self._safe_status("Listening... Speak now.", "red")
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=15)

                if not self.is_listening:
                    break

                self._safe_status("Processing speech...", "orange")

                try:
                    text = self.recognizer.recognize_google(audio, language=lang_code)
                    if text.strip():
                        timestamp = datetime.datetime.now().strftime("[%H:%M:%S] ")
                        self._insert_text(timestamp + text + "\n")
                        self._safe_status("Ready. Listening for next phrase...", "red")
                except sr.UnknownValueError:
                    self._safe_status("Could not understand audio. Listening again...", "orange")
                except sr.RequestError as e:
                    self._safe_status(f"API error: {e}", "orange")
                    self._safe_stop()

            except sr.WaitTimeoutError:
                continue
            except OSError as e:
                self._safe_status(f"Microphone error: {e}", "orange")
                self._safe_stop()
                self._safe_messagebox("Microphone Error",
                                      f"Cannot access microphone:\n{e}\n\nPlease check your audio devices.")
            except Exception as e:
                self._safe_status(f"Error: {e}", "orange")
                self._safe_stop()

    # ──────────────────────────── File Upload & Conversion ────────────────────────────

    def upload_file(self):
        if self.is_listening or self.is_processing:
            return

        filepath = filedialog.askopenfilename(
            title="Select an audio file",
            filetypes=[
                ("Audio files", "*.wav *.mp3 *.flac *.aiff *.aif *.m4a *.ogg *.wma *.aac"),
                ("WAV files", "*.wav"),
                ("MP3 files", "*.mp3"),
                ("All files", "*.*"),
            ],
        )
        if not filepath:
            return

        self._clear_placeholder()
        self.is_processing = True
        self._set_buttons_state("disabled")

        # Show progress panel
        self.progress_frame.pack(fill="x", padx=15, pady=(5, 0))
        self._clear_log()

        # Reset progress display
        self.percent_var.set("0%")
        self.chunk_var.set("")
        self.timer_var.set("⏱ 00:00")
        self.eta_var.set("ETA --:--")
        self.progress.config(maximum=1, value=0)

        thread = threading.Thread(target=self._process_file, args=(filepath,), daemon=True)
        thread.start()

    def _convert_to_wav(self, src_path, dest_path):
        """Convert any audio file to 16kHz mono WAV using bundled ffmpeg."""
        cmd = [
            FFMPEG_PATH,
            "-y",                # overwrite output
            "-i", src_path,      # input
            "-ar", "16000",      # sample rate 16kHz
            "-ac", "1",          # mono
            "-acodec", "pcm_s16le",  # 16-bit PCM
            dest_path,
        ]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode("utf-8", errors="ignore")[:500]
            raise RuntimeError(f"ffmpeg failed: {err}")
        except FileNotFoundError:
            raise RuntimeError(f"ffmpeg not found at {FFMPEG_PATH}")

    def _process_file(self, filepath):
        lang_code = self._get_lang_code()
        filename = os.path.basename(filepath)
        temp_wav_path = None
        self._total_chunks = 0
        self._current_chunk = 0
        self._chunk_times = []

        try:
            # ── Step 1: Create temp WAV and convert / normalize audio ──
            ext = os.path.splitext(filepath)[1].lower()
            temp_fd, temp_wav_path = tempfile.mkstemp(suffix=".wav")
            os.close(temp_fd)
            wav_path = temp_wav_path

            if ext == ".wav":
                self._safe_status(f"Normalizing {filename}...", "orange")
                self._log(f"Normalizing WAV: {filename}")
            else:
                self._safe_status(f"Converting {filename} to WAV...", "orange")
                self._log(f"Converting {ext} to WAV via ffmpeg...")

            self._convert_to_wav(filepath, wav_path)
            self._log(f"WAV ready: {wav_path}")

            # ── Step 2: Analyze duration & plan chunks ──
            with sr.AudioFile(wav_path) as source:
                total_duration = source.DURATION

            chunk_size = 30  # seconds per chunk
            self._total_chunks = max(1, int(total_duration // chunk_size) + (1 if total_duration % chunk_size > 0 else 0))

            self._log(f"Duration: {total_duration:.1f}s | Chunks: {self._total_chunks} (30s each)")
            self._safe_status(
                f"Processing {filename} — {total_duration:.1f}s, {self._total_chunks} chunks",
                "orange",
            )

            # Initialize progress bar
            self.root.after(0, lambda: self.progress.config(maximum=self._total_chunks, value=0))

            # Start timer
            self._start_timer()

            all_text = []

            # ── Step 3: Process each chunk ──
            for i in range(self._total_chunks):
                if not self.is_processing:
                    break

                offset = i * chunk_size
                duration = min(chunk_size, total_duration - offset)
                if duration <= 0:
                    break

                self._current_chunk = i + 1
                chunk_start = time.time()

                self._safe_status(
                    f"Transcribing chunk {i + 1}/{self._total_chunks} ({offset:.0f}s–{offset + duration:.0f}s)...",
                    "orange",
                )
                self._log(f"Chunk {i + 1}/{self._total_chunks}: reading audio {offset:.0f}s–{offset + duration:.0f}s...")

                # Update chunk info label
                self.root.after(0, lambda c=i + 1, t=self._total_chunks: self.chunk_var.set(
                    f"Chunk {c}/{t}"
                ))

                # Read audio chunk
                with sr.AudioFile(wav_path) as source:
                    audio_data = self.recognizer.record(source, offset=offset, duration=duration)

                self._log(f"Chunk {i + 1}/{self._total_chunks}: sending to Google API...")

                # Recognize
                try:
                    text = self.recognizer.recognize_google(audio_data, language=lang_code)
                    chunk_elapsed = time.time() - chunk_start
                    self._chunk_times.append(chunk_elapsed)

                    if text.strip():
                        all_text.append(text.strip())
                        # Show partial result immediately with chunk tag
                        self._insert_text(f"[{offset:.0f}s] {text.strip()}\n")
                        self._log(f"Chunk {i + 1}/{self._total_chunks}: OK ({chunk_elapsed:.1f}s) — {len(text)} chars")
                    else:
                        self._log(f"Chunk {i + 1}/{self._total_chunks}: empty result ({chunk_elapsed:.1f}s)")

                except sr.UnknownValueError:
                    chunk_elapsed = time.time() - chunk_start
                    self._chunk_times.append(chunk_elapsed)
                    all_text.append(f"[unintelligible at {offset:.0f}s]")
                    self._insert_text(f"[{offset:.0f}s] [unintelligible]\n")
                    self._log(f"Chunk {i + 1}/{self._total_chunks}: could not understand ({chunk_elapsed:.1f}s)")

                except sr.RequestError as e:
                    self._safe_status(f"API error: {e}", "red")
                    self._log(f"Chunk {i + 1}/{self._total_chunks}: API ERROR — {e}")
                    break

                # Update progress bar + percentage
                pct = int((i + 1) / self._total_chunks * 100)
                self.root.after(0, lambda v=i + 1, p=pct: (
                    self.progress.config(value=v),
                    self.percent_var.set(f"{p}%"),
                ))

            # ── Step 4: Finalize ──
            self._stop_timer()
            final_elapsed = time.time() - self._process_start_time if self._process_start_time else 0

            if all_text:
                self._insert_text("\n")
                total_chars = len(" ".join(all_text))
                self._log(f"Done — {total_chars} chars, {self._current_chunk} chunks, {final_elapsed:.1f}s total")
                self._safe_status(
                    f"Done — {total_chars} chars in {final_elapsed:.1f}s ({self._current_chunk} chunks)",
                    "green",
                )
            else:
                self._log(f"No speech detected in {self._total_chunks} chunks")
                self._safe_status(f"No speech detected in {filename}.", "orange")

            # Final percentage
            self.root.after(0, lambda: self.percent_var.set("100%"))

        except Exception as e:
            self._stop_timer()
            self._safe_status(f"Error: {e}", "red")
            self._log(f"ERROR: {e}")
            self._safe_messagebox("File Processing Error",
                                  f"Failed to process {filename}:\n\n{e}")
        finally:
            # Clean up temp file
            if temp_wav_path and os.path.exists(temp_wav_path):
                try:
                    os.remove(temp_wav_path)
                except Exception:
                    pass

            # Reset state
            self.is_processing = False
            self._process_start_time = None
            self._stop_timer()
            self.root.after(500, lambda: (
                self.progress_frame.pack_forget(),
                self._set_buttons_state("normal"),
            ))

    # ──────────────────────────── Text Actions ────────────────────────────

    def clear_text(self):
        self.text_area.delete("1.0", "end")
        self.status_var.set("Text cleared.")
        self.status_label.config(foreground="gray")

    def save_text(self):
        content = self.text_area.get("1.0", "end-1c").strip()
        if not content or content == "Recognized text will appear here...":
            messagebox.showinfo("Save", "Nothing to save.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"transcript_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                self.status_var.set(f"Saved to {filepath}")
                self.status_label.config(foreground="green")
            except Exception as e:
                messagebox.showerror("Save Error", str(e))

    def copy_text(self):
        content = self.text_area.get("1.0", "end-1c").strip()
        if content and content != "Recognized text will appear here...":
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.status_var.set("Copied to clipboard.")
            self.status_label.config(foreground="green")
        else:
            self.status_var.set("Nothing to copy.")


def main():
    root = tk.Tk()
    app = VoiceToTextApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
