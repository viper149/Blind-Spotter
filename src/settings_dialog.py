"""Sleek dark-mode Settings dialog for Blind-Spotter.
Allows configuring alert cooldowns, screen locking, camera index, detection thresholds,
and Windows startup preferences.
"""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import Optional

from src.config import ConfigManager
from src.notifier import default_notifier
from src.paths import get_resource_path, get_log_dir

logger = logging.getLogger("blind_spotter.settings")

_dialog_lock = threading.Lock()
_active_dialog_root: Optional[tk.Tk] = None


def set_dpi_awareness() -> None:
    """Set process DPI awareness for crisp font rendering on high-resolution screens."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def get_startup_shortcut_path() -> Path:
    """Return path to user's Windows Startup shortcut."""
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Blind-Spotter.lnk"


def set_windows_startup(enable: bool) -> bool:
    """Enable or disable Blind-Spotter launch at Windows login."""
    shortcut = get_startup_shortcut_path()
    if not enable:
        try:
            if shortcut.exists():
                shortcut.unlink()
                logger.info("Removed startup shortcut: %s", shortcut)
            return True
        except Exception as e:
            logger.warning("Failed to remove startup shortcut: %s", e)
            return False

    # Create startup shortcut
    try:
        target_path: str
        if hasattr(sys, "_MEIPASS"):
            target_path = str(Path(sys.executable).resolve())
        else:
            vbs_launcher = get_resource_path("run_silent.vbs")
            if vbs_launcher.exists():
                target_path = str(vbs_launcher.resolve())
            else:
                target_path = str(Path(sys.executable).resolve())

        shortcut_str = str(shortcut.resolve()).replace("'", "''")
        target_str = target_path.replace("'", "''")
        work_dir = str(Path(target_path).parent.resolve()).replace("'", "''")

        ps_cmd = (
            f"$w = New-Object -ComObject WScript.Shell; "
            f"$s = $w.CreateShortcut('{shortcut_str}'); "
            f"$s.TargetPath = '{target_str}'; "
            f"$s.WorkingDirectory = '{work_dir}'; "
            f"$s.Description = 'Blind-Spotter Stealth Shoulder-Surfing Monitor'; "
            f"$s.Save()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd],
            capture_output=True,
            timeout=5,
            check=False,
        )
        logger.info("Created Windows startup shortcut at %s", shortcut)
        return True
    except Exception as e:
        logger.warning("Failed to create startup shortcut: %s", e)
        return False


