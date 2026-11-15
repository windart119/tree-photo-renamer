#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Browser-based tree photo renaming tool."""

from __future__ import annotations

import io
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, render_template, request, send_file

from renamer import IMAGE_EXTS, rename_photos

APP_TITLE = "樹木相片重新命名工具"
UPLOAD_ROOT = Path(tempfile.gettempdir()) / "tree-photo-renamer"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB


def _safe_name(name: str) -> str:
    name = Path(name).name
    if not name or name in {".", ".."}:
        return "photo"
    return name


def _collect_uploads(tmp: Path) -> list[str]:
    """Save uploaded images or zip contents. Return names in upload order."""
    order: list[str] = []
    files = request.files.getlist("photos")
    for item in files:
        if not item or not item.filename:
            continue
        filename = _safe_name(item.filename)
        suffix = Path(filename).suffix.lower()
        if suffix == ".zip":
            data = io.BytesIO(item.read())
            with zipfile.ZipFile(data) as zf:
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
        item.save(target)
        order.append(target.name)
    return order


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


@app.get("/")
def index():
    return render_template("index.html", title=APP_TITLE)


@app.post("/api/process")
def process():
    tmp = UPLOAD_ROOT / str(uuid4())
    tmp.mkdir(parents=True, exist_ok=True)
    logs: list[str] = []
    try:
        order = _collect_uploads(tmp)
        if not order:
            return jsonify({"ok": False, "error": "請先選擇照片，或上傳含照片的 zip。", "log": logs}), 400

        logs.append(f"已接收 {len(order)} 張照片。")
        result = rename_photos(tmp, log=logs.append, order=order)

        zip_name = "重新命名照片.zip"
        zip_path = tmp / zip_name
        image_files = [
            p for p in tmp.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS
        ]
        if not image_files:
            return jsonify({"ok": False, "error": "處理後沒有可下載的照片。", "log": logs, "result": result}), 400

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(image_files, key=lambda x: x.name.lower()):
                zf.write(p, p.name)

        token = tmp.name
        return jsonify(
            {
                "ok": True,
                "log": logs,
                "result": {
                    "renamed": result["renamed"],
                    "skipped": result["skipped"],
                    "errors": result["errors"],
                    "mapping": [{"from": a, "to": b} for a, b in result["mapping"]],
                },
                "download": f"/download/{token}",
            }
        )
    except Exception as e:
        logs.append(f"錯誤：{e}")
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify({"ok": False, "error": str(e), "log": logs}), 500


@app.get("/download/<token>")
def download(token: str):
    if not token or any(ch in token for ch in "\\/."):
        return "無效的下載連結", 400
    folder = UPLOAD_ROOT / token
    zip_path = folder / "重新命名照片.zip"
    if not zip_path.is_file():
        return "找不到檔案，請重新處理一次。", 404
    return send_file(
        zip_path,
        as_attachment=True,
        download_name="重新命名照片.zip",
        mimetype="application/zip",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"請在瀏覽器開啟 http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
