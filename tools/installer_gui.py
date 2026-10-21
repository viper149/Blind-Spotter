"""Self-contained Windows Graphical & Silent Installer for Blind-Spotter.
Extracts payload, configures shortcuts, registers Windows Add/Remove programs,
and manages clean uninstallation.

An Ashnif Arnob Product
Copyright (c) 2026 Ashnif Arnob
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import winreg
import zipfile


def get_bundle_dir() -> Path:
    """Return the base path where PyInstaller extracted temporary assets."""
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def get_default_install_dir() -> Path:
    """Return %LOCALAPPDATA%\\Programs\\Blind-Spotter."""
    local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local_appdata) / "Programs" / "Blind-Spotter"


def kill_running_process(process_name: str = "Blind-Spotter.exe") -> None:
    """Safely terminate any running process to allow overwriting files."""
    try:
        subprocess.run(
            ["taskkill", "/f", "/im", process_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        time.sleep(0.5)
    except Exception:
        pass


def create_windows_shortcut(target: Path, shortcut_path: Path, work_dir: Path, desc: str, icon_path: Path) -> bool:
    """Create a Windows .lnk shortcut using WScript.Shell via PowerShell."""
    try:
        shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        ps_cmd = (
            f"$w = New-Object -ComObject WScript.Shell; "
            f"$s = $w.CreateShortcut('{str(shortcut_path)}'); "
            f"$s.TargetPath = '{str(target)}'; "
            f"$s.WorkingDirectory = '{str(work_dir)}'; "
            f"$s.Description = '{desc}'; "
            f"$s.IconLocation = '{str(icon_path)},0'; "
            f"$s.Save()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return True
    except Exception:
        return False


def register_in_windows_uninstall(install_dir: Path, exe_path: Path, uninstall_path: Path) -> None:
    """Register in Windows Add/Remove Programs (Registry HKCU)."""
    reg_key = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Blind-Spotter"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_key) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Blind-Spotter")
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "1.1.0")
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Ashnif Arnob")
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, f'"{str(exe_path)}",0')
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{str(uninstall_path)}"')
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    except Exception as e:
        print(f"Registry registration error: {e}", file=sys.stderr)


def create_uninstaller_script(install_dir: Path) -> Path:
    """Generate clean uninstall script in the target install directory."""
    uninstaller_vbs = install_dir / "uninstall.vbs"
    uninstaller_bat = install_dir / "uninstall.bat"
    safe_dir = str(install_dir).replace('"', '""')
    content = (
        "' Blind-Spotter Uninstaller\n"
        "' An Ashnif Arnob Product\n\n"
        "Set WshShell = CreateObject(\"WScript.Shell\")\n"
        "Set fso = CreateObject(\"Scripting.FileSystemObject\")\n\n"
        "ans = MsgBox(\"Are you sure you want to completely uninstall Blind-Spotter?\", vbYesNo + vbQuestion, \"Blind-Spotter Uninstall\")\n"
        "If ans = vbYes Then\n"
        "    ' Kill any running instances\n"
        "    WshShell.Run \"taskkill /f /im Blind-Spotter.exe\", 0, True\n"
        "    WScript.Sleep 500\n\n"
        "    ' Remove shortcuts\n"
        "    desktop = WshShell.SpecialFolders(\"Desktop\") & \"\\Blind-Spotter.lnk\"\n"
        "    programs = WshShell.SpecialFolders(\"Programs\") & \"\\Blind-Spotter.lnk\"\n"
        "    startup = WshShell.SpecialFolders(\"Startup\") & \"\\Blind-Spotter.lnk\"\n\n"
        "    If fso.FileExists(desktop) Then fso.DeleteFile desktop, True\n"
        "    If fso.FileExists(programs) Then fso.DeleteFile programs, True\n"
        "    If fso.FileExists(startup) Then fso.DeleteFile startup, True\n\n"
        "    ' Remove Windows Add/Remove Programs Registry\n"
        "    On Error Resume Next\n"
        "    WshShell.RegDelete \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Blind-Spotter\\\"\n"
        "    On Error GoTo 0\n\n"
        "    ' Schedule folder self-deletion via background cmd\n"
        f"    installPath = \"{safe_dir}\"\n"
        "    cmd = \"cmd.exe /c ping 127.0.0.1 -n 2 > nul & rd /s /q \"\"\" & installPath & \"\"\"\"\n"
        "    WshShell.Run cmd, 0, False\n\n"
        "    MsgBox \"Blind-Spotter was successfully removed from your computer.\", vbInformation, \"Uninstall Complete\"\n"
        "End If\n"
    )
    try:
        with open(uninstaller_vbs, "w", encoding="utf-8") as f:
            f.write(content)
        with open(uninstaller_bat, "w", encoding="utf-8") as f:
            f.write(f'@echo off\nwscript.exe "{uninstaller_vbs}"\n')
    except Exception:
        pass
    return uninstaller_vbs


def perform_installation(
    dest_dir: Path,
    desktop_shortcut: bool,
    start_menu_shortcut: bool,
    startup_shortcut: bool,
    launch_now: bool,
    progress_callback=None,
) -> bool:
    """Execute the core file extraction and Windows integration."""
    try:
        if progress_callback:
            progress_callback(10, "Closing running processes...")
        kill_running_process("Blind-Spotter.exe")

        if progress_callback:
            progress_callback(25, "Preparing destination directory...")
        dest_dir.mkdir(parents=True, exist_ok=True)

        bundle_dir = get_bundle_dir()
        payload_zip = bundle_dir / "app_payload.zip"

        if not payload_zip.exists():
            raise FileNotFoundError(f"Missing payload archive at {payload_zip}")

        if progress_callback:
            progress_callback(40, "Extracting application binaries and neural models...")

        with zipfile.ZipFile(payload_zip, "r") as zf:
            zf.extractall(dest_dir)

        exe_path = dest_dir / "Blind-Spotter.exe"
        icon_path = dest_dir / "_internal" / "assets" / "icon.ico"
        if not icon_path.exists():
            icon_path = exe_path

        if progress_callback:
            progress_callback(70, "Creating Windows shortcuts...")

        # 1. Desktop Shortcut
        if desktop_shortcut:
            desktop_dir = Path.home() / "Desktop"
            create_windows_shortcut(
                target=exe_path,
                shortcut_path=desktop_dir / "Blind-Spotter.lnk",
                work_dir=dest_dir,
                desc="Blind-Spotter Stealth Shoulder-Surfing Monitor",
                icon_path=icon_path,
            )

        # 2. Start Menu Shortcut
        if start_menu_shortcut:
            appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
            programs_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            create_windows_shortcut(
                target=exe_path,
                shortcut_path=programs_dir / "Blind-Spotter.lnk",
                work_dir=dest_dir,
                desc="Blind-Spotter Stealth Shoulder-Surfing Monitor",
                icon_path=icon_path,
            )

        # 3. Windows Startup Shortcut
        if startup_shortcut:
            appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
            startup_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            create_windows_shortcut(
                target=exe_path,
                shortcut_path=startup_dir / "Blind-Spotter.lnk",
                work_dir=dest_dir,
                desc="Blind-Spotter Stealth Shoulder-Surfing Monitor",
                icon_path=icon_path,
            )

        if progress_callback:
            progress_callback(85, "Configuring Windows uninstaller...")

        uninstaller_path = create_uninstaller_script(dest_dir)
        register_in_windows_uninstall(dest_dir, exe_path, uninstaller_path)

        if progress_callback:
            progress_callback(100, "Installation complete!")

        if launch_now and exe_path.exists():
            subprocess.Popen([str(exe_path)], cwd=str(dest_dir))

        return True
    except Exception as e:
        if progress_callback:
            progress_callback(0, f"Error: {e}")
        return False


class InstallerUI:
    """Modern dark-themed Tkinter installer window."""

    def __init__(self) -> None:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        self.root = tk.Tk()
        self.root.title("Blind-Spotter Setup")
        self.root.geometry("520x460")
        self.root.resizable(False, False)

        self.dest_var = tk.StringVar(value=str(get_default_install_dir()))
        self.desktop_var = tk.BooleanVar(value=True)
        self.start_menu_var = tk.BooleanVar(value=True)
        self.startup_var = tk.BooleanVar(value=True)
        self.launch_var = tk.BooleanVar(value=True)

        self.bg_dark = "#12141a"
        self.bg_card = "#1a1e27"
        self.fg_white = "#f3f4f6"
        self.fg_muted = "#9ca3af"
        self.accent_blue = "#38bdf8"
        self.accent_green = "#10b981"
        self.border_color = "#2e3646"

        self.root.configure(bg=self.bg_dark)
        self._center_window()
        self._build_ui()

    def _center_window(self) -> None:
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - 520) // 2)
        y = max(0, (sh - 460) // 2)
        self.root.geometry(f"+{x}+{y}")

    def _build_ui(self) -> None:
        # Header
        header = tk.Frame(self.root, bg=self.bg_dark, pady=16)
        header.pack(fill="x", padx=24)

        title = tk.Label(
            header,
            text="🛡️ Blind-Spotter Setup",
            font=("Segoe UI", 16, "bold"),
            bg=self.bg_dark,
            fg=self.accent_blue,
        )
        title.pack(anchor="w")

        sub = tk.Label(
            header,
            text="Stealth Onlooker Detection • v1.1.0-Enterprise • An Ashnif Arnob Product",
            font=("Segoe UI", 8),
            bg=self.bg_dark,
            fg=self.fg_muted,
        )
        sub.pack(anchor="w", pady=(2, 0))

        # Main Card
        card = tk.Frame(self.root, bg=self.bg_card, bd=1, relief="flat", highlightbackground=self.border_color, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        content = tk.Frame(card, bg=self.bg_card, padx=16, pady=16)
        content.pack(fill="both", expand=True)

        # Destination Folder
        dest_lbl = tk.Label(content, text="Installation Location (No Admin Rights Needed):", font=("Segoe UI", 9, "bold"), bg=self.bg_card, fg=self.fg_white)
        dest_lbl.pack(anchor="w")

        dest_frame = tk.Frame(content, bg=self.bg_card)
        dest_frame.pack(fill="x", pady=(4, 12))

        dest_entry = tk.Entry(
            dest_frame,
            textvariable=self.dest_var,
            bg=self.bg_dark,
            fg=self.fg_white,
            insertbackground=self.fg_white,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.border_color,
            font=("Segoe UI", 8),
        )
        dest_entry.pack(side="left", fill="x", expand=True, ipady=3)

        browse_btn = tk.Button(
            dest_frame,
            text="Browse...",
            command=self._browse_dest,
            bg="#374151",
            fg=self.fg_white,
            activebackground="#4b5563",
            bd=0,
            padx=8,
            font=("Segoe UI", 8),
            cursor="hand2",
        )
        browse_btn.pack(side="right", padx=(6, 0))

        # Checkboxes
        opt_lbl = tk.Label(content, text="Options:", font=("Segoe UI", 9, "bold"), bg=self.bg_card, fg=self.fg_white)
        opt_lbl.pack(anchor="w", pady=(0, 4))

        cb1 = tk.Checkbutton(
            content,
            text="Create Desktop Shortcut",
            variable=self.desktop_var,
            bg=self.bg_card,
            fg=self.fg_white,
            selectcolor=self.bg_dark,
            activebackground=self.bg_card,
            activeforeground=self.fg_white,
            font=("Segoe UI", 9),
        )
        cb1.pack(anchor="w")

        cb2 = tk.Checkbutton(
            content,
            text="Create Start Menu Shortcut",
            variable=self.start_menu_var,
            bg=self.bg_card,
            fg=self.fg_white,
            selectcolor=self.bg_dark,
            activebackground=self.bg_card,
            activeforeground=self.fg_white,
            font=("Segoe UI", 9),
        )
        cb2.pack(anchor="w")

        cb3 = tk.Checkbutton(
            content,
            text="Launch automatically when Windows starts",
            variable=self.startup_var,
            bg=self.bg_card,
            fg=self.fg_white,
            selectcolor=self.bg_dark,
            activebackground=self.bg_card,
            activeforeground=self.fg_white,
            font=("Segoe UI", 9),
        )
        cb3.pack(anchor="w")

        cb4 = tk.Checkbutton(
            content,
            text="Launch Blind-Spotter immediately after install",
            variable=self.launch_var,
            bg=self.bg_card,
            fg=self.fg_white,
            selectcolor=self.bg_dark,
            activebackground=self.bg_card,
            activeforeground=self.fg_white,
            font=("Segoe UI", 9),
        )
        cb4.pack(anchor="w", pady=(0, 8))

        # Progress bar
        self.prog_var = tk.DoubleVar(value=0)
        self.prog_bar = ttk.Progressbar(content, variable=self.prog_var, maximum=100)
        self.prog_bar.pack(fill="x", pady=(4, 4))

        self.status_lbl = tk.Label(content, text="Ready to install.", font=("Segoe UI", 8), bg=self.bg_card, fg=self.fg_muted)
        self.status_lbl.pack(anchor="w")

        # Bottom Buttons
        btn_frame = tk.Frame(self.root, bg=self.bg_dark)
        btn_frame.pack(fill="x", padx=24, pady=(0, 16))

        self.install_btn = tk.Button(
            btn_frame,
            text="Install Now",
            command=self._start_install,
            bg=self.accent_green,
            fg="#064e3b",
            activebackground="#34d399",
            activeforeground="#064e3b",
            bd=0,
            padx=20,
            pady=8,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
        )
        self.install_btn.pack(side="right")

        self.cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            command=self.root.destroy,
            bg="#27272a",
            fg=self.fg_muted,
            activebackground="#3f3f46",
            activeforeground=self.fg_white,
            bd=0,
            padx=14,
            pady=8,
            font=("Segoe UI", 9),
            relief="flat",
            cursor="hand2",
        )
        self.cancel_btn.pack(side="right", padx=(0, 8))

    def _browse_dest(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.dest_var.get(), title="Select Install Folder")
        if chosen:
            self.dest_var.set(chosen)

    def _start_install(self) -> None:
        self.install_btn.config(state="disabled", bg="#4b5563")
        self.cancel_btn.config(state="disabled")

        def worker():
            dest = Path(self.dest_var.get())
            success = perform_installation(
                dest_dir=dest,
                desktop_shortcut=self.desktop_var.get(),
                start_menu_shortcut=self.start_menu_var.get(),
                startup_shortcut=self.startup_var.get(),
                launch_now=self.launch_var.get(),
                progress_callback=self._update_progress,
            )
            if success:
                self.root.after(0, self._on_success)
            else:
                self.root.after(0, self._on_failure)

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress(self, val: int, msg: str) -> None:
        self.root.after(0, lambda: (self.prog_var.set(val), self.status_lbl.config(text=msg)))

    def _on_success(self) -> None:
        self.status_lbl.config(text="Installation completed successfully! You can close this window.", fg=self.accent_green)
        self.install_btn.config(text="Finish", state="normal", bg=self.accent_green, command=self.root.destroy)
        self.cancel_btn.pack_forget()

    def _on_failure(self) -> None:
        self.status_lbl.config(text="Installation failed. Check permissions or close existing instances.", fg="#ef4444")
        self.install_btn.config(text="Retry", state="normal", bg=self.accent_green)
        self.cancel_btn.config(state="normal")

    def run(self) -> None:
        self.root.mainloop()


def main():
    # Handle silent install flags: /S or /silent
    if any(arg.lower() in ("/s", "/silent", "-s", "--silent") for arg in sys.argv[1:]):
        print("Running silent enterprise installation...")
        dest = get_default_install_dir()
        success = perform_installation(
            dest_dir=dest,
            desktop_shortcut=True,
            start_menu_shortcut=True,
            startup_shortcut=True,
            launch_now=False,
            progress_callback=lambda v, m: print(f"[{v}%] {m}"),
        )
        sys.exit(0 if success else 1)

    app = InstallerUI()
    app.run()


if __name__ == "__main__":
    main()
