import tkinter as tk
from tkinter import filedialog
import os

# --- カラー定義 ---
BG_PANEL  = "#32302F"
FG_MAIN   = "#e5e7eb"
SEARCH_BG = "#3d3b3a"


class SettingsPage(tk.Frame):
    """設定タブ"""

    def __init__(
        self,
        master,
        api_key_var: tk.StringVar,
        steam_id_var: tk.StringVar,
        steam_path_var: tk.StringVar,
        output_path_var: tk.StringVar,
        save_config_callback=None,
        *args,
        **kwargs
    ):
        super().__init__(master, bg=BG_PANEL, *args, **kwargs)

        self.api_key = api_key_var
        self.steam_id = steam_id_var
        self.steam_path = steam_path_var
        self.output_path = output_path_var
        self.save_config_callback = save_config_callback

        self._build_layout()
        self._setup_trace()

    # =============================================================================
    # ⭐Entry
    # =============================================================================
    def _rounded_entry(self, parent, textvariable, width_ratio=1.0,
                       right_icon=None, right_command=None, icon_size=20):

        # アイコン用の安全余白
        icon_area = icon_size + 18     

        container = tk.Frame(parent, bg=BG_PANEL)
        container.pack(side="left", fill="x", expand=(width_ratio == 1.0))

        canvas = tk.Canvas(
            container,
            height=32,
            bg=BG_PANEL,
            highlightthickness=0,
            bd=0
        )
        canvas.pack(fill="x", expand=True)

        entry = tk.Entry(
            canvas,
            textvariable=textvariable,
            bg=SEARCH_BG,
            fg="#ffffff",
            relief="flat",
            insertbackground="#ffffff",
            bd=0
        )

        canvas._is_redrawing = False

        def _redraw():
            if canvas._is_redrawing:
                return
            canvas._is_redrawing = True

            canvas.delete("all")

            pw = parent.winfo_width() or 300
            w = int(pw * width_ratio)
            h = 32
            r = 16

            canvas.config(width=w)

            offset = 2

            # 丸背景
            canvas.create_oval(0, offset, h, h + offset,
                               fill=SEARCH_BG, outline=SEARCH_BG)
            canvas.create_oval(w - h, offset, w, h + offset,
                               fill=SEARCH_BG, outline=SEARCH_BG)
            canvas.create_rectangle(r, offset, w - r, h + offset,
                                    fill=SEARCH_BG, outline=SEARCH_BG)

            # Entry
            canvas.create_window(
                (w - icon_area) // 2,
                h // 2 + offset,
                window=entry,
                width=w - icon_area - 10,
                height=h - 12
            )

            # アイコン
            if right_icon:
                icon_id = canvas.create_text(
                    w - icon_area // 2,
                    h // 2 + offset,
                    text=right_icon,
                    fill="#e5e7eb",
                    font=("NotoSansJP", icon_size, "bold")
                )

                def enter(_): canvas.itemconfig(icon_id, fill="#ffffff")
                def leave(_): canvas.itemconfig(icon_id, fill="#e5e7eb")
                def click(_): right_command() if right_command else None

                canvas.tag_bind(icon_id, "<Enter>", enter)
                canvas.tag_bind(icon_id, "<Leave>", leave)
                canvas.tag_bind(icon_id, "<Button-1>", click)

            canvas._is_redrawing = False

        def _safe_configure(_):
            self.after(5, _redraw)

        parent.bind("<Configure>", _safe_configure)
        container.bind("<Configure>", _safe_configure)

        return entry


    # =============================================================================
    # UI 本体
    # =============================================================================
    def _build_layout(self):

        # タイトル
        tk.Label(
            self,
            text="Steam API 設定",
            bg=BG_PANEL,
            fg="#ffffff",
            font=("NotoSansJP", 16, "bold")
        ).pack(anchor="w", padx=20, pady=(20, 6))

        # 説明
        tk.Label(
            self,
            text="Steam Web API のキーと SteamID64 を入力し、CSV の保存先を指定してください。\n秘密の実績説明を補完する場合は Steam フォルダも指定できます。　※ 設定は自動保存されます。",
            bg=BG_PANEL,
            fg="#d1d5db",
            wraplength=780,
            justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 16))

        # ----------------------------
        # フォーム
        # ----------------------------
        form = tk.Frame(self, bg=BG_PANEL)
        form.pack(fill="x", padx=20)

        # --- API Key（60%）
        row1 = tk.Frame(form, bg=BG_PANEL)
        row1.pack(fill="x", pady=6)

        tk.Label(row1, text="API Key：", bg=BG_PANEL, fg=FG_MAIN,
                 width=14, anchor="e").pack(side="left")

        self._rounded_entry(row1, self.api_key, width_ratio=0.6).pack(side="left")

        # --- SteamID64（60%）
        row2 = tk.Frame(form, bg=BG_PANEL)
        row2.pack(fill="x", pady=6)

        tk.Label(row2, text="SteamID64：", bg=BG_PANEL, fg=FG_MAIN,
                 width=14, anchor="e").pack(side="left")

        self._rounded_entry(row2, self.steam_id, width_ratio=0.6).pack(side="left")

        # --- Steam フォルダ（100%）＋ 📁 アイコン
        row2b = tk.Frame(form, bg=BG_PANEL)
        row2b.pack(fill="x", pady=6)

        tk.Label(row2b, text="Steamフォルダ：", bg=BG_PANEL, fg=FG_MAIN,
                 width=14, anchor="e").pack(side="left")

        steam_entry_frame = tk.Frame(row2b, bg=BG_PANEL)
        steam_entry_frame.pack(side="left", fill="x", expand=True)

        self._rounded_entry(
            steam_entry_frame,
            self.steam_path,
            width_ratio=1.0,
            right_icon="📁",
            right_command=self._browse_steam_path
        )

        # Steam 状態（stats フォルダ）
        steam_stat = tk.Frame(form, bg=BG_PANEL)
        steam_stat.pack(fill="x", pady=(0, 6))

        tk.Label(steam_stat, text="", bg=BG_PANEL, fg=FG_MAIN,
                 width=14, anchor="e").pack(side="left")

        stat_inner = tk.Frame(steam_stat, bg=BG_PANEL)
        stat_inner.pack(side="left", fill="x", expand=True)

        self._steam_status_value = tk.Label(
            stat_inner,
            text="",
            bg=BG_PANEL,
            fg="#9ca3af",
            font=("NotoSansJP", 9),
            anchor="w",
            wraplength=780,
            justify="left"
        )
        self._steam_status_value.pack(side="left", fill="x", expand=True)

        btns = tk.Frame(stat_inner, bg=BG_PANEL)
        btns.pack(side="right")

        open_link = tk.Label(
            btns, text="開く",
            bg=BG_PANEL, fg="#93c5fd",
            font=("NotoSansJP", 10, "underline"),
            cursor="hand2"
        )
        open_link.pack(side="left", padx=(8, 0))
        open_link.bind("<Button-1>", lambda e: self._open_steam_folder())

        stats_link = tk.Label(
            btns, text="stats",
            bg=BG_PANEL, fg="#93c5fd",
            font=("NotoSansJP", 10, "underline"),
            cursor="hand2"
        )
        stats_link.pack(side="left", padx=(10, 0))
        stats_link.bind("<Button-1>", lambda e: self._open_stats_folder())

        self.after(100, self._update_steam_status)

        # --- 出力先（100%）＋ 📁 アイコン
        row3 = tk.Frame(form, bg=BG_PANEL)
        row3.pack(fill="x", pady=6)

        tk.Label(row3, text="出力先CSV：", bg=BG_PANEL, fg=FG_MAIN,
                 width=14, anchor="e").pack(side="left")

        entry_frame = tk.Frame(row3, bg=BG_PANEL)
        entry_frame.pack(side="left", fill="x", expand=True)

        self._rounded_entry(
            entry_frame,
            self.output_path,
            width_ratio=1.0,
            right_icon="📁",
            right_command=self._browse_output_path
        )


        # ---------------------------------------------------------
        # 下部説明
        # ---------------------------------------------------------
        info = tk.Frame(self, bg=BG_PANEL)
        info.pack(fill="x", padx=30, pady=(10, 20))

        # --- API Key 説明 ---
        title_row = tk.Frame(info, bg=BG_PANEL)
        title_row.pack(anchor="w", pady=(0, 8))

        tk.Label(
            title_row, text="Steam Web APIキーを取得 ( ",
            bg=BG_PANEL, fg="#e5e7eb", font=("NotoSansJP", 12, "bold")
        ).pack(side="left")

        link1 = tk.Label(
            title_row,
            text="https://steamcommunity.com/dev/apikey",
            bg=BG_PANEL,
            fg="#93c5fd",
            font=("NotoSansJP", 11, "underline"),
            cursor="hand2"
        )
        link1.pack(side="left")
        link1.bind("<Button-1>", lambda e: os.startfile("https://steamcommunity.com/dev/apikey"))

        tk.Label(
            title_row, text=" )",
            bg=BG_PANEL, fg="#e5e7eb", font=("NotoSansJP", 12, "bold")
        ).pack(side="left")

        tk.Label(info, text="1. Steamアカウントでログイン。",
                 bg=BG_PANEL, fg=FG_MAIN, font=("NotoSansJP", 10)).pack(anchor="w")

        tk.Label(info, text="2. Domain に [localhost] と入力。",
                 bg=BG_PANEL, fg=FG_MAIN, font=("NotoSansJP", 10)).pack(anchor="w")

        tk.Label(info, text="3. 「Register」→ API Key が発行される。",
                 bg=BG_PANEL, fg=FG_MAIN,
                 font=("NotoSansJP", 10)).pack(anchor="w", pady=(0, 14))

        # --- SteamID 説明 ---
        id_title = tk.Frame(info, bg=BG_PANEL)
        id_title.pack(anchor="w", pady=(6, 8))

        tk.Label(
            id_title, text="SteamID64 を確認 ( ",
            bg=BG_PANEL, fg="#ffffff", font=("NotoSansJP", 12, "bold")
        ).pack(side="left")

        link2 = tk.Label(
            id_title,
            text="https://steamid.io/",
            bg=BG_PANEL,
            fg="#93c5fd",
            font=("NotoSansJP", 11, "underline"),
            cursor="hand2"
        )
        link2.pack(side="left")
        link2.bind("<Button-1>", lambda e: os.startfile("https://steamid.io/"))

        tk.Label(
            id_title, text=" )",
            bg=BG_PANEL, fg="#ffffff", font=("NotoSansJP", 12, "bold")
        ).pack(side="left")

        tk.Label(
            info,
            text="1. プロフィールURLを確認する。（例：https://steamcommunity.com/id/ユーザー名/）",
            bg=BG_PANEL, fg=FG_MAIN,
            font=("NotoSansJP", 10),
            wraplength=780,
            justify="left"
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            info,
            text="2. URL を steamid.io に貼り付けて Lookup を実行する。",
            bg=BG_PANEL, fg=FG_MAIN,
            font=("NotoSansJP", 10)
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            info,
            text="3. 「SteamID64（17桁の数字）」を確認。",
            bg=BG_PANEL, fg=FG_MAIN,
            font=("NotoSansJP", 10)
        ).pack(anchor="w")

    # =============================================================================
    # 自動保存
    # =============================================================================
    def _setup_trace(self):
        def _on_change(*_):
            if self.save_config_callback:
                self.save_config_callback()

        self.api_key.trace_add("write", _on_change)
        self.steam_id.trace_add("write", _on_change)
        self.steam_path.trace_add("write", _on_change)
        self.output_path.trace_add("write", _on_change)

        # Steam パスの状態表示
        self.steam_path.trace_add("write", lambda *_: self._update_steam_status())

    # =============================================================================
    # Steam フォルダ
    # =============================================================================
    def _browse_steam_path(self):
        current = self.steam_path.get().strip()
        initial_dir = current if current and os.path.isdir(current) else "C:\\"
        path = filedialog.askdirectory(
            title="Steam フォルダを選択",
            initialdir=initial_dir,
            mustexist=True,
        )
        if path:
            self.steam_path.set(path)
            if self.save_config_callback:
                self.save_config_callback()

    def _open_folder(self, path: str):
        try:
            if path and os.path.exists(path):
                os.startfile(path)
        except Exception:
            pass

    def _steam_stats_dir(self) -> str:
        root = self.steam_path.get().strip()
        if not root:
            return ""
        return os.path.join(root, "appcache", "stats")

    def _update_steam_status(self):
        root = self.steam_path.get().strip()
        stats = self._steam_stats_dir()

        if not root:
            msg = "未設定（ローカルスキーマ補完を使う場合は Steam フォルダを指定）"
        elif not os.path.isdir(root):
            msg = "Steam フォルダが見つかりません"
        else:
            if os.path.isdir(stats):
                msg = f"OK: {stats}"
            else:
                msg = f"Steam は見つかったが stats フォルダがありません: {stats}"

        if hasattr(self, "_steam_status_value"):
            self._steam_status_value.configure(text=msg)

    def _open_steam_folder(self):
        self._open_folder(self.steam_path.get().strip())

    def _open_stats_folder(self):
        self._open_folder(self._steam_stats_dir())

    # =============================================================================
    # ファイルダイアログ
    # =============================================================================
    def _browse_output_path(self):
        current = self.output_path.get().strip()

        initial_dir = os.path.dirname(current) if current else "C:\\"
        initial_file = os.path.basename(current) if current else "steam_achievements_jp.csv"

        path = filedialog.asksaveasfilename(
            title="CSV 出力先を選択",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialdir=initial_dir,
            initialfile=initial_file,
        )

        if path:
            self.output_path.set(path)
            if self.save_config_callback:
                self.save_config_callback()