class SettingsDialog:
    """Dark-themed graphical configuration dialog."""

    def __init__(self, config_mgr: ConfigManager) -> None:
        self.config_mgr = config_mgr
        self.config = config_mgr.config
        self.root: Optional[tk.Tk] = None
        self._icon_img: Optional[tk.PhotoImage] = None

    def show(self) -> None:
        """Launch the dialog in a dedicated sub-process to guarantee Tcl/Tk thread isolation and prevent crashes."""
        try:
            if hasattr(sys, "_MEIPASS"):
                subprocess.Popen([sys.executable, "--settings"])
            else:
                main_py = get_resource_path("main.py")
                subprocess.Popen([sys.executable, str(main_py), "--settings"])
        except Exception as e:
            logger.warning("Could not launch settings sub-process (%s). Falling back to in-process thread.", e)
            threading.Thread(target=self._run_tk, daemon=True, name="SettingsGUIThread").start()

    def run_standalone(self) -> None:
        """Run dialog directly on main thread of a dedicated settings process."""
        set_dpi_awareness()
        self.root = tk.Tk()
        self._build_ui()
        self.root.mainloop()

    def _run_tk(self) -> None:
        global _active_dialog_root

        with _dialog_lock:
            if _active_dialog_root is not None:
                try:
                    _active_dialog_root.lift()
                    _active_dialog_root.focus_force()
                    return
                except Exception:
                    _active_dialog_root = None

            set_dpi_awareness()
            self.root = tk.Tk()
            _active_dialog_root = self.root

        try:
            self._build_ui()
            self.root.mainloop()
        finally:
            with _dialog_lock:
                _active_dialog_root = None

    def _build_ui(self) -> None:
        if not self.root:
            return

        self.root.title("Blind-Spotter Settings")
        self.root.geometry("520x720")
        self.root.minsize(500, 680)
        self.root.resizable(True, True)

        # Set window icon
        icon_path = get_resource_path("assets/icon.png")
        if icon_path.exists():
            try:
                self._icon_img = tk.PhotoImage(file=str(icon_path))
                self.root.iconphoto(False, self._icon_img)
            except Exception as e:
                logger.debug("Could not set window icon: %s", e)

        # Dark theme palette
        bg_dark = "#12141a"
        bg_card = "#1a1e27"
        fg_white = "#f3f4f6"
        fg_muted = "#9ca3af"
        accent_blue = "#38bdf8"
        accent_green = "#10b981"
        border_color = "#2e3646"

        self.root.configure(bg=bg_dark)

        # Center on screen
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(0, (screen_w - 520) // 2)
        y = max(0, (screen_h - 720) // 2)
        self.root.geometry(f"520x720+{x}+{y}")

        # 1. DOCK BOTTOM BUTTON BAR FIRST (Guarantees buttons are NEVER cut off by DPI scaling)
        btn_frame = tk.Frame(self.root, bg=bg_dark, pady=6)
        btn_frame.pack(side="bottom", fill="x", padx=24, pady=(10, 18))

        test_btn = tk.Button(
            btn_frame,
            text="🔔 Test Alert",
            command=self._test_alert,
            bg="#374151",
            fg=fg_white,
            activebackground="#4b5563",
            activeforeground=fg_white,
            bd=0,
            padx=12,
            pady=8,
            font=("Segoe UI", 9),
            relief="flat",
            cursor="hand2",
        )
        test_btn.pack(side="left")

        logs_btn = tk.Button(
            btn_frame,
            text="📂 Open Logs",
            command=self._open_logs,
            bg="#374151",
            fg=fg_white,
            activebackground="#4b5563",
            activeforeground=fg_white,
            bd=0,
            padx=12,
            pady=8,
            font=("Segoe UI", 9),
            relief="flat",
            cursor="hand2",
        )
        logs_btn.pack(side="left", padx=(8, 0))

        save_btn = tk.Button(
            btn_frame,
            text="Save Settings",
            command=self._save_settings,
            bg=accent_green,
            fg="#064e3b",
            activebackground="#34d399",
            activeforeground="#064e3b",
            bd=0,
            padx=18,
            pady=8,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
        )
        save_btn.pack(side="right", padx=(8, 0))

        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            command=self.root.destroy,
            bg="#27272a",
            fg=fg_muted,
            activebackground="#3f3f46",
            activeforeground=fg_white,
            bd=0,
            padx=12,
            pady=8,
            font=("Segoe UI", 9),
            relief="flat",
            cursor="hand2",
        )
        cancel_btn.pack(side="right")

        # 2. TOP HEADER
        header_frame = tk.Frame(self.root, bg=bg_dark, pady=10)
        header_frame.pack(side="top", fill="x", padx=24)

        title_lbl = tk.Label(
            header_frame,
            text="🛡️ Blind-Spotter",
            font=("Segoe UI", 16, "bold"),
            bg=bg_dark,
            fg=accent_blue,
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = tk.Label(
            header_frame,
            text="Stealthy Onlooker & Shoulder-Surfing Detection • An Ashnif Arnob Product",
            font=("Segoe UI", 8),
            bg=bg_dark,
            fg=fg_muted,
        )
        subtitle_lbl.pack(anchor="w", pady=(2, 0))

        # 3. MAIN CARD CONTAINER (Expands in remaining middle area)
        card = tk.Frame(self.root, bg=bg_card, bd=1, relief="flat", highlightbackground=border_color, highlightthickness=1)
        card.pack(side="top", fill="both", expand=True, padx=24, pady=(0, 8))

        content = tk.Frame(card, bg=bg_card, padx=18, pady=14)
        content.pack(fill="both", expand=True)

        # 1. Alert Cooldown Slider
        cooldown_lbl = tk.Label(content, text="Alert Cooldown (Seconds):", font=("Segoe UI", 9, "bold"), bg=bg_card, fg=fg_white)
        cooldown_lbl.pack(anchor="w")

        self.cooldown_var = tk.IntVar(value=self.config.cooldown_seconds)
        cooldown_val_lbl = tk.Label(content, text=f"{self.config.cooldown_seconds}s", font=("Segoe UI", 9), bg=bg_card, fg=accent_blue)
        cooldown_val_lbl.pack(anchor="e")

        def on_cooldown_change(val: str) -> None:
            cooldown_val_lbl.config(text=f"{int(float(val))}s")

        cooldown_slider = tk.Scale(
            content,
            from_=3,
            to=60,
            orient="horizontal",
            variable=self.cooldown_var,
            bg=bg_card,
            fg=fg_white,
            troughcolor=bg_dark,
            activebackground=accent_blue,
            highlightthickness=0,
            command=on_cooldown_change,
        )
        cooldown_slider.pack(fill="x", pady=(0, 8))

        # 2. Reaction Speed / Sampling Interval (Real-time speed)
        speed_lbl = tk.Label(content, text="Reaction Speed (Webcam Sampling Interval):", font=("Segoe UI", 9, "bold"), bg=bg_card, fg=fg_white)
        speed_lbl.pack(anchor="w")

        self.interval_var = tk.DoubleVar(value=round(self.config.sample_interval, 2))
        speed_desc = "⚡ Ultra Fast" if self.config.sample_interval <= 0.2 else ("🚀 Fast" if self.config.sample_interval <= 0.4 else "🔋 Balanced")
        speed_val_lbl = tk.Label(content, text=f"{round(self.config.sample_interval, 2)}s ({speed_desc})", font=("Segoe UI", 9), bg=bg_card, fg=accent_blue)
        speed_val_lbl.pack(anchor="e")

        def on_speed_change(val: str) -> None:
            v = round(float(val), 2)
            desc = "⚡ Ultra Fast" if v <= 0.2 else ("🚀 Fast" if v <= 0.4 else "🔋 Balanced")
            speed_val_lbl.config(text=f"{v}s ({desc})")

        speed_slider = tk.Scale(
            content,
            from_=0.1,
            to=1.0,
            resolution=0.05,
            orient="horizontal",
            variable=self.interval_var,
            bg=bg_card,
            fg=fg_white,
            troughcolor=bg_dark,
            activebackground=accent_blue,
            highlightthickness=0,
            command=on_speed_change,
        )
        speed_slider.pack(fill="x", pady=(0, 8))

        # 3. Consecutive Confirmation Frames
        frames_lbl = tk.Label(content, text="Confirmation Frames Required (Anti-Flicker):", font=("Segoe UI", 9, "bold"), bg=bg_card, fg=fg_white)
        frames_lbl.pack(anchor="w")

        self.frames_var = tk.IntVar(value=self.config.consecutive_frames_required)
        frames_val_lbl = tk.Label(content, text=f"{self.config.consecutive_frames_required} frame(s)", font=("Segoe UI", 9), bg=bg_card, fg=accent_blue)
        frames_val_lbl.pack(anchor="e")

        def on_frames_change(val: str) -> None:
            frames_val_lbl.config(text=f"{int(float(val))} frame(s)")

        frames_slider = tk.Scale(
            content,
            from_=1,
            to=5,
            orient="horizontal",
            variable=self.frames_var,
            bg=bg_card,
            fg=fg_white,
            troughcolor=bg_dark,
            activebackground=accent_blue,
            highlightthickness=0,
            command=on_frames_change,
        )
        frames_slider.pack(fill="x", pady=(0, 8))

        # 4. Detection Confidence Threshold
        conf_lbl = tk.Label(content, text="Detection Confidence Threshold:", font=("Segoe UI", 9, "bold"), bg=bg_card, fg=fg_white)
        conf_lbl.pack(anchor="w")

        self.conf_var = tk.DoubleVar(value=self.config.confidence_threshold)
        conf_val_lbl = tk.Label(content, text=f"{int(self.config.confidence_threshold * 100)}%", font=("Segoe UI", 9), bg=bg_card, fg=accent_blue)
        conf_val_lbl.pack(anchor="e")

        def on_conf_change(val: str) -> None:
            conf_val_lbl.config(text=f"{int(float(val) * 100)}%")

        conf_slider = tk.Scale(
            content,
            from_=0.2,
            to=0.9,
            resolution=0.05,
            orient="horizontal",
            variable=self.conf_var,
            bg=bg_card,
            fg=fg_white,
            troughcolor=bg_dark,
            activebackground=accent_blue,
            highlightthickness=0,
            command=on_conf_change,
        )
        conf_slider.pack(fill="x", pady=(0, 8))

        # 5. Camera Index
        cam_frame = tk.Frame(content, bg=bg_card)
        cam_frame.pack(fill="x", pady=(0, 8))

        cam_lbl = tk.Label(cam_frame, text="Camera Index (0 = Default Webcam):", font=("Segoe UI", 9, "bold"), bg=bg_card, fg=fg_white)
        cam_lbl.pack(side="left")

        self.cam_var = tk.IntVar(value=self.config.camera_index)
        cam_spin = tk.Spinbox(
            cam_frame,
            from_=0,
            to=5,
            textvariable=self.cam_var,
            width=5,
            bg=bg_dark,
            fg=fg_white,
            buttonbackground=bg_card,
            highlightthickness=1,
            highlightbackground=border_color,
        )
        cam_spin.pack(side="right")

        # 6. Checkboxes (Audio, Screen Lock, Startup)
        self.sound_var = tk.BooleanVar(value=self.config.play_sound)
        sound_chk = tk.Checkbutton(
            content,
            text="🔊 Play warning chime on alert",
            variable=self.sound_var,
            bg=bg_card,
            fg=fg_white,
            selectcolor=bg_dark,
            activebackground=bg_card,
            activeforeground=fg_white,
            font=("Segoe UI", 9),
        )
        sound_chk.pack(anchor="w", pady=(0, 4))

        self.lock_var = tk.BooleanVar(value=self.config.lock_screen_on_alert)
        lock_chk = tk.Checkbutton(
            content,
            text="🔒 Automatically lock Windows workstation on alert",
            variable=self.lock_var,
            bg=bg_card,
            fg=fg_white,
            selectcolor=bg_dark,
            activebackground=bg_card,
            activeforeground=fg_white,
            font=("Segoe UI", 9),
        )
        lock_chk.pack(anchor="w", pady=(0, 4))

        # Windows Startup Checkbox (with wraplength so text is never cut off)
        is_startup_active = get_startup_shortcut_path().exists() or self.config.start_with_windows
        self.startup_var = tk.BooleanVar(value=is_startup_active)
        startup_chk = tk.Checkbutton(
            content,
            text="🚀 Launch Blind-Spotter automatically when Windows starts",
            variable=self.startup_var,
            bg=bg_card,
            fg=fg_white,
            selectcolor=bg_dark,
            activebackground=bg_card,
            activeforeground=fg_white,
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=440,
        )
        startup_chk.pack(anchor="w", fill="x")

    def _open_logs(self) -> None:
        """Open the diagnostics logs directory in Windows Explorer."""
        log_dir = get_log_dir()
        try:
            os.startfile(str(log_dir))
        except Exception as e:
            logger.warning("Could not open logs folder: %s", e)
            messagebox.showinfo("Logs Directory", f"Logs directory:\n{log_dir}")

    def _test_alert(self) -> None:
        """Trigger a safe test alert with sound and toast (without locking computer)."""
        default_notifier.trigger_onlooker_alert(
            title="🔔 Blind-Spotter Test Alert",
            message="Test successful! Detection and notifications are working properly.",
            lock_screen=False,
            play_sound=self.sound_var.get(),
        )

    def _save_settings(self) -> None:
        """Commit updated values to config and sync Windows startup preference."""
        startup_enabled = bool(self.startup_var.get())
        set_windows_startup(startup_enabled)

        self.config_mgr.update(
            cooldown_seconds=int(self.cooldown_var.get()),
            sample_interval=round(float(self.interval_var.get()), 2),
            consecutive_frames_required=int(self.frames_var.get()),
            confidence_threshold=round(float(self.conf_var.get()), 2),
            camera_index=int(self.cam_var.get()),
            play_sound=bool(self.sound_var.get()),
            lock_screen_on_alert=bool(self.lock_var.get()),
            start_with_windows=startup_enabled,
        )
        logger.info("Settings updated via GUI dialog.")
        if self.root:
            self.root.destroy()
