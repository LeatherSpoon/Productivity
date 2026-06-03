import time
import math
import threading
from PIL import Image, ImageDraw
import pystray
import pyperclip
from pynput import keyboard

# ---------------------------------------------------------------------------
# Snippets — add your own here
# ---------------------------------------------------------------------------
SNIPPETS = {
    "||date":         lambda: time.strftime("%m-%d-%Y"),
    "||shrug":        lambda: r"¯\_(ツ)_/¯",
    "||p1":           lambda: "This is a massive block of boilerplate text you use constantly.",
    "||lorem":        lambda: "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
    "||PF":           lambda: "1853689",
    "bc":             lambda: "because",
    "btw":            lambda: "by the way",
    "tomo":           lambda: "tomorrow",
    "occur":          lambda: "occurred",
    "seperate":       lambda: "separate",
    "definately":     lambda: "definitely",
    "definitly":      lambda: "definitely",
    "maintainance":   lambda: "maintenance",
    "recieve":        lambda: "receive",
    "simultan":       lambda: "simultaneous",
    "characteris":    lambda: "characteristic",
    "recommendation": lambda: "recommendation",
    "recomendation":  lambda: "recommendation",
    "infrast":        lambda: "infrastructure",
    "enviro":         lambda: "environment",
    "straightf":      lambda: "straightforward",
    "furtherm":       lambda: "furthermore",

}

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
paused    = False
expanding = threading.Event()   # set() = expansion in progress; listener ignores keypresses
max_buffer_len = max(len(k) for k in SNIPPETS.keys())
key_buffer: list[str] = []
controller = keyboard.Controller()

PASSTHROUGH_CHARS = set(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789|_@."
)

# ---------------------------------------------------------------------------
# Keyboard logic
# ---------------------------------------------------------------------------
def on_press(key):
    global key_buffer

    # Ignore all keypresses while paused or while we're typing an expansion
    if paused or expanding.is_set():
        return

    try:
        if hasattr(key, "char") and key.char is not None:
            char = key.char
        elif key == keyboard.Key.backspace:
            if key_buffer:
                key_buffer.pop()
            return
        else:
            key_buffer.clear()
            return

        if char not in PASSTHROUGH_CHARS:
            key_buffer.clear()
            return

        key_buffer.append(char)
        if len(key_buffer) > max_buffer_len:
            key_buffer.pop(0)

        current_str = "".join(key_buffer)
        for shortcut, expansion_fn in SNIPPETS.items():
            if current_str.endswith(shortcut):
                # Set the flag HERE, before the thread starts, so no further
                # keypresses can sneak through between t.start() and the thread
                # actually running.
                expanding.set()
                t = threading.Thread(
                    target=trigger_expansion,
                    args=(shortcut, expansion_fn()),
                    daemon=True,
                )
                t.start()
                break

    except Exception as e:
        print(f"[keyboard] Error: {e}")


def trigger_expansion(shortcut: str, expansion: str):
    global key_buffer
    # expanding was already set by on_press before this thread started
    key_buffer.clear()

    time.sleep(0.05)      # let the triggering keypress fully land

    for _ in range(len(shortcut)):
        controller.press(keyboard.Key.backspace)
        controller.release(keyboard.Key.backspace)
        time.sleep(0.02)

    time.sleep(0.05)      # let backspaces settle

    # Paste via clipboard rather than simulating individual keystrokes.
    # Per-character SendInput is too fast for apps like Notepad that process
    # raw WM_CHAR messages one at a time — characters get dropped. Pasting
    # hands the entire string to the app in one shot.
    try:
        saved_clip = pyperclip.paste()
    except Exception:
        saved_clip = ""
    pyperclip.copy(expansion)
    time.sleep(0.02)
    with controller.pressed(keyboard.Key.ctrl):
        controller.tap('v')
    time.sleep(0.1)       # let the paste land before restoring the clipboard
    try:
        pyperclip.copy(saved_clip)
    except Exception:
        pass

    key_buffer.clear()
    expanding.clear()     # listener is open again


# ---------------------------------------------------------------------------
# System-tray icon
# ---------------------------------------------------------------------------
ICON_SIZE = 64

def make_icon(is_paused: bool) -> Image.Image:
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (220, 50, 50) if is_paused else (50, 200, 80)
    cx, cy = ICON_SIZE / 2, ICON_SIZE / 2
    outer_r, inner_r = ICON_SIZE / 2 - 2, ICON_SIZE / 4 - 1
    points = []
    for i in range(10):
        angle = math.radians(i * 36 - 90)
        r = outer_r if i % 2 == 0 else inner_r
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=color)
    return img


def tray_label(is_paused: bool) -> str:
    return "Text Expander — PAUSED" if is_paused else "Text Expander — Active"


def toggle_pause(icon, item):
    global paused
    paused = not paused
    icon.icon = make_icon(paused)
    icon.title = tray_label(paused)
    print(f"[tray] {'Paused' if paused else 'Resumed'}")


def quit_app(icon, item):
    print("[tray] Quitting…")
    icon.stop()


def run_tray():
    icon = pystray.Icon(
        name="text_expander",
        icon=make_icon(paused),
        title=tray_label(paused),
        menu=pystray.Menu(
            pystray.MenuItem(lambda item: "Resume" if paused else "Pause", toggle_pause),
            pystray.MenuItem("Quit", quit_app),
        ),
    )
    icon.run()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Text Expander running.")
    print("  • Right-click the tray icon to Pause / Resume / Quit.")
    print("  • Snippets:", ", ".join(SNIPPETS.keys()))

    tray_thread = threading.Thread(target=run_tray, daemon=True)
    tray_thread.start()

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()
