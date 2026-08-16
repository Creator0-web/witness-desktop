import sys as _sys, os as _os
_base = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
for _sub in ("core", "character", "shared", "_archive"):
    _p = _os.path.join(_base, _sub)
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

"""Standalone chat test. Run: python chattest.py
If this works, the chat module is fine and we just need
to transplant this code into main.py cleanly.
"""
import tkinter as tk
import threading
import chat

root = tk.Tk()
root.title("Chat Test")
root.geometry("400x300")
root.configure(bg="#111")

history = []

log = tk.Text(root, wrap="word", bg="#111", fg="#ddd", height=12,
              state="disabled", font=("Segoe UI", 10))
log.pack(fill="both", expand=True, padx=8, pady=8)

entry = tk.Entry(root, bg="#222", fg="#ddd", font=("Segoe UI", 10),
                 insertbackground="#ddd")
entry.pack(fill="x", padx=8, pady=(0, 8))
entry.focus_set()


def add_msg(who, text):
    log.config(state="normal")
    log.insert("end", f"{who}: {text}\n")
    log.config(state="disabled")
    log.see("end")


def send(_=None):
    text = entry.get().strip()
    if not text:
        return
    entry.delete(0, "end")
    add_msg("You", text)
    history.append({"role": "user", "content": text})

    def worker():
        reply = chat.reply(history)
        history.append({"role": "assistant", "content": reply})
        root.after(0, lambda: add_msg("Witness", reply))

    threading.Thread(target=worker, daemon=True).start()


entry.bind("<Return>", send)
tk.Button(root, text="Send", command=send, bg="#333", fg="#ddd").pack(pady=(0, 8))

root.mainloop()
