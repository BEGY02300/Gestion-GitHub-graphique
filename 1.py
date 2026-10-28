from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

from app_api import DesktopApi


def main() -> int:
    try:
        webview = import_module("webview")
    except ImportError:
        message = (
            "La fenetre GitHub Desk a besoin de pywebview. "
            "Lance Lancer.bat pour installer les composants automatiquement."
        )
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Composant manquant", message)
            root.destroy()
        except ImportError:
            print(message)
        return 1

    interface = Path(__file__).with_name("interface.html")
    if not interface.is_file():
        raise FileNotFoundError(f"Interface introuvable : {interface}")

    try:
        webview.create_window(
            "GitHub Desk",
            interface.resolve().as_uri(),
            js_api=DesktopApi(),
            width=1360,
            height=900,
            min_size=(900, 620),
            background_color="#0b1020",
        )
        webview.start(debug=False)
    except Exception as error:
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("GitHub Desk n'a pas pu démarrer", str(error))
            root.destroy()
        except ImportError:
            print(f"GitHub Desk n'a pas pu demarrer : {error}")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
