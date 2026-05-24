import copy
import datetime
import os
import platform
import random
import re
import shlex
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from tkinter import messagebox, simpledialog


def rounded_rectangle(canvas, x1, y1, x2, y2, radius=16, **kwargs):
    radius = min(radius, abs(x2 - x1) // 2, abs(y2 - y1) // 2)
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class ReadableHTMLParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.parts = []
        self.links = []
        self.skip = False
        self.current_href = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            self.skip = True
            return
        if tag in ("p", "div", "section", "article", "header", "footer", "br", "li", "tr", "h1", "h2", "h3"):
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")
        if tag == "a" and attrs.get("href"):
            self.current_href = urllib.parse.urljoin(self.base_url, attrs["href"])

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip = False
        if tag == "a":
            self.current_href = None
        if tag in ("p", "div", "li", "tr", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip:
            return
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        self.parts.append(text + " ")
        if self.current_href and text:
            if len(self.links) < 40:
                self.links.append((text[:80], self.current_href))

    def readable_text(self):
        text = "".join(self.parts)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def fetch_url(address, timeout=12, limit=350000):
    if "://" not in address:
        address = "https://" + address
    parsed = urllib.parse.urlparse(address)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Somente HTTP e HTTPS sao suportados.")
    request = urllib.request.Request(
        address,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 MintTk/1.0",
            "Accept": "text/html,text/plain,application/xhtml+xml,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type", "")
        raw = response.read(limit + 1)
    truncated = len(raw) > limit
    raw = raw[:limit]
    charset_match = re.search(r"charset=([\w.-]+)", content_type, re.I)
    charset = charset_match.group(1) if charset_match else "utf-8"
    try:
        body = raw.decode(charset, errors="replace")
    except LookupError:
        body = raw.decode("utf-8", errors="replace")
    if "html" in content_type.lower() or "<html" in body[:1000].lower():
        parser = ReadableHTMLParser(final_url)
        parser.feed(body)
        text = parser.readable_text()
        links = parser.links
    else:
        text = body
        links = []
    if truncated:
        text += "\n\n[conteudo truncado para manter o app responsivo]"
    return {
        "url": final_url,
        "content_type": content_type or "desconhecido",
        "text": text,
        "links": links,
        "bytes": len(raw),
    }


class IconCanvas(tk.Canvas):
    def __init__(self, master, os_app, spec, size=44, command=None):
        self.os = os_app
        self.spec = spec
        self.size = size
        self.command = command
        super().__init__(master, width=size, height=size, highlightthickness=0, bd=0)
        self.bind("<Button-1>", self.activate)
        self.bind("<Enter>", lambda _event: self.draw(True))
        self.bind("<Leave>", lambda _event: self.draw(False))
        self.draw(False)

    def activate(self, _event=None):
        if self.command:
            self.command()

    def draw(self, hover=False):
        self.delete("all")
        theme = self.os.theme
        fill = self.spec.get("color", theme["accent"])
        bg = self.os.mix(fill, "#ffffff", 0.12 if self.os.theme_name == "dark" else 0.22)
        if hover:
            bg = self.os.mix(fill, "#ffffff", 0.28)
        rounded_rectangle(self, 3, 3, self.size - 3, self.size - 3, 12, fill=bg, outline=self.os.mix(fill, "#000000", 0.2), width=1)
        self.create_text(
            self.size // 2,
            self.size // 2,
            text=self.spec.get("icon", "●"),
            fill=self.spec.get("icon_fg", "#ffffff"),
            font=("Segoe UI Symbol", max(15, self.size // 2), "bold"),
        )


class DesktopIcon(tk.Canvas):
    def __init__(self, master, os_app, spec, command):
        self.os = os_app
        self.spec = spec
        self.command = command
        super().__init__(master, width=98, height=78, highlightthickness=0, bd=0, bg=os_app.wallpaper)
        self.bind("<Button-1>", self.activate)
        self.bind("<Double-Button-1>", self.activate)
        self.bind("<Enter>", lambda _event: self.draw(True))
        self.bind("<Leave>", lambda _event: self.draw(False))
        self.draw(False)

    def activate(self, _event=None):
        self.command()

    def draw(self, hover=False):
        self.delete("all")
        self.configure(bg=self.os.wallpaper)
        if hover:
            rounded_rectangle(self, 2, 2, 96, 76, 12, fill=self.os.mix(self.os.theme["accent"], "#ffffff", 0.12), outline="")
        fill = self.spec.get("color", self.os.theme["accent"])
        rounded_rectangle(self, 26, 5, 72, 51, 12, fill=fill, outline=self.os.mix(fill, "#000000", 0.25))
        self.create_text(49, 29, text=self.spec.get("icon", "●"), fill="#ffffff", font=("Segoe UI Symbol", 22, "bold"))
        self.create_text(
            49,
            64,
            text=self.spec.get("short", self.spec["name"]),
            fill="#ffffff",
            font=("Segoe UI", 9),
            width=92,
        )


class VirtualFileSystem:
    def __init__(self):
        self.root = {
            "type": "dir",
            "children": {
                "Home": {
                    "type": "dir",
                    "children": {
                        "Documents": {
                            "type": "dir",
                            "children": {
                                "welcome.txt": {
                                    "type": "file",
                                    "content": (
                                        "Cinnix 1.0\n\n"
                                        "Este ambiente roda em Python/Tkinter e o navegador acessa HTTP/HTTPS reais.\n"
                                        "O terminal, o editor e o gerenciador de arquivos usam o "
                                        "mesmo sistema de arquivos virtual."
                                    ),
                                },
                                "todo.txt": {
                                    "type": "file",
                                    "content": "- Explorar o menu\n- Testar comandos no terminal\n- Alternar tema claro/escuro\n",
                                },
                            },
                        },
                        "Desktop": {
                            "type": "dir",
                            "children": {
                                "README.txt": {
                                    "type": "file",
                                    "content": "Bem-vindo ao desktop Cinnix.",
                                }
                            },
                        },
                        "Downloads": {"type": "dir", "children": {}},
                        "Pictures": {"type": "dir", "children": {}},
                    },
                },
                "System": {
                    "type": "dir",
                    "children": {
                        "about.txt": {
                            "type": "file",
                            "content": "Cinnix Desktop 1.0\nKernel: tk-6.6\nShell: cinnixsh",
                        },
                        "themes.conf": {
                            "type": "file",
                            "content": "themes=Luminix Light,Luminix Dark\naccent=green\n",
                        },
                    },
                },
                "Trash": {"type": "dir", "children": {}},
            },
        }

    def normalize(self, path, cwd="/Home"):
        if not path:
            path = cwd
        if not path.startswith("/"):
            path = cwd.rstrip("/") + "/" + path
        parts = []
        for part in path.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(part)
        return "/" + "/".join(parts)

    def split_parent(self, path, cwd="/Home"):
        path = self.normalize(path, cwd)
        if path == "/":
            raise ValueError("Nao e possivel alterar a raiz.")
        parent, name = path.rsplit("/", 1)
        return parent or "/", name

    def node(self, path, cwd="/Home"):
        path = self.normalize(path, cwd)
        if path == "/":
            return self.root
        node = self.root
        for part in path.strip("/").split("/"):
            if node["type"] != "dir" or part not in node["children"]:
                raise FileNotFoundError(path)
            node = node["children"][part]
        return node

    def exists(self, path, cwd="/Home"):
        try:
            self.node(path, cwd)
            return True
        except FileNotFoundError:
            return False

    def is_dir(self, path, cwd="/Home"):
        return self.node(path, cwd)["type"] == "dir"

    def list_dir(self, path, cwd="/Home"):
        node = self.node(path, cwd)
        if node["type"] != "dir":
            raise NotADirectoryError(path)
        rows = []
        for name, item in sorted(node["children"].items(), key=lambda pair: (pair[1]["type"] != "dir", pair[0].lower())):
            rows.append((name, item["type"]))
        return rows

    def read_file(self, path, cwd="/Home"):
        node = self.node(path, cwd)
        if node["type"] != "file":
            raise IsADirectoryError(path)
        return node.get("content", "")

    def write_file(self, path, content, cwd="/Home"):
        parent, name = self.split_parent(path, cwd)
        directory = self.node(parent)
        if directory["type"] != "dir":
            raise NotADirectoryError(parent)
        directory["children"][name] = {"type": "file", "content": content}
        return self.normalize(path, cwd)

    def mkdir(self, path, cwd="/Home"):
        parent, name = self.split_parent(path, cwd)
        directory = self.node(parent)
        if name in directory["children"]:
            raise FileExistsError(path)
        directory["children"][name] = {"type": "dir", "children": {}}
        return self.normalize(path, cwd)

    def touch(self, path, cwd="/Home"):
        parent, name = self.split_parent(path, cwd)
        directory = self.node(parent)
        if name not in directory["children"]:
            directory["children"][name] = {"type": "file", "content": ""}
        elif directory["children"][name]["type"] != "file":
            raise IsADirectoryError(path)
        return self.normalize(path, cwd)

    def delete(self, path, cwd="/Home"):
        parent, name = self.split_parent(path, cwd)
        directory = self.node(parent)
        if name not in directory["children"]:
            raise FileNotFoundError(path)
        del directory["children"][name]

    def count_items(self):
        counts = {"files": 0, "folders": 0}

        def walk(node):
            if node["type"] == "file":
                counts["files"] += 1
                return
            counts["folders"] += 1
            for child in node["children"].values():
                walk(child)

        walk(self.root)
        return counts


class InternalWindow:
    def __init__(self, wm, title, app_id, width=720, height=460, x=None, y=None):
        self.wm = wm
        self.app_id = app_id
        self.title = title
        self.minimized = False
        self.maximized = False
        self.closed = False
        self.saved_geometry = None
        self.drag_offset = (0, 0)

        self.frame = tk.Frame(wm.desktop, bd=0, relief="flat", highlightthickness=1)
        self.titlebar = tk.Frame(self.frame, height=34)
        self.titlebar.pack(fill="x")
        spec = wm.os.get_app_spec(app_id) or {"icon": "●"}
        self.icon_label = tk.Label(self.titlebar, text=spec.get("icon", "●"), width=3)
        self.icon_label.pack(side="left")
        self.title_label = tk.Label(self.titlebar, text=title, anchor="w", padx=6)
        self.title_label.pack(side="left", fill="x", expand=True)
        self.min_btn = tk.Button(self.titlebar, text="−", width=3, command=self.minimize)
        self.max_btn = tk.Button(self.titlebar, text="□", width=3, command=self.toggle_maximize)
        self.close_btn = tk.Button(self.titlebar, text="×", width=3, command=self.close)
        self.close_btn.pack(side="right")
        self.max_btn.pack(side="right")
        self.min_btn.pack(side="right")
        self.content = tk.Frame(self.frame, bd=0)
        self.content.pack(fill="both", expand=True)

        offset = len(wm.windows) * 26
        self.x = x if x is not None else 80 + offset
        self.y = y if y is not None else 50 + offset
        self.width = width
        self.height = height
        self.frame.place(x=self.x, y=self.y, width=self.width, height=self.height)

        for widget in (self.frame, self.titlebar, self.title_label, self.icon_label):
            widget.bind("<Button-1>", self.focus)
        self.titlebar.bind("<ButtonPress-1>", self.start_drag)
        self.title_label.bind("<ButtonPress-1>", self.start_drag)
        self.icon_label.bind("<ButtonPress-1>", self.start_drag)
        self.titlebar.bind("<B1-Motion>", self.drag)
        self.title_label.bind("<B1-Motion>", self.drag)
        self.icon_label.bind("<B1-Motion>", self.drag)
        self.titlebar.bind("<Double-Button-1>", lambda _event: self.toggle_maximize())
        self.title_label.bind("<Double-Button-1>", lambda _event: self.toggle_maximize())
        self.apply_theme()

    def apply_theme(self):
        theme = self.wm.os.theme
        self.frame.configure(bg=theme["window"], highlightbackground=theme["border"])
        self.titlebar.configure(bg=theme["titlebar"])
        self.icon_label.configure(bg=theme["titlebar"], fg=theme["accent"], font=("Segoe UI Symbol", 13, "bold"))
        self.title_label.configure(bg=theme["titlebar"], fg=theme["title_fg"], font=("Segoe UI", 9, "bold"))
        self.content.configure(bg=theme["window"])
        for button in (self.min_btn, self.max_btn, self.close_btn):
            button.configure(
                bg=theme["button"],
                fg=theme["fg"],
                activebackground=theme["accent"],
                activeforeground=theme["accent_fg"],
                bd=0,
                relief="flat",
                font=("Segoe UI", 10, "bold"),
            )

    def set_title(self, title):
        self.title = title
        self.title_label.configure(text=title)
        self.wm.refresh_taskbar()

    def focus(self, _event=None):
        self.wm.focus(self)

    def start_drag(self, event):
        if self.maximized:
            return
        self.focus()
        self.drag_offset = (event.x, event.y)

    def drag(self, event):
        if self.maximized:
            return
        dx, dy = self.drag_offset
        new_x = self.frame.winfo_x() + event.x - dx
        new_y = self.frame.winfo_y() + event.y - dy
        max_x = max(0, self.wm.desktop.winfo_width() - 120)
        max_y = max(0, self.wm.desktop.winfo_height() - 60)
        self.x = min(max(new_x, 0), max_x)
        self.y = min(max(new_y, 0), max_y)
        self.frame.place_configure(x=self.x, y=self.y)

    def minimize(self):
        self.minimized = True
        self.frame.place_forget()
        self.wm.refresh_taskbar()

    def restore(self):
        self.minimized = False
        self.frame.place(x=self.x, y=self.y, width=self.width, height=self.height)
        self.focus()
        self.wm.refresh_taskbar()

    def toggle_maximize(self):
        if self.minimized:
            self.restore()
        if self.maximized:
            self.maximized = False
            self.x, self.y, self.width, self.height = self.saved_geometry
            self.frame.place(x=self.x, y=self.y, width=self.width, height=self.height)
            return
        self.saved_geometry = (self.frame.winfo_x(), self.frame.winfo_y(), self.frame.winfo_width(), self.frame.winfo_height())
        self.x, self.y = 0, 0
        self.width = max(400, self.wm.desktop.winfo_width())
        self.height = max(260, self.wm.desktop.winfo_height())
        self.maximized = True
        self.frame.place(x=0, y=0, width=self.width, height=self.height)
        self.focus()

    def close(self):
        self.closed = True
        self.frame.destroy()
        self.wm.close(self)


class WindowManager:
    def __init__(self, os_app, desktop, taskbar):
        self.os = os_app
        self.desktop = desktop
        self.taskbar = taskbar
        self.windows = []
        self.focused = None

    def create(self, title, app_id, width=720, height=460):
        window = InternalWindow(self, title, app_id, width, height)
        self.windows.append(window)
        self.focus(window)
        self.refresh_taskbar()
        return window

    def focus(self, window):
        if window.closed:
            return
        self.focused = window
        window.frame.lift()
        for item in self.windows:
            item.frame.configure(highlightbackground=self.os.theme["border"])
        window.frame.configure(highlightbackground=self.os.theme["accent"])
        self.refresh_taskbar()

    def close(self, window):
        if window in self.windows:
            self.windows.remove(window)
        if self.focused is window:
            self.focused = self.windows[-1] if self.windows else None
        self.refresh_taskbar()

    def refresh_taskbar(self):
        for child in self.taskbar.winfo_children():
            child.destroy()
        for window in self.windows:
            marker = "▣" if window is self.focused and not window.minimized else " "
            spec = self.os.get_app_spec(window.app_id) or {"icon": "●"}
            label = f"{marker} {spec.get('icon', '●')} {window.title[:20]}"
            button = tk.Button(
                self.taskbar,
                text=label,
                command=lambda win=window: win.restore() if win.minimized else self.focus(win),
                padx=8,
            )
            self.os.style_button(button, compact=True)
            button.pack(side="left", padx=2, pady=3)

    def apply_theme(self):
        for window in self.windows:
            window.apply_theme()
        self.refresh_taskbar()


class FileManagerApp:
    def __init__(self, os_app, window, start_path="/Home"):
        self.os = os_app
        self.fs = os_app.fs
        self.window = window
        self.path = tk.StringVar(value=self.fs.normalize(start_path))
        self.rows = []
        self.build()
        self.refresh()

    def build(self):
        root = self.window.content
        toolbar = tk.Frame(root)
        toolbar.pack(fill="x", padx=8, pady=8)
        for text, command in (
            ("Home", lambda: self.go("/Home")),
            ("Up", self.up),
            ("New folder", self.new_folder),
            ("New file", self.new_file),
            ("Open", self.open_selected),
            ("Delete", self.delete_selected),
        ):
            button = tk.Button(toolbar, text=text, command=command)
            self.os.style_button(button)
            button.pack(side="left", padx=(0, 6))
        entry = tk.Entry(toolbar, textvariable=self.path)
        self.os.style_entry(entry)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _event: self.go(self.path.get()))

        body = tk.Frame(root)
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.listbox = tk.Listbox(body, activestyle="dotbox")
        self.os.style_listbox(self.listbox)
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<Double-Button-1>", lambda _event: self.open_selected())
        details = tk.Frame(body, width=180)
        details.pack(side="right", fill="y", padx=(8, 0))
        self.info = tk.Label(details, text="", justify="left", anchor="nw")
        self.os.style_label(self.info)
        self.info.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", lambda _event: self.update_details())

    def refresh(self):
        current = self.path.get()
        self.listbox.delete(0, "end")
        try:
            self.rows = self.fs.list_dir(current)
        except Exception as exc:
            messagebox.showerror("Arquivos", str(exc))
            self.path.set("/Home")
            self.rows = self.fs.list_dir("/Home")
        for name, kind in self.rows:
            prefix = "▣  " if kind == "dir" else "✎  "
            self.listbox.insert("end", prefix + name)
        self.update_details()

    def selected(self):
        selection = self.listbox.curselection()
        if not selection:
            return None
        name, kind = self.rows[selection[0]]
        return name, kind, self.path.get().rstrip("/") + "/" + name

    def update_details(self):
        item = self.selected()
        if not item:
            counts = self.fs.count_items()
            self.info.configure(text=f"Path: {self.path.get()}\n\n{len(self.rows)} itens\n{counts['files']} arquivos virtuais\n{counts['folders']} pastas virtuais")
            return
        name, kind, full_path = item
        label = "Pasta" if kind == "dir" else "Arquivo"
        size = ""
        if kind == "file":
            size = f"\nTamanho: {len(self.fs.read_file(full_path))} bytes"
        self.info.configure(text=f"Nome: {name}\nTipo: {label}\nLocal: {full_path}{size}")

    def go(self, path):
        path = self.fs.normalize(path, self.path.get())
        try:
            if not self.fs.is_dir(path):
                self.os.open_text_editor(path)
                return
        except Exception as exc:
            messagebox.showerror("Arquivos", str(exc))
            return
        self.path.set(path)
        self.window.set_title("Arquivos - " + path)
        self.refresh()

    def up(self):
        path = self.path.get()
        parent = "/" if path == "/" else path.rsplit("/", 1)[0] or "/"
        self.go(parent)

    def new_folder(self):
        name = simpledialog.askstring("Nova pasta", "Nome da pasta:")
        if not name:
            return
        try:
            self.fs.mkdir(name, self.path.get())
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Nova pasta", str(exc))

    def new_file(self):
        name = simpledialog.askstring("Novo arquivo", "Nome do arquivo:")
        if not name:
            return
        try:
            full_path = self.fs.touch(name, self.path.get())
            self.refresh()
            self.os.open_text_editor(full_path)
        except Exception as exc:
            messagebox.showerror("Novo arquivo", str(exc))

    def open_selected(self):
        item = self.selected()
        if not item:
            return
        _name, kind, full_path = item
        if kind == "dir":
            self.go(full_path)
        else:
            self.os.open_text_editor(full_path)

    def delete_selected(self):
        item = self.selected()
        if not item:
            return
        name, _kind, full_path = item
        if not messagebox.askyesno("Excluir", f"Excluir {name}?"):
            return
        try:
            self.fs.delete(full_path)
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Excluir", str(exc))


class TextEditorApp:
    def __init__(self, os_app, window, path=None):
        self.os = os_app
        self.fs = os_app.fs
        self.window = window
        self.path = path
        self.path_var = tk.StringVar(value=path or "Sem titulo")
        self.build()
        if path:
            self.load(path)

    def build(self):
        root = self.window.content
        toolbar = tk.Frame(root)
        toolbar.pack(fill="x", padx=8, pady=8)
        for text, command in (
            ("New", self.new),
            ("Open", self.open_dialog),
            ("Save", self.save),
            ("Save as", self.save_as),
        ):
            button = tk.Button(toolbar, text=text, command=command)
            self.os.style_button(button)
            button.pack(side="left", padx=(0, 6))
        label = tk.Label(toolbar, textvariable=self.path_var, anchor="w")
        self.os.style_label(label)
        label.pack(side="left", fill="x", expand=True)
        self.text = tk.Text(root, wrap="word", undo=True)
        self.os.style_text(self.text)
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def new(self):
        self.path = None
        self.path_var.set("Sem titulo")
        self.window.set_title("Editor de Texto")
        self.text.delete("1.0", "end")

    def load(self, path):
        try:
            data = self.fs.read_file(path)
        except Exception as exc:
            messagebox.showerror("Editor", str(exc))
            return
        self.path = self.fs.normalize(path)
        self.path_var.set(self.path)
        self.window.set_title("Editor - " + self.path.rsplit("/", 1)[-1])
        self.text.delete("1.0", "end")
        self.text.insert("1.0", data)

    def open_dialog(self):
        path = simpledialog.askstring("Abrir", "Caminho do arquivo:", initialvalue=self.path or "/Home/Documents/welcome.txt")
        if path:
            self.load(path)

    def save(self):
        if not self.path:
            self.save_as()
            return
        try:
            self.fs.write_file(self.path, self.text.get("1.0", "end-1c"))
            self.os.notify("Editor", "Arquivo salvo.")
        except Exception as exc:
            messagebox.showerror("Salvar", str(exc))

    def save_as(self):
        path = simpledialog.askstring("Salvar como", "Caminho:", initialvalue=self.path or "/Home/Documents/novo.txt")
        if not path:
            return
        try:
            self.path = self.fs.write_file(path, self.text.get("1.0", "end-1c"))
            self.path_var.set(self.path)
            self.window.set_title("Editor - " + self.path.rsplit("/", 1)[-1])
            self.os.notify("Editor", "Arquivo salvo.")
        except Exception as exc:
            messagebox.showerror("Salvar como", str(exc))


class TerminalApp:
    def __init__(self, os_app, window):
        self.os = os_app
        self.fs = os_app.fs
        self.window = window
        self.cwd = "/Home"
        self.history = []
        self.history_index = 0
        self.build()
        self.print_line("Cinnix Shell - digite 'help' para comandos.")

    def build(self):
        root = self.window.content
        self.output = tk.Text(root, wrap="word", height=20)
        self.os.style_terminal(self.output)
        self.output.pack(fill="both", expand=True, padx=8, pady=8)
        bottom = tk.Frame(root)
        bottom.pack(fill="x", padx=8, pady=(0, 8))
        self.prompt = tk.Label(bottom, text=self.cwd + " $ ")
        self.os.style_label(self.prompt)
        self.prompt.pack(side="left")
        self.entry = tk.Entry(bottom)
        self.os.style_entry(self.entry)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self.run_command)
        self.entry.bind("<Up>", self.history_up)
        self.entry.bind("<Down>", self.history_down)
        self.entry.focus_set()

    def print_line(self, text=""):
        self.output.configure(state="normal")
        self.output.insert("end", text + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def run_command(self, _event=None):
        command = self.entry.get().strip()
        if not command:
            return
        self.history.append(command)
        self.history_index = len(self.history)
        self.print_line(f"{self.cwd} $ {command}")
        self.entry.delete(0, "end")
        try:
            result = self.execute(command)
            if result:
                self.print_line(result)
        except Exception as exc:
            self.print_line("erro: " + str(exc))
        self.prompt.configure(text=self.cwd + " $ ")

    def history_up(self, _event):
        if not self.history:
            return "break"
        self.history_index = max(0, self.history_index - 1)
        self.entry.delete(0, "end")
        self.entry.insert(0, self.history[self.history_index])
        return "break"

    def history_down(self, _event):
        if not self.history:
            return "break"
        self.history_index = min(len(self.history), self.history_index + 1)
        self.entry.delete(0, "end")
        if self.history_index < len(self.history):
            self.entry.insert(0, self.history[self.history_index])
        return "break"

    def execute(self, command):
        args = shlex.split(command)
        if not args:
            return ""
        cmd = args[0].lower()
        if cmd == "help":
            return (
                "Comandos: help, clear, pwd, ls, cd, cat, echo, touch, mkdir, rm, date,\n"
                "whoami, neofetch, theme, open, apps, history, nano, curl, wget, ping, exit"
            )
        if cmd == "clear":
            self.output.configure(state="normal")
            self.output.delete("1.0", "end")
            self.output.configure(state="disabled")
            return ""
        if cmd == "pwd":
            return self.cwd
        if cmd == "ls":
            path = args[1] if len(args) > 1 else self.cwd
            rows = self.fs.list_dir(path, self.cwd)
            return "\n".join(("[DIR] " if kind == "dir" else "      ") + name for name, kind in rows) or "(vazio)"
        if cmd == "cd":
            path = args[1] if len(args) > 1 else "/Home"
            new_path = self.fs.normalize(path, self.cwd)
            if not self.fs.is_dir(new_path):
                raise NotADirectoryError(new_path)
            self.cwd = new_path
            return ""
        if cmd == "cat":
            if len(args) < 2:
                return "uso: cat arquivo"
            return self.fs.read_file(args[1], self.cwd)
        if cmd == "echo":
            if ">" in args:
                index = args.index(">")
                content = " ".join(args[1:index])
                if index + 1 >= len(args):
                    return "uso: echo texto > arquivo"
                self.fs.write_file(args[index + 1], content + "\n", self.cwd)
                return ""
            return " ".join(args[1:])
        if cmd == "touch":
            for name in args[1:]:
                self.fs.touch(name, self.cwd)
            return ""
        if cmd == "mkdir":
            for name in args[1:]:
                self.fs.mkdir(name, self.cwd)
            return ""
        if cmd == "rm":
            if len(args) < 2:
                return "uso: rm caminho"
            for name in args[1:]:
                self.fs.delete(name, self.cwd)
            return ""
        if cmd == "date":
            return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if cmd == "whoami":
            return self.os.username
        if cmd == "history":
            return "\n".join(f"{i + 1:>3}  {item}" for i, item in enumerate(self.history))
        if cmd == "neofetch":
            counts = self.fs.count_items()
            return (
                "Cinnix 1.0\n"
                f"User: {self.os.username}\n"
                "Desktop: Cinnamon/Luminix Tk\n"
                f"Theme: {self.os.theme_name}\n"
                f"Windows: {len(self.os.wm.windows)}\n"
                f"Virtual FS: {counts['folders']} folders, {counts['files']} files"
            )
        if cmd == "theme":
            if len(args) < 2:
                return "tema atual: " + self.os.theme_name
            self.os.set_theme(args[1])
            return "tema alterado para " + self.os.theme_name
        if cmd == "apps":
            return "\n".join(spec["id"] + " - " + spec["name"] for spec in self.os.app_specs)
        if cmd == "open":
            if len(args) < 2:
                return "uso: open app-ou-caminho"
            target = args[1]
            if self.fs.exists(target, self.cwd):
                path = self.fs.normalize(target, self.cwd)
                if self.fs.is_dir(path):
                    self.os.open_file_manager(path)
                else:
                    self.os.open_text_editor(path)
                return ""
            self.os.launch_app(target)
            return ""
        if cmd == "nano":
            path = args[1] if len(args) > 1 else None
            self.os.open_text_editor(self.fs.normalize(path, self.cwd) if path else None)
            return ""
        if cmd == "curl":
            if len(args) < 2:
                return "uso: curl url [> arquivo]"
            url = args[1]
            result = fetch_url(url)
            output = result["text"]
            if ">" in args:
                index = args.index(">")
                if index + 1 >= len(args):
                    return "uso: curl url > arquivo"
                self.fs.write_file(args[index + 1], output, self.cwd)
                return f"salvo em {self.fs.normalize(args[index + 1], self.cwd)}"
            return output[:8000] + ("\n[saida truncada]" if len(output) > 8000 else "")
        if cmd == "wget":
            if len(args) < 2:
                return "uso: wget url [arquivo]"
            result = fetch_url(args[1])
            filename = args[2] if len(args) > 2 else urllib.parse.urlparse(result["url"]).netloc.replace(".", "-") + ".txt"
            self.fs.write_file(filename, result["text"], self.cwd)
            return f"{result['bytes']} bytes lidos; salvo em {self.fs.normalize(filename, self.cwd)}"
        if cmd == "ping":
            if len(args) < 2:
                return "uso: ping host-ou-url"
            target = args[1]
            if "://" not in target:
                target = "https://" + target
            start = datetime.datetime.now()
            result = fetch_url(target, timeout=6, limit=1024)
            elapsed = (datetime.datetime.now() - start).total_seconds() * 1000
            return f"HTTP OK {urllib.parse.urlparse(result['url']).netloc} tempo={elapsed:.0f} ms tipo={result['content_type']}"
        if cmd == "exit":
            self.window.close()
            return ""
        return f"comando nao encontrado: {cmd}"


class BrowserApp:
    def __init__(self, os_app, window):
        self.os = os_app
        self.window = window
        self.history = []
        self.index = -1
        self.links = []
        self.loading = False
        self.pages = {
            "cinnix://home": (
                "Cinnix Browser\n\n"
                "Digite um site real na barra, por exemplo:\n"
                "https://example.com\nhttps://www.python.org\nhttps://duckduckgo.com/html/?q=Cinnix\n\n"
                "Paginas internas:\n"
                "cinnix://about\ncinnix://docs\ncinnix://apps\n\n"
                "HTML e texto sao carregados pela internet e renderizados em modo leitura."
            ),
            "cinnix://about": "Sobre o navegador\n\nEste browser usa urllib da biblioteca padrao do Python para acessar HTTP/HTTPS reais. Ele nao executa JavaScript nem CSS; renderiza o conteudo como texto legivel.",
            "cinnix://docs": (
                "Documentacao rapida\n\n"
                "- Use o menu para abrir apps.\n"
                "- Arraste janelas pela barra de titulo.\n"
                "- O navegador acessa sites HTTP/HTTPS reais.\n"
                "- Use o botao Link para abrir um link numerado da pagina."
            ),
            "cinnix://apps": "Apps instalados\n\n" + "\n".join(spec["name"] for spec in os_app.app_specs),
        }
        self.build()
        self.navigate("cinnix://home")

    def build(self):
        root = self.window.content
        toolbar = tk.Frame(root)
        toolbar.pack(fill="x", padx=8, pady=8)
        for text, command in (("<", self.back), (">", self.forward), ("Home", lambda: self.navigate("cinnix://home")), ("Go", self.go), ("Link", self.open_link_dialog), ("Save", self.save_page)):
            button = tk.Button(toolbar, text=text, command=command)
            self.os.style_button(button)
            button.pack(side="left", padx=(0, 6))
        self.url = tk.Entry(toolbar)
        self.os.style_entry(self.url)
        self.url.pack(side="left", fill="x", expand=True)
        self.url.bind("<Return>", lambda _event: self.go())
        self.view = tk.Text(root, wrap="word")
        self.os.style_text(self.view)
        self.view.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.view.tag_configure("link", foreground=self.os.theme["accent"], underline=True)
        self.status = tk.Label(root, text="", anchor="w")
        self.os.style_label(self.status)
        self.status.pack(fill="x", padx=8, pady=(0, 8))

    def render(self, text, links=None):
        self.links = links or []
        self.view.configure(state="normal")
        self.view.delete("1.0", "end")
        self.view.insert("1.0", text)
        if self.links:
            self.view.insert("end", "\n\nLinks encontrados:\n")
            for index, (label, href) in enumerate(self.links, start=1):
                start = self.view.index("end-1c")
                self.view.insert("end", f"{index}. {label} -> {href}\n")
                end = self.view.index("end-1c")
                self.view.tag_add("link", start, end)
        self.view.configure(state="disabled")

    def navigate(self, address, remember=True):
        address = address.strip() or "cinnix://home"
        if "://" not in address:
            if "." in address and " " not in address:
                address = "https://" + address
            else:
                address = "https://duckduckgo.com/html/?q=" + urllib.parse.quote_plus(address)
        if remember:
            self.history = self.history[: self.index + 1]
            self.history.append(address)
            self.index += 1
        self.url.delete(0, "end")
        self.url.insert(0, address)
        if address.startswith("cinnix://"):
            self.render(self.pages.get(address, "404\n\nEsta pagina interna nao existe."))
            self.status.configure(text="Pagina interna carregada.")
            self.window.set_title("Firefox - " + address)
            return
        self.loading = True
        self.render("Carregando " + address + " ...")
        self.status.configure(text="Conectando...")
        self.window.set_title("Firefox - carregando")
        threading.Thread(target=self.fetch_in_background, args=(address,), daemon=True).start()

    def fetch_in_background(self, address):
        try:
            result = fetch_url(address)
        except urllib.error.HTTPError as exc:
            self.window.content.after(0, lambda: self.render_error(address, f"HTTP {exc.code}: {exc.reason}"))
            return
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            self.window.content.after(0, lambda: self.render_error(address, "Erro de rede: " + str(reason)))
            return
        except Exception as exc:
            self.window.content.after(0, lambda: self.render_error(address, str(exc)))
            return
        self.window.content.after(0, lambda: self.render_remote_page(result))

    def render_remote_page(self, result):
        header = (
            f"URL: {result['url']}\n"
            f"Tipo: {result['content_type']}\n"
            f"Bytes lidos: {result['bytes']}\n\n"
        )
        self.render(header + (result["text"] or "[sem texto renderizavel]"), result["links"])
        self.url.delete(0, "end")
        self.url.insert(0, result["url"])
        self.status.configure(text=f"Carregado: {result['url']}")
        self.window.set_title("Firefox - " + urllib.parse.urlparse(result["url"]).netloc)

    def render_error(self, address, message):
        self.render(f"Nao foi possivel carregar:\n{address}\n\n{message}\n\nVerifique sua conexao, DNS ou firewall.")
        self.status.configure(text="Falha ao carregar.")
        self.window.set_title("Firefox - erro")

    def go(self):
        self.navigate(self.url.get())

    def open_link_dialog(self):
        if not self.links:
            self.status.configure(text="Nenhum link carregado.")
            return
        number = simpledialog.askinteger("Abrir link", f"Numero do link (1-{len(self.links)}):")
        if number is None:
            return
        if 1 <= number <= len(self.links):
            self.navigate(self.links[number - 1][1])
        else:
            self.status.configure(text="Numero de link invalido.")

    def save_page(self):
        content = self.view.get("1.0", "end-1c")
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = f"/Home/Downloads/webpage-{stamp}.txt"
        self.os.fs.write_file(path, content)
        self.status.configure(text="Pagina salva em " + path)
        self.os.notify("Firefox", "Pagina salva.")

    def back(self):
        if self.index > 0:
            self.index -= 1
            self.navigate(self.history[self.index], remember=False)

    def forward(self):
        if self.index + 1 < len(self.history):
            self.index += 1
            self.navigate(self.history[self.index], remember=False)


class SettingsApp:
    def __init__(self, os_app, window):
        self.os = os_app
        self.window = window
        self.build()

    def build(self):
        root = self.window.content
        title = tk.Label(root, text="Configuracoes do Sistema", font=("Segoe UI", 16, "bold"), anchor="w")
        self.os.style_label(title)
        title.pack(fill="x", padx=14, pady=(14, 10))

        section = tk.Frame(root)
        section.pack(fill="x", padx=14, pady=8)
        self.os.style_frame(section)
        tk.Label(section, text="Tema", anchor="w").pack(fill="x")
        for theme_id, label in (("light", "Luminix Light"), ("dark", "Luminix Dark")):
            button = tk.Button(section, text=label, command=lambda value=theme_id: self.os.set_theme(value))
            self.os.style_button(button)
            button.pack(side="left", padx=(0, 8), pady=8)

        wall = tk.Frame(root)
        wall.pack(fill="x", padx=14, pady=8)
        self.os.style_frame(wall)
        tk.Label(wall, text="Papel de parede", anchor="w").pack(fill="x")
        for color, label in (("#0f8f57", "Cinnix"), ("#245c73", "Ocean"), ("#4b3b6b", "Dusk"), ("#4b5d3a", "Forest")):
            button = tk.Button(wall, text=label, command=lambda value=color: self.os.set_wallpaper(value), width=10)
            button.configure(bg=color, fg="white", activebackground=color)
            button.pack(side="left", padx=(0, 8), pady=8)

        user_box = tk.Frame(root)
        user_box.pack(fill="x", padx=14, pady=8)
        self.os.style_frame(user_box)
        tk.Label(user_box, text="Usuario", anchor="w").pack(fill="x")
        self.username = tk.Entry(user_box)
        self.os.style_entry(self.username)
        self.username.insert(0, self.os.username)
        self.username.pack(side="left", fill="x", expand=True, pady=8)
        save = tk.Button(user_box, text="Aplicar", command=self.save_user)
        self.os.style_button(save)
        save.pack(side="left", padx=(8, 0))

        clock = tk.Checkbutton(root, text="Mostrar segundos no relogio", variable=self.os.show_seconds, command=self.os.update_clock)
        self.os.style_check(clock)
        clock.pack(anchor="w", padx=14, pady=10)

    def save_user(self):
        self.os.username = self.username.get().strip() or "cinnix"
        self.os.notify("Configuracoes", "Usuario atualizado.")


class CalculatorApp:
    def __init__(self, os_app, window):
        self.os = os_app
        self.window = window
        self.value = tk.StringVar()
        self.build()

    def build(self):
        root = self.window.content
        display = tk.Entry(root, textvariable=self.value, justify="right", font=("Segoe UI", 18))
        self.os.style_entry(display)
        display.pack(fill="x", padx=10, pady=10, ipady=8)
        grid = tk.Frame(root)
        grid.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        buttons = [
            ("7", "8", "9", "/"),
            ("4", "5", "6", "*"),
            ("1", "2", "3", "-"),
            ("0", ".", "=", "+"),
            ("C", "(", ")", "DEL"),
        ]
        for r, row in enumerate(buttons):
            grid.rowconfigure(r, weight=1)
            for c, label in enumerate(row):
                grid.columnconfigure(c, weight=1)
                button = tk.Button(grid, text=label, command=lambda text=label: self.press(text))
                self.os.style_button(button)
                button.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)

    def press(self, text):
        if text == "C":
            self.value.set("")
            return
        if text == "DEL":
            self.value.set(self.value.get()[:-1])
            return
        if text == "=":
            expr = self.value.get()
            if any(ch not in "0123456789+-*/(). % " for ch in expr):
                self.value.set("Erro")
                return
            try:
                self.value.set(str(eval(expr, {"__builtins__": None}, {})))
            except Exception:
                self.value.set("Erro")
            return
        self.value.set(self.value.get() + text)


class SystemMonitorApp:
    def __init__(self, os_app, window):
        self.os = os_app
        self.window = window
        self.build()
        self.refresh()

    def build(self):
        root = self.window.content
        self.info = tk.Label(root, text="", justify="left", anchor="w", font=("Consolas", 10))
        self.os.style_label(self.info)
        self.info.pack(fill="x", padx=10, pady=10)
        self.listbox = tk.Listbox(root)
        self.os.style_listbox(self.listbox)
        self.listbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        actions = tk.Frame(root)
        actions.pack(fill="x", padx=10, pady=(0, 10))
        focus = tk.Button(actions, text="Focar janela", command=self.focus_selected)
        close = tk.Button(actions, text="Fechar janela", command=self.close_selected)
        self.os.style_button(focus)
        self.os.style_button(close)
        focus.pack(side="left", padx=(0, 6))
        close.pack(side="left")

    def refresh(self):
        if self.window.closed:
            return
        counts = self.os.fs.count_items()
        uptime = datetime.datetime.now() - self.os.started_at
        self.info.configure(
            text=(
                f"Uptime: {str(uptime).split('.')[0]}\n"
                f"Janelas abertas: {len(self.os.wm.windows)}\n"
                f"Filesystem virtual: {counts['folders']} pastas, {counts['files']} arquivos\n"
                f"Tema: {self.os.theme_name}"
            )
        )
        self.listbox.delete(0, "end")
        for window in self.os.wm.windows:
            status = "min" if window.minimized else "ativo"
            self.listbox.insert("end", f"{window.title}  [{window.app_id} / {status}]")
        self.window.content.after(1000, self.refresh)

    def selected_window(self):
        selection = self.listbox.curselection()
        if not selection:
            return None
        index = selection[0]
        if index >= len(self.os.wm.windows):
            return None
        return self.os.wm.windows[index]

    def focus_selected(self):
        window = self.selected_window()
        if window:
            window.restore() if window.minimized else self.os.wm.focus(window)

    def close_selected(self):
        window = self.selected_window()
        if window and window is not self.window:
            window.close()


class GenericCinnixApp:
    def __init__(self, os_app, window, spec):
        self.os = os_app
        self.window = window
        self.spec = spec
        self.status = tk.StringVar(value=spec.get("status", "Pronto"))
        self.listbox = None
        self.editor_text = None
        self.media_job = None
        self.media_progress = 0
        self.build()

    def build(self):
        root = self.window.content
        header = tk.Frame(root)
        self.os.style_frame(header)
        header.pack(fill="x", padx=14, pady=(14, 10))
        icon = IconCanvas(header, self.os, self.spec, size=54)
        icon.pack(side="left", padx=(0, 12))
        titles = tk.Frame(header)
        self.os.style_frame(titles)
        titles.pack(side="left", fill="x", expand=True)
        title = tk.Label(titles, text=self.spec["name"], anchor="w", font=("Segoe UI", 16, "bold"))
        subtitle = tk.Label(titles, text=self.spec.get("tagline", self.spec.get("category", "Aplicativo")), anchor="w")
        self.os.style_label(title)
        self.os.style_label(subtitle)
        subtitle.configure(fg=self.os.theme["muted"])
        title.pack(fill="x")
        subtitle.pack(fill="x")

        action_bar = tk.Frame(root)
        self.os.style_frame(action_bar)
        action_bar.pack(fill="x", padx=14, pady=(0, 10))
        for text, command in self.actions_for_app():
            button = tk.Button(action_bar, text=text, command=command)
            self.os.style_button(button)
            button.pack(side="left", padx=(0, 8))

        kind = self.spec.get("kind", "utility")
        if kind == "office":
            self.office_view(root)
        elif kind == "media":
            self.media_view(root)
        elif kind == "grid":
            self.grid_view(root)
        elif kind == "calendar":
            self.calendar_view(root)
        elif kind == "notes":
            self.notes_view(root)
        else:
            self.utility_view(root)

        status = tk.Label(root, textvariable=self.status, anchor="w")
        self.os.style_label(status)
        status.configure(fg=self.os.theme["muted"])
        status.pack(fill="x", padx=14, pady=(0, 10))

    def actions_for_app(self):
        app_id = self.spec["id"]
        actions = {
            "update-manager": [("↻ Atualizar lista", self.refresh_updates), ("✓ Instalar selecionada", self.install_selected_update), ("✓ Instalar tudo", self.install_all_updates)],
            "driver-manager": [("⌕ Detectar hardware", self.detect_hardware), ("✓ Aplicar selecionado", self.apply_selected_driver)],
            "software-manager": [("⌕ Buscar", self.search_software), ("+ Instalar", self.install_selected_package), ("− Remover", self.remove_selected_package)],
            "timeshift": [("+ Snapshot", self.create_snapshot), ("↺ Restaurar ultimo", self.restore_snapshot)],
            "firewall": [("● Alternar firewall", self.toggle_firewall), ("+ Regra", self.add_firewall_rule), ("− Remover regra", self.remove_selected_item)],
            "gnome-screenshot": [("▣ Capturar tela", self.take_screenshot), ("◴ Capturar janela", self.take_window_snapshot)],
            "sticky-notes": [("+ Nova nota", self.new_note), ("✓ Salvar", self.save_notes)],
            "calendar": [("+ Evento", self.add_calendar_event), ("Hoje", lambda: self.set_status(datetime.date.today().strftime("Hoje: %Y-%m-%d")))],
            "thunderbird": [("+ Escrever email", self.compose_mail), ("✓ Arquivar", self.archive_mail)],
            "transmission": [("+ Torrent", self.add_torrent), ("▶ Iniciar", self.start_media_progress), ("⏸ Pausar", self.pause_media_progress)],
            "remmina": [("+ Conexao", self.add_connection), ("▶ Conectar", self.connect_selected)],
            "warpinator": [("⇄ Enviar arquivo", self.send_file), ("↻ Procurar", self.discover_devices)],
            "power-manager": [("Balanceado", lambda: self.set_power_profile("Balanceado")), ("Economia", lambda: self.set_power_profile("Economia")), ("Performance", lambda: self.set_power_profile("Performance"))],
            "bluetooth": [("⌕ Procurar", self.scan_bluetooth), ("✓ Parear", self.pair_bluetooth), ("− Remover", self.remove_selected_item)],
            "archive-manager": [("+ Criar arquivo", self.create_archive), ("⇩ Extrair", self.extract_archive)],
            "disk-usage": [("↻ Analisar", self.analyze_disk_usage)],
            "disks": [("↻ Atualizar", self.refresh_disks), ("⏏ Ejetar USB", self.eject_usb)],
            "usb-image-writer": [("▰ Gravar ISO", self.write_usb_image), ("✓ Verificar", self.verify_usb_image)],
            "font-viewer": [("A Visualizar", self.preview_font)],
            "cinnamon-control-center": [("Abrir tema", lambda: self.os.open_settings()), ("Abrir monitor", lambda: self.os.open_monitor())],
            "xreader": [("Abrir documento", self.open_document), ("Adicionar marcador", self.add_bookmark)],
            "pix": [("Abrir imagem", self.open_picture), ("Girar", self.rotate_picture)],
        }
        if self.spec.get("kind") == "office":
            return [("Novo", self.office_new), ("Salvar", self.office_save), ("Exportar PDF", self.office_export_pdf)]
        if self.spec.get("kind") == "media":
            return [("▶ Reproduzir", self.start_media_progress), ("⏸ Pausar", self.pause_media_progress), ("■ Parar", self.stop_media_progress)]
        if app_id in actions:
            return actions[app_id]
        return [("+ Adicionar item", self.add_generic_item), ("✓ Salvar estado", self.save_generic_state), ("− Remover", self.remove_selected_item)]

    def set_status(self, text):
        self.status.set(text)
        self.os.notify(self.spec["name"], text)

    def selected_index(self):
        if not self.listbox:
            return None
        selection = self.listbox.curselection()
        return selection[0] if selection else None

    def selected_text(self):
        index = self.selected_index()
        if index is None:
            return None
        return self.listbox.get(index)

    def refresh_list(self, items):
        if not self.listbox:
            return
        self.listbox.delete(0, "end")
        for item in items:
            self.listbox.insert("end", item)

    def add_list_item(self, text):
        if self.listbox:
            self.listbox.insert("end", text)

    def state_list(self, key):
        return self.os.app_state.setdefault(key, [])

    def utility_view(self, root):
        body = tk.Frame(root)
        self.os.style_frame(body)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.listbox = tk.Listbox(body)
        self.os.style_listbox(self.listbox)
        self.listbox.pack(side="left", fill="both", expand=True, padx=(0, 10))
        items = self.initial_items()
        for item in items:
            self.listbox.insert("end", item)
        panel = tk.Text(body, height=8, wrap="word")
        self.os.style_text(panel)
        panel.pack(side="right", fill="both", expand=True)
        panel.insert("1.0", self.spec.get("description", "Ferramenta integrada do Cinnix com controles locais."))
        panel.configure(state="disabled")

    def initial_items(self):
        app_id = self.spec["id"]
        if app_id == "update-manager":
            return self.os.app_state["updates"]
        if app_id == "software-manager":
            return self.software_items()
        if app_id == "timeshift":
            return self.snapshot_items()
        if app_id == "firewall":
            return self.firewall_items()
        if app_id == "thunderbird":
            return self.os.app_state["mail"]
        if app_id == "transmission":
            return self.os.app_state["torrents"]
        if app_id == "remmina":
            return self.os.app_state["connections"]
        if app_id == "warpinator":
            return self.os.app_state["devices"]
        if app_id == "bluetooth":
            return self.os.app_state["bluetooth"]
        if app_id == "power-manager":
            return self.power_items()
        if app_id == "disk-usage":
            return self.disk_usage_items()
        if app_id == "disks":
            return self.os.app_state["disks"]
        if app_id == "calendar":
            return self.os.app_state["events"]
        if app_id == "archive-manager":
            return self.os.app_state["archives"]
        return self.spec.get("items") or [
            "Estado: operacional",
            "Perfil: padrao do Cinnix",
            "Dados locais: ativo",
            "Integracao com Cinnamon: ativa",
        ]

    def office_view(self, root):
        self.editor_text = tk.Text(root, wrap="word")
        self.os.style_text(self.editor_text)
        self.editor_text.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.editor_text.insert("1.0", self.spec.get("template", f"{self.spec['name']}\n\nDocumento pronto para edicao."))

    def media_view(self, root):
        body = tk.Frame(root)
        self.os.style_frame(body)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        art = tk.Canvas(body, width=180, highlightthickness=0, bg=self.os.theme["window"])
        art.pack(side="left", fill="y", padx=(0, 14))
        rounded_rectangle(art, 18, 28, 162, 172, 24, fill=self.spec.get("color", self.os.theme["accent"]), outline="")
        art.create_text(90, 100, text=self.spec.get("icon", "▶"), fill="#ffffff", font=("Segoe UI Symbol", 54, "bold"))
        self.listbox = tk.Listbox(body)
        self.os.style_listbox(self.listbox)
        self.listbox.pack(side="left", fill="both", expand=True)
        for item in self.spec.get("items", ["Arquivo local 01", "Arquivo local 02", "Arquivo local 03"]):
            self.listbox.insert("end", item)

    def grid_view(self, root):
        grid = tk.Frame(root)
        self.os.style_frame(grid)
        grid.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        for index, item in enumerate(self.spec.get("items", ["Item A", "Item B", "Item C", "Item D"])):
            row, col = divmod(index, 3)
            cell = tk.Frame(grid, highlightthickness=1, highlightbackground=self.os.theme["border"])
            self.os.style_frame(cell)
            cell.grid(row=row, column=col, sticky="nsew", padx=5, pady=5, ipadx=8, ipady=8)
            grid.columnconfigure(col, weight=1)
            label = tk.Label(cell, text=f"{self.spec.get('icon', '●')}\n{item}", justify="center")
            self.os.style_label(label)
            label.pack(expand=True, fill="both")

    def calendar_view(self, root):
        text = tk.Text(root, wrap="none", font=("Consolas", 11))
        self.os.style_text(text)
        text.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        today = datetime.date.today()
        first = today.replace(day=1)
        start = (first.weekday() + 1) % 7
        days = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab"]
        line = " ".join(day.center(4) for day in days) + "\n"
        line += "    " * start
        for day in range(1, 32):
            try:
                current = first.replace(day=day)
            except ValueError:
                break
            token = f"[{day:02d}]" if current == today else f" {day:02d} "
            line += token
            if (start + day) % 7 == 0:
                line += "\n"
        text.insert("1.0", today.strftime("%B %Y\n\n") + line)
        text.configure(state="disabled")

    def notes_view(self, root):
        self.editor_text = tk.Text(root, wrap="word")
        self.os.style_text(self.editor_text)
        self.editor_text.configure(bg="#fff4a3", fg="#202020", insertbackground="#202020")
        self.editor_text.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.editor_text.insert("1.0", self.os.app_state.get("notes", "Notas adesivas\n\n- Comprar cafe\n- Revisar atualizacoes\n- Testar Warpinator"))

    def take_screenshot(self):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = f"/Home/Pictures/screenshot-{stamp}.txt"
        self.os.fs.write_file(path, self.desktop_snapshot("Tela inteira"))
        self.set_status("Screenshot salvo em " + path)

    def take_window_snapshot(self):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        title = self.os.wm.focused.title if self.os.wm.focused else self.window.title
        path = f"/Home/Pictures/window-{stamp}.txt"
        self.os.fs.write_file(path, self.desktop_snapshot("Janela: " + title))
        self.set_status("Janela salva em " + path)

    def desktop_snapshot(self, label):
        windows = "\n".join(f"- {window.title} [{window.app_id}]" for window in self.os.wm.windows)
        return f"{label}\nData: {datetime.datetime.now()}\nResolucao: {self.os.root.winfo_width()}x{self.os.root.winfo_height()}\nJanelas:\n{windows}\n"

    def refresh_updates(self):
        packages = ["cinnix-update", "cinnamon", "nemo", "xed", "xreader", "warpinator"]
        updates = [f"{pkg}  {random.randint(1, 9)}.{random.randint(0, 9)} MB" for pkg in packages if random.choice((True, False))]
        self.os.app_state["updates"] = updates or ["Sistema atualizado"]
        self.refresh_list(self.os.app_state["updates"])
        self.set_status(f"{len(updates)} atualizacoes encontradas.")

    def install_selected_update(self):
        item = self.selected_text()
        if not item or item == "Sistema atualizado":
            self.set_status("Selecione uma atualizacao.")
            return
        self.os.app_state["updates"].remove(item)
        self.refresh_list(self.os.app_state["updates"] or ["Sistema atualizado"])
        self.os.fs.write_file("/System/last-update.log", f"Instalado: {item}\n{datetime.datetime.now()}")
        self.set_status(item.split()[0] + " instalado.")

    def install_all_updates(self):
        installed = list(self.os.app_state["updates"])
        self.os.app_state["updates"] = []
        self.refresh_list(["Sistema atualizado"])
        self.os.fs.write_file("/System/last-update.log", "Instalados:\n" + "\n".join(installed))
        self.set_status(f"{len(installed)} atualizacoes instaladas.")

    def detect_hardware(self):
        items = [
            "CPU: " + (platform.processor() or "processador detectado"),
            "Host: " + platform.node(),
            "Sistema: " + platform.platform(),
            "Video: driver generico acelerado",
            "Rede: adaptador local pronto",
        ]
        self.refresh_list(items)
        self.set_status("Hardware detectado.")

    def apply_selected_driver(self):
        item = self.selected_text()
        if not item:
            self.set_status("Selecione um driver.")
            return
        self.os.app_state["drivers"].append(item)
        self.os.fs.write_file("/System/drivers.conf", "\n".join(self.os.app_state["drivers"]))
        self.set_status("Aplicado: " + item)

    def software_items(self):
        installed = self.os.app_state["installed_packages"]
        return [f"{'✓' if pkg in installed else '+'} {pkg}" for pkg in self.os.app_state["catalog"]]

    def search_software(self):
        term = simpledialog.askstring("Software Manager", "Buscar pacote:")
        if term is None:
            return
        rows = [f"{'✓' if pkg in self.os.app_state['installed_packages'] else '+'} {pkg}" for pkg in self.os.app_state["catalog"] if term.lower() in pkg.lower()]
        self.refresh_list(rows or ["Nenhum pacote encontrado"])
        self.set_status(f"Busca: {term}")

    def selected_package(self):
        item = self.selected_text()
        if not item or item.startswith("Nenhum"):
            return None
        return item[2:].strip()

    def install_selected_package(self):
        package = self.selected_package()
        if not package:
            self.set_status("Selecione um pacote.")
            return
        self.os.app_state["installed_packages"].add(package)
        self.refresh_list(self.software_items())
        self.set_status(package + " instalado.")

    def remove_selected_package(self):
        package = self.selected_package()
        if not package:
            self.set_status("Selecione um pacote.")
            return
        self.os.app_state["installed_packages"].discard(package)
        self.refresh_list(self.software_items())
        self.set_status(package + " removido.")

    def snapshot_items(self):
        return [snap["name"] for snap in self.os.app_state["snapshots"]] or ["Nenhum snapshot"]

    def create_snapshot(self):
        name = "snapshot-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.os.app_state["snapshots"].append({"name": name, "root": copy.deepcopy(self.os.fs.root)})
        self.refresh_list(self.snapshot_items())
        self.set_status("Criado: " + name)

    def restore_snapshot(self):
        snapshots = self.os.app_state["snapshots"]
        if not snapshots:
            self.set_status("Nao ha snapshot para restaurar.")
            return
        self.os.fs.root = copy.deepcopy(snapshots[-1]["root"])
        self.set_status("Restaurado: " + snapshots[-1]["name"])

    def firewall_items(self):
        state = "ativo" if self.os.app_state["firewall_enabled"] else "inativo"
        return ["Firewall: " + state] + self.os.app_state["firewall_rules"]

    def toggle_firewall(self):
        self.os.app_state["firewall_enabled"] = not self.os.app_state["firewall_enabled"]
        self.refresh_list(self.firewall_items())
        self.set_status("Firewall " + ("ativado." if self.os.app_state["firewall_enabled"] else "desativado."))

    def add_firewall_rule(self):
        rule = simpledialog.askstring("Firewall", "Regra, ex: allow tcp 22:")
        if not rule:
            return
        self.os.app_state["firewall_rules"].append(rule)
        self.refresh_list(self.firewall_items())
        self.set_status("Regra adicionada.")

    def remove_selected_item(self):
        item = self.selected_text()
        if not item:
            self.set_status("Selecione um item.")
            return
        for key in ("firewall_rules", "bluetooth", "events", "archives"):
            if item in self.os.app_state.get(key, []):
                self.os.app_state[key].remove(item)
        index = self.selected_index()
        if index is not None:
            self.listbox.delete(index)
        self.set_status("Item removido: " + item)

    def new_note(self):
        if self.editor_text:
            self.editor_text.insert("end", "\n- Nova nota " + datetime.datetime.now().strftime("%H:%M"))
            self.set_status("Nota adicionada.")

    def save_notes(self):
        if not self.editor_text:
            return
        self.os.app_state["notes"] = self.editor_text.get("1.0", "end-1c")
        self.os.fs.write_file("/Home/Documents/sticky-notes.txt", self.os.app_state["notes"])
        self.set_status("Notas salvas.")

    def add_calendar_event(self):
        event = simpledialog.askstring("Calendar", "Evento:")
        if not event:
            return
        row = datetime.date.today().strftime("%Y-%m-%d") + "  " + event
        self.os.app_state["events"].append(row)
        self.add_list_item(row)
        self.set_status("Evento adicionado.")

    def compose_mail(self):
        to = simpledialog.askstring("Thunderbird", "Para:")
        subject = simpledialog.askstring("Thunderbird", "Assunto:") if to else None
        if not to or subject is None:
            return
        row = f"Para {to}: {subject}"
        self.os.app_state["mail"].append(row)
        self.refresh_list(self.os.app_state["mail"])
        self.os.fs.write_file("/Home/Documents/mailbox.txt", "\n".join(self.os.app_state["mail"]))
        self.set_status("Email salvo na caixa local.")

    def archive_mail(self):
        item = self.selected_text()
        if not item:
            self.set_status("Selecione um email.")
            return
        self.os.app_state["mail"].remove(item)
        self.os.app_state["mail_archive"].append(item)
        self.refresh_list(self.os.app_state["mail"])
        self.set_status("Email arquivado.")

    def add_torrent(self):
        name = simpledialog.askstring("Transmission", "Nome do torrent:")
        if not name:
            return
        row = name + " - 0%"
        self.os.app_state["torrents"].append(row)
        self.refresh_list(self.os.app_state["torrents"])
        self.set_status("Torrent adicionado.")

    def start_media_progress(self):
        item = self.selected_text() or self.spec["name"]
        self.media_progress = 0
        self.set_status("Reproduzindo: " + item)
        self.advance_media_progress()

    def advance_media_progress(self):
        if self.window.closed:
            return
        self.media_progress = min(100, self.media_progress + 10)
        self.status.set(f"Progresso: {self.media_progress}%")
        if self.media_progress < 100:
            self.media_job = self.window.content.after(350, self.advance_media_progress)

    def pause_media_progress(self):
        if self.media_job:
            self.window.content.after_cancel(self.media_job)
            self.media_job = None
        self.set_status("Pausado em " + str(self.media_progress) + "%")

    def stop_media_progress(self):
        self.pause_media_progress()
        self.media_progress = 0
        self.set_status("Parado.")

    def add_connection(self):
        target = simpledialog.askstring("Remmina", "Host:")
        if target:
            self.os.app_state["connections"].append("RDP " + target)
            self.refresh_list(self.os.app_state["connections"])
            self.set_status("Conexao adicionada.")

    def connect_selected(self):
        item = self.selected_text()
        self.set_status("Conectado a " + item if item else "Selecione uma conexao.")

    def discover_devices(self):
        devices = ["desktop-sala", "notebook", "phone", "media-center"]
        self.os.app_state["devices"] = random.sample(devices, random.randint(2, len(devices)))
        self.refresh_list(self.os.app_state["devices"])
        self.set_status("Dispositivos encontrados.")

    def send_file(self):
        device = self.selected_text()
        if not device:
            self.set_status("Selecione um dispositivo.")
            return
        path = simpledialog.askstring("Warpinator", "Caminho do arquivo:", initialvalue="/Home/Documents/welcome.txt")
        if not path:
            return
        try:
            content = self.os.fs.read_file(path)
        except Exception as exc:
            self.set_status(str(exc))
            return
        sent_path = f"/Home/Downloads/sent-to-{device}.txt"
        self.os.fs.write_file(sent_path, content)
        self.set_status("Arquivo enviado para " + device)

    def set_power_profile(self, profile):
        self.os.app_state["power_profile"] = profile
        self.refresh_list(self.power_items())
        self.set_status("Perfil: " + profile)

    def power_items(self):
        return [f"Perfil: {self.os.app_state['power_profile']}", "Tela: 15 min", "Suspensao: 30 min", "Bateria: 96%"]

    def scan_bluetooth(self):
        devices = ["Headphones", "Keyboard", "Mouse", "Phone", "Speaker"]
        self.os.app_state["bluetooth"] = random.sample(devices, 3)
        self.refresh_list(self.os.app_state["bluetooth"])
        self.set_status("Bluetooth atualizado.")

    def pair_bluetooth(self):
        item = self.selected_text()
        if item:
            self.set_status(item + " pareado.")
        else:
            self.set_status("Selecione um dispositivo.")

    def create_archive(self):
        name = "archive-" + datetime.datetime.now().strftime("%H%M%S") + ".zip"
        manifest = "\n".join(path for path in ("/Home/Documents/welcome.txt", "/Home/Documents/todo.txt") if self.os.fs.exists(path))
        self.os.fs.write_file("/Home/Downloads/" + name, "Archive Manager\n" + manifest)
        self.os.app_state["archives"].append(name)
        self.refresh_list(self.os.app_state["archives"])
        self.set_status(name + " criado.")

    def extract_archive(self):
        item = self.selected_text()
        if not item:
            self.set_status("Selecione um arquivo.")
            return
        self.os.fs.write_file("/Home/Downloads/extracted-" + item + ".txt", "Conteudo extraido de " + item)
        self.set_status(item + " extraido.")

    def analyze_disk_usage(self):
        self.refresh_list(self.disk_usage_items())
        self.set_status("Analise concluida.")

    def disk_usage_items(self):
        counts = self.os.fs.count_items()
        return [f"Arquivos: {counts['files']}", f"Pastas: {counts['folders']}", f"Janelas abertas: {len(self.os.wm.windows)}"]

    def refresh_disks(self):
        self.refresh_list(self.os.app_state["disks"])
        self.set_status("Discos atualizados.")

    def eject_usb(self):
        self.os.app_state["disks"] = [disk for disk in self.os.app_state["disks"] if "USB" not in disk]
        self.refresh_list(self.os.app_state["disks"])
        self.set_status("USB ejetado.")

    def write_usb_image(self):
        self.os.fs.write_file("/System/usb-writer.log", "cinnix-1.0.iso gravado em USB Drive\n" + str(datetime.datetime.now()))
        self.set_status("Imagem gravada no USB.")

    def verify_usb_image(self):
        ok = self.os.fs.exists("/System/usb-writer.log")
        self.set_status("Imagem verificada." if ok else "Nenhuma imagem gravada.")

    def preview_font(self):
        item = self.selected_text() or "TkDefaultFont"
        self.set_status("Fonte selecionada: " + item)

    def open_document(self):
        self.os.open_text_editor("/Home/Documents/welcome.txt")
        self.set_status("Documento aberto.")

    def add_bookmark(self):
        self.os.app_state["bookmarks"].append(self.spec["name"] + " " + datetime.datetime.now().strftime("%H:%M"))
        self.set_status("Marcador adicionado.")

    def open_picture(self):
        item = self.selected_text() or "wallpaper-cinnix.png"
        self.set_status("Imagem aberta: " + item)

    def rotate_picture(self):
        item = self.selected_text() or "imagem"
        self.set_status(item + " girada 90 graus.")

    def add_generic_item(self):
        text = simpledialog.askstring(self.spec["name"], "Novo item:")
        if text:
            self.add_list_item(text)
            self.set_status("Item adicionado.")

    def save_generic_state(self):
        items = [self.listbox.get(i) for i in range(self.listbox.size())] if self.listbox else []
        path = f"/Home/Documents/{self.spec['id']}.txt"
        self.os.fs.write_file(path, "\n".join(items))
        self.set_status("Estado salvo em " + path)

    def office_new(self):
        if self.editor_text:
            self.editor_text.delete("1.0", "end")
            self.editor_text.insert("1.0", self.spec["name"] + "\n\n")
            self.set_status("Novo documento.")

    def office_save(self):
        if not self.editor_text:
            return
        ext = {
            "libreoffice-writer": "odt",
            "libreoffice-calc": "ods",
            "libreoffice-impress": "odp",
            "libreoffice-draw": "odg",
            "libreoffice-base": "odb",
        }.get(self.spec["id"], "txt")
        path = f"/Home/Documents/{self.spec['short'].lower()}.{ext}"
        self.os.fs.write_file(path, self.editor_text.get("1.0", "end-1c"))
        self.set_status("Salvo em " + path)

    def office_export_pdf(self):
        if not self.editor_text:
            return
        path = f"/Home/Documents/{self.spec['short'].lower()}.pdf"
        self.os.fs.write_file(path, "PDF EXPORT\n\n" + self.editor_text.get("1.0", "end-1c"))
        self.set_status("Exportado em " + path)


class AboutApp:
    def __init__(self, os_app, window):
        self.os = os_app
        self.window = window
        self.build()

    def build(self):
        root = self.window.content
        text = tk.Text(root, wrap="word")
        self.os.style_text(text)
        text.pack(fill="both", expand=True, padx=12, pady=12)
        text.insert(
            "1.0",
            (
                "Cinnix 1.0\n\n"
                "Um desktop completo em um unico arquivo Python.\n\n"
                "Recursos:\n"
                "- Gerenciador de janelas com foco, minimizar, maximizar e multitarefa\n"
                "- Menu iniciar e barra inferior com relogio\n"
                "- Sistema de arquivos virtual compartilhado\n"
                "- Terminal funcional com comandos basicos\n"
                "- Catalogo de apps do Cinnix com Nemo, Firefox, LibreOffice, Timeshift e mais\n"
                "- Icones, menu Cinnamon e visual arredondado\n"
                "- Temas claro/escuro e papel de parede configuravel\n\n"
                "Tudo usa somente Tkinter e biblioteca padrao; o navegador acessa a internet via urllib."
            ),
        )
        text.configure(state="disabled")


class CinnixSystem:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Cinnix 1.0")
        self.root.geometry("1180x720")
        self.root.minsize(900, 560)
        self.started_at = datetime.datetime.now()
        self.username = "cinnix"
        self.fs = VirtualFileSystem()
        self.app_state = {
            "updates": ["cinnamon 6.0.4 8.2 MB", "nemo 6.0.2 4.7 MB", "cinnix-update 7.1.1 2.1 MB"],
            "drivers": [],
            "catalog": ["Firefox", "Thunderbird", "LibreOffice", "Celluloid", "Rhythmbox", "Warpinator", "Remmina", "Transmission", "Pix", "Xreader"],
            "installed_packages": {"Firefox", "Thunderbird", "LibreOffice", "Nemo", "Xed"},
            "snapshots": [],
            "firewall_enabled": False,
            "firewall_rules": ["allow tcp 22", "deny tcp 23"],
            "mail": ["Inbox: Bem-vindo ao Thunderbird", "Inbox: Relatorio semanal"],
            "mail_archive": [],
            "torrents": ["cinnix-1.0.iso - 100%", "docs-pack.tar.gz - 34%"],
            "connections": ["RDP desktop-local", "VNC workstation", "SSH server"],
            "devices": ["desktop-sala", "notebook", "phone"],
            "bluetooth": ["Headphones", "Keyboard", "Phone"],
            "power_profile": "Balanceado",
            "disks": ["sda 128 GB ext4 montado em /", "sdb USB 16 GB montado em /media/usb", "loop0 Cinnix ISO"],
            "events": [datetime.date.today().strftime("%Y-%m-%d") + "  Revisar sistema"],
            "archives": ["backup-home.zip", "documentos.tar.gz"],
            "bookmarks": [],
            "notes": "Notas adesivas\n\n- Comprar cafe\n- Revisar atualizacoes\n- Testar Warpinator",
        }
        self.theme_name = "dark"
        self.show_seconds = tk.BooleanVar(value=False)
        self.menu_visible = False
        self.menu_category = "All"
        self.wallpaper = "#0f8f57"
        self.themes = {
            "dark": {
                "bg": "#202624",
                "desktop": "#0f8f57",
                "panel": "#202020",
                "window": "#2f3437",
                "titlebar": "#252a2d",
                "fg": "#f2f2f2",
                "muted": "#b8c0bd",
                "title_fg": "#ffffff",
                "button": "#3d4447",
                "button_hover": "#4b5457",
                "entry": "#1d2123",
                "border": "#111111",
                "accent": "#78c257",
                "accent_fg": "#101410",
                "text_bg": "#1d2123",
                "terminal_bg": "#111715",
                "terminal_fg": "#98e66e",
            },
            "light": {
                "bg": "#eef2ee",
                "desktop": "#6fbf73",
                "panel": "#303436",
                "window": "#f7faf7",
                "titlebar": "#e5ebe5",
                "fg": "#1d2520",
                "muted": "#53605a",
                "title_fg": "#1d2520",
                "button": "#e7ede8",
                "button_hover": "#d8e3da",
                "entry": "#ffffff",
                "border": "#9aa69d",
                "accent": "#3ca65a",
                "accent_fg": "#ffffff",
                "text_bg": "#ffffff",
                "terminal_bg": "#17201a",
                "terminal_fg": "#a3f27a",
            },
        }
        self.theme = self.themes[self.theme_name]
        self.app_specs = []
        self.app_specs_by_id = {}
        self.shell_ready = False
        self.installed = False
        self.oobe_done = False
        self.locked = False
        self.password = ""
        self.startup_frame = None
        self.boot_progress = 0
        self.install_progress = 0
        self.fps_counter = 0
        self.fps_last_time = time.perf_counter()
        self.performance_running = False
        self.oobe_step = 0
        self.oobe_data = {
            "language": "Português",
            "keyboard": "br-abnt2",
            "timezone": "America/Sao_Paulo",
            "username": self.username,
            "password": "",
            "theme": self.theme_name,
        }
        self.show_boot_screen()

    def clear_startup_screen(self):
        if self.startup_frame is not None:
            self.startup_frame.destroy()
            self.startup_frame = None

    def startup_button(self, master, text, command):
        button = tk.Button(
            master,
            text=text,
            command=command,
            bg=self.theme["accent"],
            fg=self.theme["accent_fg"],
            activebackground=self.mix(self.theme["accent"], "#ffffff", 0.18),
            activeforeground=self.theme["accent_fg"],
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            font=("Segoe UI", 10, "bold"),
        )
        return button

    def show_boot_screen(self):
        self.clear_startup_screen()
        self.root.configure(bg="#0d1110")
        self.startup_frame = tk.Frame(self.root, bg="#0d1110")
        self.startup_frame.pack(fill="both", expand=True)
        center = tk.Frame(self.startup_frame, bg="#0d1110")
        center.place(relx=0.5, rely=0.48, anchor="center")
        tk.Label(center, text="LM", bg="#0d1110", fg="#78c257", font=("Segoe UI", 54, "bold")).pack()
        tk.Label(center, text="Cinnix 1.0", bg="#0d1110", fg="#f4f4f4", font=("Segoe UI", 18, "bold")).pack(pady=(4, 22))
        self.boot_canvas = tk.Canvas(center, width=360, height=8, bg="#1d2421", highlightthickness=0, bd=0)
        self.boot_canvas.pack()
        self.boot_status = tk.Label(center, text="Inicializando firmware...", bg="#0d1110", fg="#9aa69d", font=("Consolas", 10))
        self.boot_status.pack(pady=(12, 0))
        self.boot_messages = [
            "Detectando ACPI e dispositivos",
            "Carregando kernel tk-6.6",
            "Montando sistema de arquivos",
            "Iniciando systemd user session",
            "Preparando instalador",
        ]
        self.boot_progress = 0
        self.animate_boot()

    def animate_boot(self):
        if not hasattr(self, "boot_canvas") or not self.boot_canvas.winfo_exists():
            return
        self.boot_progress += 4
        self.boot_canvas.delete("all")
        width = int(360 * min(self.boot_progress, 100) / 100)
        self.boot_canvas.create_rectangle(0, 0, width, 8, fill="#78c257", outline="")
        index = min(len(self.boot_messages) - 1, self.boot_progress // 22)
        self.boot_status.configure(text=self.boot_messages[index])
        if self.boot_progress >= 100:
            self.root.after(420, self.show_installer_terminal)
        else:
            self.root.after(90, self.animate_boot)

    def show_installer_terminal(self):
        self.clear_startup_screen()
        self.startup_frame = tk.Frame(self.root, bg="#101615")
        self.startup_frame.pack(fill="both", expand=True)
        header = tk.Frame(self.startup_frame, bg="#202020", height=40)
        header.pack(fill="x")
        tk.Label(header, text="  Cinnix Installer TTY1", bg="#202020", fg="#ffffff", font=("Segoe UI", 10, "bold")).pack(side="left", fill="y")
        body = tk.Frame(self.startup_frame, bg="#101615")
        body.pack(fill="both", expand=True, padx=28, pady=24)
        tk.Label(body, text="Instalador em terminal", bg="#101615", fg="#78c257", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(
            body,
            text="Digite install ou clique em Instalar para particionar, copiar pacotes e configurar o sistema.",
            bg="#101615",
            fg="#cbd5d0",
        ).pack(anchor="w", pady=(4, 12))
        self.installer_output = tk.Text(body, height=18, bg="#07100d", fg="#98e66e", insertbackground="#98e66e", relief="flat", font=("Consolas", 10))
        self.installer_output.pack(fill="both", expand=True)
        bottom = tk.Frame(body, bg="#101615")
        bottom.pack(fill="x", pady=(12, 0))
        tk.Label(bottom, text="cinnix-installer $ ", bg="#101615", fg="#98e66e", font=("Consolas", 10)).pack(side="left")
        self.installer_entry = tk.Entry(bottom, bg="#07100d", fg="#ffffff", insertbackground="#ffffff", relief="flat", font=("Consolas", 10))
        self.installer_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.installer_entry.bind("<Return>", self.run_installer_command)
        self.startup_button(bottom, "Instalar", self.start_terminal_install).pack(side="right", padx=(10, 0))
        self.installer_entry.focus_set()
        self.installer_log("Cinnix 1.0 live session")
        self.installer_log("Comandos: help, lsblk, check, install, reboot")

    def installer_log(self, text):
        self.installer_output.configure(state="normal")
        self.installer_output.insert("end", text + "\n")
        self.installer_output.see("end")
        self.installer_output.configure(state="disabled")

    def run_installer_command(self, _event=None):
        command = self.installer_entry.get().strip().lower()
        self.installer_entry.delete(0, "end")
        if not command:
            return
        self.installer_log("cinnix-installer $ " + command)
        if command == "help":
            self.installer_log("help       mostra comandos")
            self.installer_log("lsblk      lista discos detectados")
            self.installer_log("check      verifica rede, energia e disco")
            self.installer_log("install    instala o sistema")
            self.installer_log("reboot     continua para configuracao inicial")
        elif command == "lsblk":
            self.installer_log("NAME   SIZE TYPE MOUNTPOINT")
            self.installer_log("sda    128G disk")
            self.installer_log("sda1   512M part /boot/efi")
            self.installer_log("sda2   127G part /")
        elif command == "check":
            self.installer_log("[ OK ] disco com espaco suficiente")
            self.installer_log("[ OK ] sistema de arquivos virtual pronto")
            self.installer_log("[ OK ] rede sera configurada no desktop")
        elif command == "install":
            self.start_terminal_install()
        elif command == "reboot":
            self.show_oobe()
        else:
            self.installer_log("comando nao encontrado: " + command)

    def start_terminal_install(self):
        if self.installed:
            self.installer_log("sistema ja instalado; use reboot")
            return
        self.install_progress = 0
        self.installer_steps = [
            "Criando tabela GPT",
            "Formatando ext4",
            "Copiando base do sistema",
            "Instalando Cinnamon",
            "Instalando apps do Cinnix",
            "Configurando bootloader",
            "Gerando usuario inicial",
            "Finalizando instalacao",
        ]
        self.installer_log("iniciando instalacao...")
        self.advance_installation()

    def advance_installation(self):
        index = self.install_progress
        if index < len(self.installer_steps):
            self.installer_log(f"[{index + 1}/{len(self.installer_steps)}] {self.installer_steps[index]}... OK")
            self.install_progress += 1
            self.root.after(320, self.advance_installation)
            return
        self.installed = True
        self.fs.write_file("/System/install.log", "Instalado em " + str(datetime.datetime.now()))
        self.installer_log("instalacao concluida.")
        self.installer_log("reiniciando para o assistente inicial...")
        self.root.after(700, self.show_oobe)

    def show_oobe(self):
        self.clear_startup_screen()
        self.startup_frame = tk.Frame(self.root, bg=self.theme["bg"])
        self.startup_frame.pack(fill="both", expand=True)
        card = tk.Frame(self.startup_frame, bg=self.theme["window"], highlightthickness=1, highlightbackground=self.theme["border"])
        card.place(relx=0.5, rely=0.5, anchor="center", width=620, height=440)
        self.oobe_card = card
        self.render_oobe_step()

    def render_oobe_step(self):
        for child in self.oobe_card.winfo_children():
            child.destroy()
        steps = [
            ("Bem-vindo", "Escolha o idioma da sessao.", "language", ["Português", "English", "Español"]),
            ("Teclado", "Escolha o layout do teclado.", "keyboard", ["br-abnt2", "us", "pt"]),
            ("Fuso horario", "Ajuste data e hora.", "timezone", ["America/Sao_Paulo", "UTC", "Europe/Lisbon"]),
            ("Conta", "Crie o usuario principal.", "account", None),
            ("Aparencia", "Escolha o tema inicial.", "theme", ["dark", "light"]),
        ]
        title, subtitle, key, choices = steps[self.oobe_step]
        tk.Label(self.oobe_card, text="Cinnix Setup", bg=self.theme["window"], fg=self.theme["accent"], font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=28, pady=(24, 4))
        tk.Label(self.oobe_card, text=title, bg=self.theme["window"], fg=self.theme["fg"], font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=28)
        tk.Label(self.oobe_card, text=subtitle, bg=self.theme["window"], fg=self.theme["muted"], font=("Segoe UI", 10)).pack(anchor="w", padx=28, pady=(0, 20))
        content = tk.Frame(self.oobe_card, bg=self.theme["window"])
        content.pack(fill="both", expand=True, padx=28)
        if key == "account":
            tk.Label(content, text="Nome de usuario", bg=self.theme["window"], fg=self.theme["fg"]).pack(anchor="w")
            self.oobe_user_entry = tk.Entry(content)
            self.style_entry(self.oobe_user_entry)
            self.oobe_user_entry.insert(0, self.oobe_data["username"])
            self.oobe_user_entry.pack(fill="x", pady=(4, 12), ipady=6)
            tk.Label(content, text="Senha (opcional)", bg=self.theme["window"], fg=self.theme["fg"]).pack(anchor="w")
            self.oobe_password_entry = tk.Entry(content, show="*")
            self.style_entry(self.oobe_password_entry)
            self.oobe_password_entry.insert(0, self.oobe_data["password"])
            self.oobe_password_entry.pack(fill="x", pady=(4, 12), ipady=6)
        else:
            self.oobe_choice = tk.StringVar(value=self.oobe_data[key])
            for choice in choices:
                item = tk.Radiobutton(content, text=choice, value=choice, variable=self.oobe_choice, bg=self.theme["window"], fg=self.theme["fg"], selectcolor=self.theme["entry"], activebackground=self.theme["window"])
                item.pack(anchor="w", pady=5)
        nav = tk.Frame(self.oobe_card, bg=self.theme["window"])
        nav.pack(fill="x", padx=28, pady=22)
        if self.oobe_step > 0:
            self.startup_button(nav, "Voltar", self.prev_oobe_step).pack(side="left")
        text = "Concluir" if self.oobe_step == len(steps) - 1 else "Continuar"
        self.startup_button(nav, text, self.next_oobe_step).pack(side="right")

    def save_oobe_step(self):
        keys = ["language", "keyboard", "timezone", "account", "theme"]
        key = keys[self.oobe_step]
        if key == "account":
            self.oobe_data["username"] = self.oobe_user_entry.get().strip() or "cinnix"
            self.oobe_data["password"] = self.oobe_password_entry.get()
        else:
            self.oobe_data[key] = self.oobe_choice.get()

    def next_oobe_step(self):
        self.save_oobe_step()
        if self.oobe_step < 4:
            self.oobe_step += 1
            self.render_oobe_step()
            return
        self.finish_oobe()

    def prev_oobe_step(self):
        self.save_oobe_step()
        self.oobe_step = max(0, self.oobe_step - 1)
        self.render_oobe_step()

    def finish_oobe(self):
        self.oobe_done = True
        self.username = self.oobe_data["username"]
        self.password = self.oobe_data["password"]
        self.set_theme(self.oobe_data["theme"], quiet=True)
        self.fs.write_file(
            "/System/oobe.conf",
            "\n".join(f"{key}={value}" for key, value in self.oobe_data.items() if key != "password"),
        )
        self.start_desktop(locked=True)

    def start_desktop(self, locked=False):
        self.clear_startup_screen()
        if not self.shell_ready:
            self.build_shell()
            self.register_apps()
            self.create_desktop_icons()
            self.shell_ready = True
            self.update_clock()
            self.start_performance_monitor()
        if locked:
            self.show_lock_screen(first_login=True)
        else:
            self.root.after(400, self.open_welcome)

    def show_lock_screen(self, first_login=False):
        if not self.shell_ready:
            return
        self.locked = True
        self.lock_overlay = tk.Frame(self.root, bg="#101615")
        self.lock_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        box = tk.Frame(self.lock_overlay, bg="#17201a", highlightthickness=1, highlightbackground="#2f4438")
        box.place(relx=0.5, rely=0.5, anchor="center", width=420, height=300)
        tk.Label(box, text=datetime.datetime.now().strftime("%H:%M"), bg="#17201a", fg="#ffffff", font=("Segoe UI", 34, "bold")).pack(pady=(28, 4))
        tk.Label(box, text=datetime.datetime.now().strftime("%A, %d/%m/%Y"), bg="#17201a", fg="#a8b8ae", font=("Segoe UI", 10)).pack()
        tk.Label(box, text=self.username, bg="#17201a", fg="#78c257", font=("Segoe UI", 15, "bold")).pack(pady=(28, 8))
        self.lock_entry = tk.Entry(box, show="*", justify="center", bg="#0d1411", fg="#ffffff", insertbackground="#ffffff", relief="flat")
        self.lock_entry.pack(fill="x", padx=50, ipady=8)
        self.lock_entry.bind("<Return>", self.unlock_session)
        message = "Pressione Entrar" if not self.password else "Digite sua senha"
        self.lock_message = tk.Label(box, text=message, bg="#17201a", fg="#a8b8ae")
        self.lock_message.pack(pady=(8, 16))
        self.startup_button(box, "Desbloquear", self.unlock_session).pack()
        self.lock_entry.focus_set()
        self.lock_overlay.lift()
        self.first_login_after_unlock = first_login

    def unlock_session(self, _event=None):
        typed = self.lock_entry.get()
        if self.password and typed != self.password:
            self.lock_message.configure(text="Senha incorreta")
            self.lock_entry.delete(0, "end")
            return
        self.locked = False
        self.lock_overlay.destroy()
        if getattr(self, "first_login_after_unlock", False):
            self.first_login_after_unlock = False
            self.root.after(350, self.open_welcome)

    def build_shell(self):
        self.desktop = tk.Frame(self.root, bg=self.wallpaper)
        self.desktop.pack(fill="both", expand=True)
        self.panel = tk.Frame(self.root, height=44, bg=self.theme["panel"])
        self.panel.pack(fill="x", side="bottom")
        self.panel.pack_propagate(False)

        self.menu_button = tk.Button(self.panel, text="●  Menu", command=self.toggle_menu, width=11)
        self.style_panel_button(self.menu_button)
        self.menu_button.pack(side="left", padx=6, pady=5)

        self.taskbar = tk.Frame(self.panel, bg=self.theme["panel"])
        self.taskbar.pack(side="left", fill="both", expand=True)
        self.tray = tk.Frame(self.panel, bg=self.theme["panel"])
        self.tray.pack(side="right", fill="y")
        self.theme_button = tk.Button(self.tray, text="◐", command=self.toggle_theme, width=4)
        self.style_panel_button(self.theme_button)
        self.theme_button.pack(side="left", padx=4, pady=5)
        self.fps_label = tk.Label(self.tray, text="FPS --", bg=self.theme["panel"], fg="#d7f5d0", padx=8, font=("Consolas", 9))
        self.fps_label.pack(side="left", fill="y")
        self.ram_label = tk.Label(self.tray, text="RAM -- MB", bg=self.theme["panel"], fg="#d7f5d0", padx=8, font=("Consolas", 9))
        self.ram_label.pack(side="left", fill="y")
        self.clock = tk.Label(self.tray, text="", bg=self.theme["panel"], fg="white", padx=10)
        self.clock.pack(side="left", fill="y")

        self.menu = tk.Frame(self.root, bd=0, relief="flat", highlightthickness=1)
        self.menu_header = tk.Frame(self.menu, height=66)
        self.menu_header.pack(fill="x")
        self.menu_user_icon = tk.Label(self.menu_header, text="●", font=("Segoe UI Symbol", 28, "bold"), width=3)
        self.menu_user_icon.pack(side="left", padx=(12, 4), pady=10)
        self.menu_title = tk.Label(self.menu_header, text="Cinnix", anchor="w", font=("Segoe UI", 14, "bold"))
        self.menu_title.pack(side="left", fill="x", expand=True)
        self.menu_search = tk.Entry(self.menu)
        self.menu_search.pack(fill="x", padx=12, pady=(0, 10), ipady=5)
        self.menu_search.bind("<KeyRelease>", lambda _event: self.populate_menu())
        self.menu_body = tk.Frame(self.menu)
        self.menu_body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.menu_categories = tk.Frame(self.menu_body, width=156)
        self.menu_categories.pack(side="left", fill="y", padx=(0, 10))
        self.menu_apps_area = tk.Frame(self.menu_body)
        self.menu_apps_area.pack(side="left", fill="both", expand=True)
        self.menu_canvas = tk.Canvas(self.menu_apps_area, highlightthickness=0, bd=0)
        self.menu_scrollbar = tk.Scrollbar(self.menu_apps_area, orient="vertical", command=self.menu_canvas.yview)
        self.menu_list = tk.Frame(self.menu_canvas)
        self.menu_list.bind("<Configure>", lambda _event: self.menu_canvas.configure(scrollregion=self.menu_canvas.bbox("all")))
        self.menu_canvas.create_window((0, 0), window=self.menu_list, anchor="nw")
        self.menu_canvas.configure(yscrollcommand=self.menu_scrollbar.set)
        self.menu_canvas.pack(side="left", fill="both", expand=True)
        self.menu_scrollbar.pack(side="right", fill="y")

        self.notification = tk.Label(self.root, text="", anchor="w")
        self.notification.place_forget()

        self.wm = WindowManager(self, self.desktop, self.taskbar)

    def app(self, app_id, name, icon, color, category, factory, short=None, tagline="", items=None, kind="utility", template=None):
        return {
            "id": app_id,
            "name": name,
            "icon": icon,
            "color": color,
            "category": category,
            "factory": factory,
            "short": short or name,
            "tagline": tagline,
            "items": items,
            "kind": kind,
            "template": template,
            "description": tagline or f"{name} integrado ao ambiente Cinnamon.",
        }

    def get_app_spec(self, app_id):
        if not hasattr(self, "app_specs_by_id"):
            return None
        return self.app_specs_by_id.get(app_id)

    def mix(self, color, other, amount=0.5):
        def parse(value):
            value = value.lstrip("#")
            return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))

        a = parse(color)
        b = parse(other)
        c = tuple(int(a[i] * (1 - amount) + b[i] * amount) for i in range(3))
        return "#%02x%02x%02x" % c

    def register_apps(self):
        self.app_categories = ["All", "Favorites", "Accessories", "Administration", "Internet", "Office", "Graphics", "Sound & Video", "Preferences"]
        self.app_specs = [
            self.app("nemo", "Nemo", "▣", "#46a35f", "Accessories", lambda: self.open_file_manager("/Home"), "Arquivos", "Gerenciador de arquivos do Cinnamon"),
            self.app("cinnamon-settings", "Cinnamon Settings", "⚙", "#6c8cff", "Preferences", self.open_settings, "Settings", "Preferencias do Cinnamon"),
            self.app("cinnamon-control-center", "Cinnamon Control Center", "◉", "#4f8cc9", "Preferences", lambda: self.open_generic_app("cinnamon-control-center"), "Control", "Central de controle do sistema"),
            self.app("update-manager", "Update Manager", "↻", "#4dbb64", "Administration", lambda: self.open_generic_app("update-manager"), "Update", "Gerencia atualizacoes locais", ["cinnix-update", "security patches", "kernel updates"]),
            self.app("driver-manager", "Driver Manager", "◈", "#607d8b", "Administration", lambda: self.open_generic_app("driver-manager"), "Drivers", "Seleciona drivers recomendados", ["GPU: driver livre ativo", "Wi-Fi: driver integrado", "Bluetooth: pronto"]),
            self.app("software-manager", "Software Manager", "+", "#63b246", "Administration", lambda: self.open_generic_app("software-manager"), "Software", "Gerencia pacotes locais", ["Firefox", "Thunderbird", "LibreOffice", "GIMP", "VLC"]),
            self.app("timeshift", "Timeshift", "↺", "#8a6fd1", "Administration", lambda: self.open_generic_app("timeshift"), "Timeshift", "Snapshots do sistema", ["Snapshot diario", "Snapshot semanal", "Snapshot antes de atualizar"]),
            self.app("system-monitor", "System Monitor", "▥", "#2aa7a7", "Administration", self.open_monitor, "Monitor", "Processos e desempenho"),
            self.app("power-manager", "Power Manager", "⏻", "#e3a23b", "Preferences", lambda: self.open_generic_app("power-manager"), "Energia", "Energia e bateria", ["Perfil: balanceado", "Tela: suspender em 15 min", "Bateria: 96%"]),
            self.app("firewall", "Firewall Configuration", "◆", "#d85a5a", "Administration", lambda: self.open_generic_app("firewall"), "Firewall", "Regras de seguranca", ["Entrada: negada", "Saida: permitida", "Perfil: Casa"]),
            self.app("firefox", "Firefox", "●", "#e8652b", "Internet", self.open_browser, "Firefox", "Navegador web com HTTP/HTTPS real"),
            self.app("thunderbird", "Thunderbird", "✉", "#3f7edb", "Internet", lambda: self.open_generic_app("thunderbird"), "Mail", "Cliente de email", ["Inbox", "Drafts", "Sent", "Archive"]),
            self.app("transmission", "Transmission", "⇩", "#d94d45", "Internet", lambda: self.open_generic_app("transmission"), "Torrents", "Cliente BitTorrent", ["ubuntu.iso - pausado", "mint.iso - completo"]),
            self.app("remmina", "Remmina", "▤", "#8b6bc9", "Internet", lambda: self.open_generic_app("remmina"), "Remmina", "Desktop remoto", ["RDP localhost", "VNC servidor-dev", "SSH mint-box"]),
            self.app("warpinator", "Warpinator", "⇄", "#2fab6f", "Internet", lambda: self.open_generic_app("warpinator"), "Warpinator", "Compartilhamento local", ["desktop-sala", "notebook", "phone"]),
            self.app("celluloid", "Celluloid", "▶", "#505a66", "Sound & Video", lambda: self.open_generic_app("celluloid"), "Celluloid", "Player de video", ["video-demo.mp4", "trailer.webm"], kind="media"),
            self.app("rhythmbox", "Rhythmbox", "♫", "#c458a8", "Sound & Video", lambda: self.open_generic_app("rhythmbox"), "Music", "Biblioteca musical", ["Mint Theme.ogg", "Session Start.wav", "Lo-fi Offline.mp3"], kind="media"),
            self.app("pix", "Pix", "▧", "#55aeb0", "Graphics", lambda: self.open_generic_app("pix"), "Pix", "Visualizador de imagens", ["wallpaper-cinnix.png", "screenshot.png", "avatar.jpg"], kind="grid"),
            self.app("xreader", "Xreader", "▤", "#b88445", "Office", lambda: self.open_generic_app("xreader"), "Xreader", "Leitor de documentos", ["Manual Cinnix.pdf", "Notas.txt"]),
            self.app("gnome-screenshot", "Gnome Screenshot", "▣", "#6aa84f", "Accessories", lambda: self.open_generic_app("gnome-screenshot"), "Screenshot", "Captura de tela"),
            self.app("libreoffice-writer", "LibreOffice Writer", "W", "#3169b1", "Office", lambda: self.open_generic_app("libreoffice-writer"), "Writer", "Documento de texto", kind="office", template="Documento sem titulo\n\nComece a escrever aqui."),
            self.app("libreoffice-calc", "LibreOffice Calc", "C", "#279d55", "Office", lambda: self.open_generic_app("libreoffice-calc"), "Calc", "Planilha", kind="office", template="A1\tB1\tC1\n10\t20\t=SUM(A1:B1)"),
            self.app("libreoffice-impress", "LibreOffice Impress", "I", "#d87933", "Office", lambda: self.open_generic_app("libreoffice-impress"), "Impress", "Apresentacao", kind="office", template="Slide 1\nTitulo da apresentacao\n\nSlide 2\nTopicos principais"),
            self.app("libreoffice-draw", "LibreOffice Draw", "D", "#d2a135", "Office", lambda: self.open_generic_app("libreoffice-draw"), "Draw", "Desenho vetorial", kind="office", template="Canvas de desenho\n\n[retangulo] [circulo] [linha]"),
            self.app("libreoffice-base", "LibreOffice Base", "B", "#7d5fb2", "Office", lambda: self.open_generic_app("libreoffice-base"), "Base", "Banco de dados", kind="office", template="Tabela: contatos\nid | nome | email\n1  | Cinnix | cinnix@example.local"),
            self.app("xed", "Xed", "✎", "#4caf70", "Accessories", lambda: self.open_text_editor(), "Xed", "Editor de texto"),
            self.app("terminal", "Terminal", "▰", "#303030", "Accessories", self.open_terminal, "Terminal", "Emulador de terminal"),
            self.app("archive-manager", "Archive Manager", "▦", "#9b7846", "Accessories", lambda: self.open_generic_app("archive-manager"), "Archive", "Compactar e extrair", ["backup.tar.gz", "documentos.zip"]),
            self.app("calculator", "Calculator", "=", "#607d8b", "Accessories", self.open_calculator, "Calc", "Calculadora"),
            self.app("disk-usage", "Disk Usage Analyzer", "◔", "#5b8bc0", "Administration", lambda: self.open_generic_app("disk-usage"), "Usage", "Uso de disco", ["/Home 42%", "/System 18%", "/Trash 2%"]),
            self.app("disks", "Disks", "◍", "#67727a", "Administration", lambda: self.open_generic_app("disks"), "Disks", "Discos e particoes", ["sda 128 GB", "sdb USB 16 GB", "loop0 Cinnix 1.0 ISO"]),
            self.app("usb-image-writer", "USB Image Writer", "▰", "#55a0c7", "Administration", lambda: self.open_generic_app("usb-image-writer"), "USB", "Gravar imagem USB", ["cinnix-1.0.iso", "USB Drive /dev/sdb"]),
            self.app("font-viewer", "Font Viewer", "A", "#7f8c8d", "Accessories", lambda: self.open_generic_app("font-viewer"), "Fonts", "Visualizador de fontes", ["Segoe UI", "Consolas", "TkDefaultFont"], kind="grid"),
            self.app("sticky-notes", "Sticky Notes", "◆", "#d3b43f", "Accessories", lambda: self.open_generic_app("sticky-notes"), "Notes", "Notas adesivas", kind="notes"),
            self.app("calendar", "Calendar", "▣", "#4f8cc9", "Accessories", lambda: self.open_generic_app("calendar"), "Calendar", "Calendario", kind="calendar"),
            self.app("bluetooth", "Bluetooth Manager", "⌁", "#3d73d9", "Preferences", lambda: self.open_generic_app("bluetooth"), "Bluetooth", "Dispositivos Bluetooth", ["Headphones", "Keyboard", "Phone"]),
            self.app("about", "About", "?", "#6c8cff", "Preferences", self.open_about, "About", "Sobre este sistema"),
        ]
        self.app_specs_by_id = {spec["id"]: spec for spec in self.app_specs}
        self.populate_menu()

    def create_desktop_icons(self):
        icons = [
            ("nemo", 24, 24),
            ("firefox", 24, 108),
            ("terminal", 24, 192),
            ("xed", 24, 276),
            ("software-manager", 24, 360),
            ("cinnamon-settings", 24, 444),
        ]
        for app_id, x, y in icons:
            spec = self.get_app_spec(app_id)
            if not spec:
                continue
            icon = DesktopIcon(self.desktop, self, spec, lambda value=app_id: self.launch_app(value))
            icon.place(x=x, y=y, width=98, height=78)

    def open_welcome(self):
        self.open_about()

    def toggle_menu(self):
        if self.menu_visible:
            self.hide_menu()
        else:
            self.show_menu()

    def show_menu(self):
        self.menu_visible = True
        self.apply_menu_theme()
        self.populate_menu()
        panel_height = self.panel.winfo_height() or 40
        self.menu.place(x=8, y=max(8, self.root.winfo_height() - panel_height - 562), width=650, height=550)
        self.menu.lift()
        self.menu_search.focus_set()

    def hide_menu(self):
        self.menu_visible = False
        self.menu.place_forget()

    def populate_menu(self):
        for child in self.menu_list.winfo_children():
            child.destroy()
        for child in self.menu_categories.winfo_children():
            child.destroy()
        query = self.menu_search.get().strip().lower() if hasattr(self, "menu_search") else ""
        for category in self.app_categories:
            text = "★ Favoritos" if category == "Favorites" else ("Todos" if category == "All" else category)
            button = tk.Button(self.menu_categories, text=text, anchor="w", command=lambda value=category: self.set_menu_category(value))
            self.style_button(button)
            if category == self.menu_category:
                button.configure(bg=self.theme["accent"], fg=self.theme["accent_fg"])
            button.pack(fill="x", pady=2)

        favorites = {"nemo", "firefox", "terminal", "xed", "software-manager", "cinnamon-settings"}
        shown = 0
        for spec in self.app_specs:
            haystack = (spec["name"] + " " + spec["id"] + " " + spec["category"]).lower()
            if query and query not in haystack:
                continue
            if not query:
                if self.menu_category == "Favorites" and spec["id"] not in favorites:
                    continue
                if self.menu_category not in ("All", "Favorites") and spec["category"] != self.menu_category:
                    continue
            row = tk.Frame(self.menu_list, highlightthickness=0)
            self.style_frame(row)
            row.pack(fill="x", pady=2)
            icon = IconCanvas(row, self, spec, size=38, command=lambda app_id=spec["id"]: self.menu_launch(app_id))
            icon.pack(side="left", padx=(0, 8))
            label = f"{spec['name']}\n{spec.get('tagline', spec['category'])}"
            button = tk.Button(row, text=label, justify="left", anchor="w", command=lambda app_id=spec["id"]: self.menu_launch(app_id))
            self.style_button(button)
            button.pack(side="left", fill="x", expand=True)
            shown += 1
        if shown == 0:
            empty = tk.Label(self.menu_list, text="Nenhum aplicativo encontrado", anchor="w")
            self.style_label(empty)
            empty.pack(fill="x", pady=8)
        sep = tk.Frame(self.menu_list, height=1, bg=self.theme["border"])
        sep.pack(fill="x", pady=8)
        for label, command in (("⏾  Bloquear tela", self.show_lock_screen), ("⏻  Sair", self.root.quit)):
            button = tk.Button(self.menu_list, text=label, anchor="w", command=command)
            self.style_button(button)
            button.pack(fill="x", pady=2)
        self.menu_canvas.yview_moveto(0)

    def set_menu_category(self, category):
        self.menu_category = category
        self.populate_menu()

    def menu_launch(self, app_id):
        self.hide_menu()
        self.launch_app(app_id)

    def launch_app(self, app_id):
        key = app_id.lower()
        aliases = {
            "arquivo": "nemo",
            "arquivos": "nemo",
            "files": "nemo",
            "file-manager": "nemo",
            "settings": "cinnamon-settings",
            "config": "cinnamon-settings",
            "browser": "firefox",
            "navegador": "firefox",
            "editor": "xed",
            "text": "xed",
            "calc": "calculator",
        }
        key = aliases.get(key, key)
        for spec in self.app_specs:
            if key in (spec["id"], spec["name"].lower(), spec.get("short", "").lower()):
                spec["factory"]()
                return
        self.notify("Apps", f"Aplicativo nao encontrado: {app_id}")

    def open_file_manager(self, path="/Home"):
        window = self.wm.create("Nemo - " + path, "nemo", 800, 500)
        FileManagerApp(self, window, path)

    def open_text_editor(self, path=None):
        window = self.wm.create("Xed", "xed", 740, 510)
        TextEditorApp(self, window, path)

    def open_terminal(self):
        window = self.wm.create("Terminal", "terminal", 760, 450)
        TerminalApp(self, window)

    def open_browser(self):
        window = self.wm.create("Firefox", "firefox", 780, 520)
        BrowserApp(self, window)

    def open_settings(self):
        window = self.wm.create("Cinnamon Settings", "cinnamon-settings", 700, 500)
        SettingsApp(self, window)

    def open_calculator(self):
        window = self.wm.create("Calculadora", "calculator", 340, 430)
        CalculatorApp(self, window)

    def open_monitor(self):
        window = self.wm.create("System Monitor", "system-monitor", 580, 430)
        SystemMonitorApp(self, window)

    def open_about(self):
        window = self.wm.create("Sobre o Sistema", "about", 600, 440)
        AboutApp(self, window)

    def open_generic_app(self, app_id):
        spec = self.get_app_spec(app_id)
        if not spec:
            self.notify("Apps", f"Aplicativo nao encontrado: {app_id}")
            return
        width = 760 if spec.get("kind") in ("office", "grid") else 640
        height = 520 if spec.get("kind") in ("office", "grid") else 450
        window = self.wm.create(spec["name"], spec["id"], width, height)
        GenericCinnixApp(self, window, spec)

    def notify(self, title, message):
        self.notification.configure(text=f"{title}: {message}")
        self.style_notification(self.notification)
        self.notification.place(relx=1.0, x=-18, y=18, anchor="ne", width=330, height=46)
        self.notification.lift()
        self.root.after(2600, self.notification.place_forget)

    def update_clock(self):
        fmt = "%H:%M:%S" if self.show_seconds.get() else "%H:%M"
        self.clock.configure(text=datetime.datetime.now().strftime(fmt))
        self.root.after(1000, self.update_clock)

    def start_performance_monitor(self):
        if self.performance_running:
            return
        self.performance_running = True
        self.fps_counter = 0
        self.fps_last_time = time.perf_counter()
        self.fps_label.configure(text="FPS 00.0")
        self.ram_label.configure(text=f"RAM {self.process_memory_mb():05.1f} MB")
        self.performance_tick()

    def performance_tick(self):
        if not self.shell_ready:
            return
        self.fps_counter += 1
        now = time.perf_counter()
        elapsed = now - self.fps_last_time
        if elapsed >= 1.0:
            fps = self.fps_counter / elapsed
            ram = self.process_memory_mb()
            self.fps_label.configure(text=f"FPS {fps:04.1f}")
            self.ram_label.configure(text=f"RAM {ram:05.1f} MB")
            self.fps_counter = 0
            self.fps_last_time = now
        self.root.after(16, self.performance_tick)

    def process_memory_mb(self):
        if os.name == "nt":
            try:
                import ctypes

                class ProcessMemoryCounters(ctypes.Structure):
                    _fields_ = [
                        ("cb", ctypes.c_ulong),
                        ("PageFaultCount", ctypes.c_ulong),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t),
                    ]

                counters = ProcessMemoryCounters()
                counters.cb = ctypes.sizeof(counters)
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                psapi = ctypes.WinDLL("psapi.dll")
                psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessMemoryCounters), ctypes.c_ulong]
                psapi.GetProcessMemoryInfo.restype = ctypes.c_int
                ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
                if ok:
                    return counters.WorkingSetSize / (1024 * 1024)
            except Exception:
                pass
        try:
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if platform.system() == "Darwin":
                return usage / (1024 * 1024)
            return usage / 1024
        except Exception:
            return 0.0

    def toggle_theme(self):
        self.set_theme("light" if self.theme_name == "dark" else "dark")

    def set_theme(self, name, quiet=False):
        name = name.lower()
        if name in ("luminix-light", "cinnix-light", "claro"):
            name = "light"
        if name in ("luminix-dark", "cinnix-dark", "escuro"):
            name = "dark"
        if name not in self.themes:
            if not quiet and hasattr(self, "notification"):
                self.notify("Tema", "Tema desconhecido.")
            return
        self.theme_name = name
        self.theme = self.themes[name]
        if self.shell_ready:
            self.apply_theme()
        if not quiet and hasattr(self, "notification"):
            self.notify("Tema", "Tema alterado.")

    def set_wallpaper(self, color):
        self.wallpaper = color
        self.desktop.configure(bg=color)
        for child in self.desktop.winfo_children():
            if isinstance(child, DesktopIcon):
                child.draw(False)
                continue
            if isinstance(child, tk.Button) and child not in [w.frame for w in self.wm.windows]:
                try:
                    child.configure(bg=color)
                except tk.TclError:
                    pass

    def apply_theme(self):
        self.root.configure(bg=self.theme["bg"])
        self.desktop.configure(bg=self.wallpaper)
        self.panel.configure(bg=self.theme["panel"])
        self.taskbar.configure(bg=self.theme["panel"])
        self.tray.configure(bg=self.theme["panel"])
        self.clock.configure(bg=self.theme["panel"], fg="#ffffff")
        self.fps_label.configure(bg=self.theme["panel"], fg="#d7f5d0")
        self.ram_label.configure(bg=self.theme["panel"], fg="#d7f5d0")
        self.style_panel_button(self.menu_button)
        self.style_panel_button(self.theme_button)
        self.apply_menu_theme()
        self.wm.apply_theme()
        self.restyle_tree(self.root)
        self.apply_menu_theme()
        for child in self.desktop.winfo_children():
            if isinstance(child, DesktopIcon):
                child.draw(False)

    def apply_menu_theme(self):
        self.menu.configure(bg=self.theme["window"], highlightbackground=self.theme["border"])
        self.menu_header.configure(bg=self.theme["titlebar"])
        self.menu_user_icon.configure(bg=self.theme["titlebar"], fg=self.theme["accent"])
        self.menu_title.configure(bg=self.theme["titlebar"], fg=self.theme["title_fg"])
        self.menu_body.configure(bg=self.theme["window"])
        self.menu_categories.configure(bg=self.theme["window"])
        self.menu_apps_area.configure(bg=self.theme["window"])
        self.menu_canvas.configure(bg=self.theme["window"])
        self.menu_list.configure(bg=self.theme["window"])
        self.style_entry(self.menu_search)

    def restyle_tree(self, widget):
        for child in widget.winfo_children():
            if child in (self.desktop, self.panel, self.menu, self.notification):
                self.restyle_tree(child)
                continue
            if isinstance(child, tk.Button):
                self.style_button(child)
            elif isinstance(child, tk.Entry):
                self.style_entry(child)
            elif isinstance(child, tk.Text):
                self.style_text(child)
            elif isinstance(child, tk.Listbox):
                self.style_listbox(child)
            elif isinstance(child, tk.Label):
                self.style_label(child)
            elif isinstance(child, tk.Frame):
                self.style_frame(child)
            elif isinstance(child, tk.Checkbutton):
                self.style_check(child)
            self.restyle_tree(child)

    def style_frame(self, widget):
        widget.configure(bg=self.theme["window"])

    def style_label(self, widget):
        widget.configure(bg=self.theme["window"], fg=self.theme["fg"])

    def style_button(self, widget, compact=False):
        widget.configure(
            bg=self.theme["button"],
            fg=self.theme["fg"],
            activebackground=self.theme["accent"],
            activeforeground=self.theme["accent_fg"],
            relief="flat",
            bd=0,
            padx=4 if compact else 8,
            pady=2 if compact else 5,
        )

    def style_panel_button(self, widget):
        widget.configure(
            bg=self.theme["panel"],
            fg="#ffffff",
            activebackground=self.theme["accent"],
            activeforeground=self.theme["accent_fg"],
            relief="flat",
            bd=0,
        )

    def style_desktop_icon(self, widget):
        widget.configure(
            bg=self.wallpaper,
            fg="#ffffff",
            activebackground=self.theme["accent"],
            activeforeground=self.theme["accent_fg"],
            relief="flat",
            bd=0,
            wraplength=82,
        )

    def style_entry(self, widget):
        widget.configure(
            bg=self.theme["entry"],
            fg=self.theme["fg"],
            insertbackground=self.theme["fg"],
            relief="flat",
            bd=1,
            highlightthickness=1,
            highlightbackground=self.theme["border"],
        )

    def style_text(self, widget):
        widget.configure(
            bg=self.theme["text_bg"],
            fg=self.theme["fg"],
            insertbackground=self.theme["fg"],
            selectbackground=self.theme["accent"],
            selectforeground=self.theme["accent_fg"],
            relief="flat",
            bd=0,
            padx=8,
            pady=8,
        )

    def style_terminal(self, widget):
        widget.configure(
            bg=self.theme["terminal_bg"],
            fg=self.theme["terminal_fg"],
            insertbackground=self.theme["terminal_fg"],
            selectbackground=self.theme["accent"],
            relief="flat",
            bd=0,
            padx=8,
            pady=8,
            font=("Consolas", 10),
        )

    def style_listbox(self, widget):
        widget.configure(
            bg=self.theme["text_bg"],
            fg=self.theme["fg"],
            selectbackground=self.theme["accent"],
            selectforeground=self.theme["accent_fg"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=self.theme["border"],
        )

    def style_check(self, widget):
        widget.configure(
            bg=self.theme["window"],
            fg=self.theme["fg"],
            activebackground=self.theme["window"],
            activeforeground=self.theme["fg"],
            selectcolor=self.theme["entry"],
        )

    def style_notification(self, widget):
        widget.configure(
            bg=self.theme["titlebar"],
            fg=self.theme["title_fg"],
            relief="solid",
            bd=1,
            padx=10,
        )

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    CinnixSystem().run()
