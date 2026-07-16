"""
demo_programming.py — AgiCode 现场编程演示
功能：一个带 GUI 的简易文件搜索工具
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path
import threading


class FileSearcher:
    """文件搜索器：按关键词搜索文件内容"""

    def __init__(self, root_path="."):
        self.root = Path(root_path)
        self.results = []

    def search(self, keyword, extensions=None):
        """搜索包含关键词的文件"""
        self.results = []
        ext_list = extensions.split(",") if extensions else []
        ext_list = [e.strip().lower() for e in ext_list if e.strip()]

        for file_path in self.root.rglob("*"):
            if file_path.is_file():
                # 扩展名过滤
                if ext_list:
                    if file_path.suffix.lower() not in ext_list:
                        continue
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_no, line in enumerate(f, 1):
                            if keyword.lower() in line.lower():
                                self.results.append((file_path, line_no, line.strip()))
                except Exception:
                    pass
        return self.results


class SearchApp:
    """搜索工具 GUI"""

    def __init__(self, root):
        self.root = root
        root.title("AgiCode 文件搜索工具")
        root.geometry("800x600")

        # 搜索框架
        frame = ttk.Frame(root, padding=10)
        frame.pack(fill=tk.X)

        ttk.Label(frame, text="搜索关键词:").grid(row=0, column=0, sticky=tk.W)
        self.keyword_entry = ttk.Entry(frame, width=30)
        self.keyword_entry.grid(row=0, column=1, padx=5)
        self.keyword_entry.bind("<Return>", lambda e: self.do_search())

        ttk.Label(frame, text="文件类型(逗号分隔):").grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.ext_entry = ttk.Entry(frame, width=20)
        self.ext_entry.insert(0, ".py,.txt,.md,.json")
        self.ext_entry.grid(row=0, column=3, padx=5)

        self.search_btn = ttk.Button(frame, text="搜索", command=self.do_search)
        self.search_btn.grid(row=0, column=4, padx=10)

        self.status_label = ttk.Label(frame, text="就绪")
        self.status_label.grid(row=0, column=5, padx=10)

        # 结果显示
        self.result_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Consolas", 10))
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # 状态栏
        self.count_label = ttk.Label(root, text="共 0 个结果", relief=tk.SUNKEN, anchor=tk.W)
        self.count_label.pack(fill=tk.X, padx=10, pady=(0, 5))

    def do_search(self):
        keyword = self.keyword_entry.get().strip()
        if not keyword:
            self.status_label.config(text="请输入关键词")
            return

        self.search_btn.config(state=tk.DISABLED)
        self.status_label.config(text="搜索中...")
        self.result_text.delete(1.0, tk.END)
        self.count_label.config(text="搜索中...")

        # 后台线程搜索
        thread = threading.Thread(target=self._search_thread, args=(keyword,))
        thread.daemon = True
        thread.start()

    def _search_thread(self, keyword):
        searcher = FileSearcher("D:/AgiCode")
        extensions = self.ext_entry.get().strip()
        results = searcher.search(keyword, extensions)

        self.root.after(0, self._show_results, results, keyword)

    def _show_results(self, results, keyword):
        self.result_text.delete(1.0, tk.END)
        if not results:
            self.result_text.insert(tk.END, f"未找到包含 '{keyword}' 的文件\n")
        else:
            for file_path, line_no, line in results[:200]:
                rel_path = os.path.relpath(file_path, "D:/AgiCode")
                self.result_text.insert(tk.END, f"{rel_path}:{line_no}\n")
                self.result_text.insert(tk.END, f"  {line}\n\n")

            if len(results) > 200:
                self.result_text.insert(tk.END, f"... 还有 {len(results) - 200} 个结果未显示\n")

        self.count_label.config(text=f"共 {len(results)} 个结果")
        self.status_label.config(text="完成")
        self.search_btn.config(state=tk.NORMAL)


if __name__ == "__main__":
    root = tk.Tk()
    app = SearchApp(root)
    root.mainloop()
