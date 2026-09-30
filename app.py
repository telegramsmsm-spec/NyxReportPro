#!/usr/bin/env python3
"""NyxReportPro – Professional single-window control panel."""
import asyncio
import threading
import queue
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from tkinter import messagebox

import config
from core.helpers import load_api_keys, load_phones, random_api_key, norm_user
from core.accounts import interactive_login
from core.orchestrator import Orchestrator

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_TITLE = "NyxReportPro"
BG = "#0f1117"
CARD = "#1a1d27"
ACCENT = "#3b82f6"
OK = "#22c55e"
ERR = "#ef4444"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x720")
        self.minsize(960, 640)
        self.configure(fg_color=BG)
        self.log_q: queue.Queue = queue.Queue()
        self.orch: Optional[Orchestrator] = None
        self.loop = None
        self.worker = None
        self._build()
        self.after(120, self._drain_logs)
        self._refresh_stats()

    def _build(self):
        head = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=56)
        head.pack(fill="x")
        head.pack_propagate(False)
        ctk.CTkLabel(head, text="NyxReportPro", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left", padx=20, pady=12)
        self.status_lbl = ctk.CTkLabel(head, text="idle", text_color="#94a3b8")
        self.status_lbl.pack(side="right", padx=20)

        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        left = ctk.CTkFrame(body, fg_color=CARD, width=360, corner_radius=12)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        right = ctk.CTkFrame(body, fg_color=CARD, corner_radius=12)
        right.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(left, text="Campaign", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=16, pady=(16, 6))
        ctk.CTkLabel(left, text="Target (@user or t.me link)", text_color="#94a3b8").pack(anchor="w", padx=16)
        self.target_e = ctk.CTkEntry(left, placeholder_text="@channel_or_group")
        self.target_e.pack(fill="x", padx=16, pady=(2, 8))

        ctk.CTkLabel(left, text="Proxy channels (space / comma)", text_color="#94a3b8").pack(anchor="w", padx=16)
        self.proxy_e = ctk.CTkEntry(left, placeholder_text="@proxych1 @proxych2")
        self.proxy_e.pack(fill="x", padx=16, pady=(2, 8))

        row = ctk.CTkFrame(left, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row, text="Posts").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(row, text="Emails").grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(row, text="Reports/acc").grid(row=0, column=2, sticky="w", padx=8)
        self.posts_e = ctk.CTkEntry(row, width=90)
        self.posts_e.insert(0, str(config.DEFAULT_POSTS))
        self.posts_e.grid(row=1, column=0, pady=4)
        self.emails_e = ctk.CTkEntry(row, width=90)
        self.emails_e.insert(0, str(config.DEFAULT_EMAILS))
        self.emails_e.grid(row=1, column=1, padx=8, pady=4)
        self.rpa_e = ctk.CTkEntry(row, width=90)
        self.rpa_e.insert(0, str(config.DEFAULT_REPORTS_PER_ACC))
        self.rpa_e.grid(row=1, column=2, padx=8, pady=4)

        self.start_btn = ctk.CTkButton(left, text="\u25b6  Start Campaign", fg_color=OK, hover_color="#16a34a",
                                       height=40, command=self._start)
        self.start_btn.pack(fill="x", padx=16, pady=(12, 6))
        self.stop_btn = ctk.CTkButton(left, text="\u25a0  Stop", fg_color=ERR, hover_color="#b91c1c",
                                      height=36, command=self._stop, state="disabled")
        self.stop_btn.pack(fill="x", padx=16, pady=4)

        ctk.CTkFrame(left, fg_color="#2a2f3a", height=1).pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(left, text="Accounts & Sessions", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=16)
        self.stats_lbl = ctk.CTkLabel(left, text="phones: \u2013 | keys: \u2013 | sessions: \u2013", text_color="#94a3b8")
        self.stats_lbl.pack(anchor="w", padx=16, pady=4)

        ctk.CTkButton(left, text="Refresh stats", command=self._refresh_stats, fg_color="#334155").pack(fill="x", padx=16, pady=4)
        ctk.CTkButton(left, text="Login next phone (code)", command=self._login_dialog, fg_color=ACCENT).pack(fill="x", padx=16, pady=4)
        ctk.CTkButton(left, text="Open data folder", command=self._open_data, fg_color="#334155").pack(fill="x", padx=16, pady=4)
        ctk.CTkButton(left, text="Clean temp", command=self._clean_temp, fg_color="#334155").pack(fill="x", padx=16, pady=4)

        tip = (
            "1) data/api_keys.txt \u2192 api_id:api_hash\n"
            "2) data/phones.txt \u2192 one phone per line\n"
            "3) Login each phone once\n"
            "4) Optional smtp.json + proxy channels\n"
            "5) Target \u2192 Start"
        )
        ctk.CTkLabel(left, text=tip, text_color="#64748b", justify="left", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=16, pady=16)

        ctk.CTkLabel(right, text="Live log", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=16, pady=(16, 6))
        self.log_box = ctk.CTkTextbox(right, font=ctk.CTkFont(family="Consolas", size=13))
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._ui_log("NyxReportPro ready. Fill data \u2192 Login \u2192 Start.")

    def _ui_log(self, msg: str):
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")

    def _drain_logs(self):
        try:
            while True:
                m = self.log_q.get_nowait()
                self._ui_log(m)
        except queue.Empty:
            pass
        self.after(120, self._drain_logs)

    def _push(self, msg: str):
        self.log_q.put(msg)

    def _set_status(self, s: str):
        self.after(0, lambda: self.status_lbl.configure(text=s))

    def _refresh_stats(self):
        keys = load_api_keys()
        phones = load_phones()
        sess = list(config.SESSIONS.glob("*.session"))
        self.stats_lbl.configure(text=f"phones: {len(phones)} | api keys: {len(keys)} | sessions: {len(sess)}")

    def _open_data(self):
        import os, subprocess, sys
        path = str(config.DATA)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _clean_temp(self):
        if config.TEMP.exists():
            for p in config.TEMP.iterdir():
                try:
                    if p.is_file():
                        p.unlink()
                except Exception:
                    pass
        self._ui_log("Temp cleaned")

    def _login_dialog(self):
        phones = load_phones()
        keys = load_api_keys()
        if not phones or not keys:
            messagebox.showerror(APP_TITLE, "Need phones + api_keys files")
            return
        target_phone = None
        for ph in phones:
            sp = config.SESSIONS / (ph.replace("+", "p") + ".session")
            if not sp.exists():
                target_phone = ph
                break
        if not target_phone:
            target_phone = phones[0]
        api_id, api_hash = random_api_key(keys)

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Login {target_phone}")
        dlg.geometry("420x260")
        dlg.grab_set()
        ctk.CTkLabel(dlg, text=f"Phone: {target_phone}\nAPI: {api_id}", justify="left").pack(padx=16, pady=12)
        ctk.CTkLabel(dlg, text="Code from Telegram").pack(anchor="w", padx=16)
        code_e = ctk.CTkEntry(dlg)
        code_e.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(dlg, text="2FA password (if any)").pack(anchor="w", padx=16)
        pw_e = ctk.CTkEntry(dlg, show="*")
        pw_e.pack(fill="x", padx=16, pady=4)
        status = ctk.CTkLabel(dlg, text="")
        status.pack(pady=4)

        def do_login():
            status.configure(text="Working\u2026")

            async def code_cb():
                return code_e.get().strip()

            async def pw_cb():
                return pw_e.get().strip()

            async def run():
                try:
                    ok, msg = await interactive_login(target_phone, api_id, api_hash, code_cb, pw_cb)
                    self.after(0, lambda: status.configure(text=msg))
                    self.after(0, self._refresh_stats)
                    self._push(f"Login {target_phone}: {msg}")
                    if ok:
                        self.after(800, dlg.destroy)
                except Exception as e:
                    self.after(0, lambda: status.configure(text=str(e)))
                    self._push(f"Login error: {e}")

            threading.Thread(target=lambda: asyncio.run(run()), daemon=True).start()

        ctk.CTkButton(dlg, text="Send / Confirm", command=do_login, fg_color=ACCENT).pack(pady=12)

        async def pre():
            from telethon import TelegramClient
            path = str(config.SESSIONS / target_phone.replace("+", "p"))
            c = TelegramClient(path, api_id, api_hash)
            await c.connect()
            if not await c.is_user_authorized():
                await c.send_code_request(target_phone)
                self._push(f"Code requested \u2192 {target_phone}")
            await c.disconnect()

        threading.Thread(target=lambda: asyncio.run(pre()), daemon=True).start()

    def _start(self):
        target = self.target_e.get().strip()
        if not target:
            messagebox.showwarning(APP_TITLE, "Enter target")
            return
        raw_px = self.proxy_e.get().replace(",", " ").split()
        proxy_channels = [norm_user(x) for x in raw_px if x.strip()]
        try:
            posts = int(self.posts_e.get())
            emails = int(self.emails_e.get())
            rpa = int(self.rpa_e.get())
        except ValueError:
            messagebox.showwarning(APP_TITLE, "Posts / Emails / Reports must be numbers")
            return

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._set_status("running")

        def thread_main():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop
            self.orch = Orchestrator(on_log=self._push, on_status=self._set_status)
            try:
                loop.run_until_complete(self.orch.run(target, proxy_channels, posts, emails, rpa))
            except Exception as e:
                self._push(f"Fatal: {e}")
                self._set_status("error")
            finally:
                self.after(0, lambda: self.start_btn.configure(state="normal"))
                self.after(0, lambda: self.stop_btn.configure(state="disabled"))
                self.after(0, self._refresh_stats)

        self.worker = threading.Thread(target=thread_main, daemon=True)
        self.worker.start()

    def _stop(self):
        if self.orch:
            self.orch.request_stop()
        self._push("Stop signal sent")


def main():
    config.DATA.mkdir(parents=True, exist_ok=True)
    config.SESSIONS.mkdir(parents=True, exist_ok=True)
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
