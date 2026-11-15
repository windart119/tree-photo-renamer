#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Browser-based tree photo renaming tool (Gradio, for local use and Hugging Face Spaces)."""

from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from pathlib import Path

import gradio as gr

from renamer import IMAGE_EXTS, rename_photos

try:
    import spaces
except ImportError:  # local run without the Spaces helper
    class spaces:  # type: ignore
        @staticmethod
        def GPU(*args, **kwargs):
            def decorator(fn):
                return fn

            if args and callable(args[0]) and not kwargs:
                return args[0]
            return decorator


APP_TITLE = "樹木相片重新命名工具"


def _safe_name(name: str) -> str:
    name = Path(name).name
    if not name or name in {".", ".."}:
        return "photo"
    return name


def _unique_path(folder: Path, filename: str) -> Path:
    dest = folder / filename
    if not dest.exists():
        return dest
    stem, suffix = Path(filename).stem, Path(filename).suffix
    i = 1
    while dest.exists():
        dest = folder / f"{stem}_{i}{suffix}"
        i += 1
    return dest


def _as_path(item) -> Path | None:
    if item is None:
        return None
    if isinstance(item, (list, tuple)):
        return _as_path(item[0]) if item else None
    if hasattr(item, "name") and item.name:
        return Path(str(item.name))
    return Path(str(item))


def _collect_uploads(files, tmp: Path) -> list[str]:
    order: list[str] = []
    if not files:
        return order
    if not isinstance(files, list):
        files = [files]
    for item in files:
        path = _as_path(item)
        if path is None or not path.exists() or not path.is_file():
            continue
        filename = _safe_name(path.name)
        suffix = path.suffix.lower()
        if suffix == ".zip":
            with zipfile.ZipFile(path) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    inner = _safe_name(info.filename)
                    if Path(inner).suffix.lower() not in IMAGE_EXTS:
                        continue
                    target = _unique_path(tmp, inner)
                    with zf.open(info) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    order.append(target.name)
            continue
        if suffix not in IMAGE_EXTS:
            continue
        target = _unique_path(tmp, filename)
        shutil.copy2(path, target)
        order.append(target.name)
    return order


@spaces.GPU(duration=180)
def process_photos(files):
    if not files:
        return "請先選擇照片，或上傳含照片的 zip。", None

    tmp = Path(tempfile.mkdtemp(prefix="tree-photo-"))
    logs: list[str] = []
    zip_out = None
    try:
        order = _collect_uploads(files, tmp)
        if not order:
            return "請先選擇照片，或上傳含照片的 zip。", None
        logs.append(f"已接收 {len(order)} 張照片。")
        result = rename_photos(tmp, log=logs.append, order=order)

        image_files = [
            p for p in tmp.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS
        ]
        if not image_files:
            logs.append("處理後沒有可下載的照片。")
            return "\n".join(logs), None

        zip_out = str(Path(tempfile.gettempdir()) / "重新命名照片.zip")
        with zipfile.ZipFile(zip_out, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(image_files, key=lambda x: x.name.lower()):
                zf.write(p, p.name)
        logs.append(f"完成，已重新命名 {result['renamed']} 張照片。可下載 zip。")
        return "\n".join(logs), zip_out
    except Exception as e:
        logs.append(f"錯誤：{e}")
        return "\n".join(logs), None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


with gr.Blocks(title=APP_TITLE, theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        f"""
# {APP_TITLE}

上傳樹木照片，程式會辨識 `TG-Txxxx` 編號牌，並依序重新命名。原檔不會被改動，完成後可下載 zip。

- 編號牌：`TG-Txxxx_Tag`
- 之後第 1 張：`TG-Txxxx_Whole view`
- 之後第 2 張：`TG-Txxxx_Crown`
- 再之後：`TG-Txxxx_ (1)`、`TG-Txxxx_ (2)`……

請依拍攝順序選擇檔案：先選編號牌，再選整體、樹冠及其他細節。也可上傳含照片的 zip。
照片只用於這次處理，不會寫入程式碼儲存庫。
        """
    )
    files = gr.File(
        label="上傳照片或 zip",
        file_count="multiple",
        file_types=["image", ".zip"],
    )
    btn = gr.Button("開始處理", variant="primary")
    log = gr.Textbox(label="處理紀錄", lines=16)
    download = gr.File(label="下載重新命名後的照片")
    btn.click(process_photos, inputs=files, outputs=[log, download])


if __name__ == "__main__":
    demo.launch()
