#!/usr/bin/env python3
"""
局域网文件共享工具 v2
- GUI 界面，拖拽/按钮添加共享文件夹
- 支持多文件夹同时共享，每个文件夹自动分配端口
- 启动/停止单个共享，一键启动全部
- 显示访问地址，双击复制
"""

import http.server
import socketserver
import socket
import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from urllib.parse import unquote

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>文件共享 - {title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: "Microsoft YaHei","PingFang SC",sans-serif; background: #f5f5f5; color: #333; }}
.header {{ background: linear-gradient(135deg, #1a3a5c, #2a5a8c); color: #fff; padding: 24px 32px; }}
.header h1 {{ font-size: 20px; font-weight: 600; }}
.header p {{ font-size: 12px; opacity: .7; margin-top: 4px; }}
.container {{ max-width: 960px; margin: 0 auto; padding: 24px 16px; }}
.breadcrumb {{ font-size: 13px; margin-bottom: 16px; }}
.breadcrumb a {{ color: #1a3a5c; text-decoration: none; }}
.breadcrumb a:hover {{ text-decoration: underline; }}
.toolbar {{ margin-bottom: 20px; }}
.toolbar input {{ width: 100%; padding: 10px 14px; border: 1px solid #ccc; border-radius: 6px; font-size: 14px; }}
.toolbar input:focus {{ outline: none; border-color: #1a3a5c; }}
table {{ width: 100%; background: #fff; border-radius: 8px; border-collapse: collapse; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
th {{ background: #f0f4f8; color: #555; font-size: 12px; text-align: left; padding: 10px 16px; border-bottom: 1px solid #e0e6ec; }}
td {{ padding: 10px 16px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }}
tr:hover {{ background: #f8fafc; }}
.name a {{ color: #1a3a5c; text-decoration: none; font-weight: 500; }}
.name a:hover {{ text-decoration: underline; }}
.size {{ color: #888; font-size: 13px; text-align: right; white-space: nowrap; }}
.type {{ color: #aaa; font-size: 12px; }}
.empty {{ text-align: center; padding: 60px; color: #aaa; }}
.footer {{ text-align: center; padding: 20px; font-size: 12px; color: #aaa; }}
</style>
</head>
<body>
<div class="header"><h1>📁 {title}</h1><p>{root_path}</p></div>
<div class="container">
<div class="breadcrumb"><a href="/">🏠 根</a> {breadcrumb}</div>
<div class="toolbar"><input type="text" id="f" placeholder="🔍 搜索..." oninput="(function(q){{var rs=document.querySelectorAll('#t tbody tr');var an=false;rs.forEach(function(r){{var n=r.querySelector('.name a');if(!n)return;if(!q||n.textContent.toLowerCase().indexOf(q)!==-1){{r.style.display='';an=true}}else{{r.style.display='none'}}}});document.getElementById('e').style.display=an?'none':''}})(this.value.toLowerCase())"></div>
<table id="t"><thead><tr><th>名称</th><th style="width:120px">大小</th><th style="width:100px">类型</th></tr></thead><tbody>{rows}</tbody></table>
<div id="e" class="empty" style="display:none">📭 无匹配</div>
</div>
</body>
</html>"""


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def format_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def get_file_type(filename):
    ext = filename.rsplit(".", 1)
    if len(ext) == 1:
        return "文件夹"
    ext = ext[1].lower()
    icons = {
        "pdf": "PDF", "doc": "Word", "docx": "Word",
        "xls": "Excel", "xlsx": "Excel", "ppt": "PPT", "pptx": "PPT",
        "jpg": "图片", "jpeg": "图片", "png": "图片", "gif": "图片",
        "mp4": "视频", "avi": "视频", "mkv": "视频",
        "mp3": "音频", "wav": "音频", "flac": "音频",
        "zip": "压缩包", "rar": "压缩包", "7z": "压缩包",
        "txt": "文本", "py": "代码", "exe": "程序",
    }
    return icons.get(ext, ext.upper())


class FileShareHandler(http.server.SimpleHTTPRequestHandler):
    share_dir = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=self.share_dir, **kwargs)

    def log_message(self, format, *args):
        pass  # 静默日志

    def do_GET(self):
        path = unquote(self.path)
        local_path = os.path.join(self.share_dir, path.lstrip("/"))

        if os.path.isfile(local_path):
            return super().do_GET()

        if os.path.isdir(local_path):
            return self._serve_dir(local_path, path)

        self.send_error(404)

    def _serve_dir(self, dir_path, url_path):
        try:
            entries = os.listdir(dir_path)
        except OSError:
            self.send_error(403)
            return

        dirs, files = [], []
        for name in entries:
            full = os.path.join(dir_path, name)
            try:
                if os.path.isdir(full):
                    dirs.append((name, 0, "文件夹"))
                else:
                    files.append((name, os.path.getsize(full), get_file_type(name)))
            except OSError:
                continue

        dirs.sort(key=lambda x: x[0].lower())
        files.sort(key=lambda x: x[0].lower())

        rows = []
        for name, size, ftype in dirs + files:
            if ftype == "文件夹":
                rows.append(f'<tr><td class="name">📁 <a href="{name}/">{name}/</a></td><td class="size">-</td><td class="type">{ftype}</td></tr>')
            else:
                rows.append(f'<tr><td class="name">📄 <a href="{name}" download>{name}</a></td><td class="size">{format_size(size)}</td><td class="type">{ftype}</td></tr>')

        breadcrumb = ""
        if url_path != "/":
            parts = [p for p in url_path.split("/") if p]
            acc = ""
            bc = []
            for i, p in enumerate(parts):
                acc += "/" + p
                bc.append(f'<span>{p}</span>' if i == len(parts) - 1 else f'<a href="{acc}/">{p}</a>')
            breadcrumb = " / " + " / ".join(bc)

        rel = os.path.relpath(dir_path, self.share_dir)
        title = rel if rel != "." else os.path.basename(self.share_dir)

        html = TEMPLATE.format(
            title=title, root_path=self.share_dir, breadcrumb=breadcrumb,
            rows="\n".join(rows) if rows else '<tr><td colspan="3" class="empty">📭 空目录</td></tr>'
        )

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))


def make_handler(share_dir):
    class Handler(FileShareHandler):
        pass
    Handler.share_dir = share_dir
    return Handler


class ShareServer:
    def __init__(self, path, port):
        self.path = path
        self.port = port
        self.httpd = None
        self.thread = None
        self.running = False

    def start(self):
        if self.running:
            return
        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = socketserver.TCPServer(("0.0.0.0", self.port), make_handler(self.path))
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.running = True

    def _run(self):
        try:
            self.httpd.serve_forever()
        except:
            pass

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        self.running = False


def center_window(win, w, h):
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("局域网文件共享工具")
        self.root.resizable(True, True)
        center_window(self.root, 800, 520)
        self.root.configure(bg="#f0f4f8")

        self.servers = {}  # port -> ShareServer
        self.items = {}    # port -> tree item id
        self.next_port = 8000

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        # 顶部栏
        top = tk.Frame(self.root, bg="#1a3a5c", height=52)
        top.pack(fill=tk.X)
        top.pack_propagate(False)

        tk.Label(top, text="📁 局域网文件共享", bg="#1a3a5c", fg="#fff",
                 font=("Microsoft YaHei", 14, "bold")).pack(side=tk.LEFT, padx=16, pady=12)

        ip = get_local_ip()
        tk.Label(top, text=f"本机IP: {ip}", bg="#1a3a5c", fg="#aac4de",
                 font=("Microsoft YaHei", 10)).pack(side=tk.RIGHT, padx=16, pady=12)

        # 工具栏
        bar = tk.Frame(self.root, bg="#fff", height=42)
        bar.pack(fill=tk.X, padx=12, pady=(12, 0))
        bar.pack_propagate(False)

        tk.Button(bar, text="＋ 添加文件夹", command=self._add_folder,
                  bg="#1a3a5c", fg="#fff", font=("Microsoft YaHei", 10),
                  relief=tk.FLAT, padx=16, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=4, pady=6)

        tk.Button(bar, text="▶ 全部启动", command=self._start_all,
                  bg="#27ae60", fg="#fff", font=("Microsoft YaHei", 10),
                  relief=tk.FLAT, padx=12, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=4, pady=6)

        tk.Button(bar, text="⏹ 全部停止", command=self._stop_all,
                  bg="#e74c3c", fg="#fff", font=("Microsoft YaHei", 10),
                  relief=tk.FLAT, padx=12, pady=2, cursor="hand2").pack(side=tk.LEFT, padx=4, pady=6)

        # 列表
        list_frame = tk.Frame(self.root, bg="#fff")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        columns = ("path", "port", "url", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("path", text="共享文件夹")
        self.tree.heading("port", text="端口")
        self.tree.heading("url", text="访问地址")
        self.tree.heading("status", text="状态")

        self.tree.column("path", width=300, minwidth=200)
        self.tree.column("port", width=60, anchor=tk.CENTER)
        self.tree.column("url", width=280, minwidth=200)
        self.tree.column("status", width=80, anchor=tk.CENTER)

        # 滚动条
        vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 双击复制地址
        self.tree.bind("<Double-1>", self._on_double_click)

        # 底部操作栏
        btm = tk.Frame(self.root, bg="#f0f4f8", height=44)
        btm.pack(fill=tk.X, padx=12, pady=(0, 12))
        btm.pack_propagate(False)

        tk.Button(btm, text="启动选中", command=self._start_selected,
                  bg="#27ae60", fg="#fff", font=("Microsoft YaHei", 9),
                  relief=tk.FLAT, padx=10, cursor="hand2").pack(side=tk.LEFT, padx=2)

        tk.Button(btm, text="停止选中", command=self._stop_selected,
                  bg="#e67e22", fg="#fff", font=("Microsoft YaHei", 9),
                  relief=tk.FLAT, padx=10, cursor="hand2").pack(side=tk.LEFT, padx=2)

        tk.Button(btm, text="修改端口", command=self._change_port,
                  bg="#3498db", fg="#fff", font=("Microsoft YaHei", 9),
                  relief=tk.FLAT, padx=10, cursor="hand2").pack(side=tk.LEFT, padx=2)

        tk.Button(btm, text="删除选中", command=self._remove_selected,
                  bg="#e74c3c", fg="#fff", font=("Microsoft YaHei", 9),
                  relief=tk.FLAT, padx=10, cursor="hand2").pack(side=tk.LEFT, padx=2)

        tk.Button(btm, text="打开文件夹", command=self._open_folder,
                  bg="#7f8c8d", fg="#fff", font=("Microsoft YaHei", 9),
                  relief=tk.FLAT, padx=10, cursor="hand2").pack(side=tk.LEFT, padx=2)

    def _add_folder(self):
        folder = filedialog.askdirectory(title="选择要共享的文件夹")
        if not folder:
            return

        # 检查是否已添加
        for srv in self.servers.values():
            if os.path.abspath(srv.path) == os.path.abspath(folder):
                messagebox.showwarning("提示", "该文件夹已在列表中")
                return

        port = self.next_port
        self.next_port += 1

        srv = ShareServer(folder, port)
        self.servers[port] = srv

        ip = get_local_ip()
        item = self.tree.insert("", tk.END, values=(
            folder,
            str(port),
            f"http://{ip}:{port}",
            "⏸ 已停止"
        ))
        self.items[port] = item
        self._save_config()

    def _start_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        port = int(self.tree.item(item, "values")[1])
        srv = self.servers[port]
        srv.start()
        self._update_item(item, port)

    def _stop_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        port = int(self.tree.item(item, "values")[1])
        srv = self.servers[port]
        srv.stop()
        self._update_item(item, port)

    def _start_all(self):
        for port, srv in self.servers.items():
            if not srv.running:
                srv.start()
        self._refresh_all()

    def _stop_all(self):
        for port, srv in self.servers.items():
            if srv.running:
                srv.stop()
        self._refresh_all()

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        port = int(self.tree.item(item, "values")[1])
        srv = self.servers[port]
        if srv.running:
            srv.stop()
        self.tree.delete(item)
        del self.servers[port]
        del self.items[port]
        self._save_config()

    def _change_port(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        old_port = int(self.tree.item(item, "values")[1])
        srv = self.servers[old_port]
        if srv.running:
            messagebox.showwarning("提示", "请先停止该共享再修改端口")
            return

        from tkinter import simpledialog
        new_port = simpledialog.askinteger("修改端口", "新端口号:", initialvalue=old_port, minvalue=1024, maxvalue=65535)
        if new_port is None or new_port == old_port:
            return

        if new_port in self.servers:
            messagebox.showwarning("提示", "该端口已被占用")
            return

        srv.port = new_port
        self.servers[new_port] = self.servers.pop(old_port)
        self.items[new_port] = self.items.pop(old_port)
        self._update_item(item, new_port)
        self._save_config()

    def _open_folder(self):
        sel = self.tree.selection()
        if not sel:
            return
        path = self.tree.item(sel[0], "values")[0]
        os.startfile(path)

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        url = self.tree.item(sel[0], "values")[2]
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        # 临时提示
        self.tree.item(sel[0], values=(
            self.tree.item(sel[0], "values")[0],
            self.tree.item(sel[0], "values")[1],
            url,
            "✅ 已复制"
        ))
        self.root.after(1500, lambda: self._update_item(sel[0], int(self.tree.item(sel[0], "values")[1])))

    def _update_item(self, item, port):
        ip = get_local_ip()
        srv = self.servers[port]
        self.tree.item(item, values=(
            srv.path,
            str(srv.port),
            f"http://{ip}:{srv.port}",
            "▶ 运行中" if srv.running else "⏸ 已停止"
        ))

    def _refresh_all(self):
        for port, item in self.items.items():
            self._update_item(item, port)

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lan_share_config.json")
        if not os.path.exists(config_path):
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data:
                path = entry.get("path", "")
                port = entry.get("port", 0)
                if not os.path.isdir(path):
                    continue
                if port in self.servers:
                    continue
                srv = ShareServer(path, port)
                self.servers[port] = srv
                ip = get_local_ip()
                item = self.tree.insert("", tk.END, values=(
                    path, str(port), f"http://{ip}:{port}", "⏸ 已停止"
                ))
                self.items[port] = item
                if port >= self.next_port:
                    self.next_port = port + 1
        except:
            pass

    def _save_config(self):
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lan_share_config.json")
        data = []
        for port, srv in self.servers.items():
            data.append({"path": srv.path, "port": srv.port})
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def run(self):
        self.root.mainloop()

    def on_close(self):
        self._stop_all()
        self._save_config()
        self.root.destroy()


if __name__ == "__main__":
    app = App()
    app.root.protocol("WM_DELETE_WINDOW", app.on_close)
    app.run()
