#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Core renaming logic for tree photos tagged with TG-Txxxx plates."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

NUMBER_PATTERN = re.compile(r"TG-T\d{3,4}", re.IGNORECASE)
WHOLE_VIEW = "Whole view"
CROWN = "Crown"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
MODEL_FILES = ("craft_mlt_25k.pth", "english_g2.pth")

_cached_reader = None


def _exif_datetime(path: Path) -> datetime | None:
    try:
        from PIL import Image

        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None
            # 36867 DateTimeOriginal, 306 DateTime, 36868 DateTimeDigitized
            for tag in (36867, 306, 36868):
                raw = exif.get(tag)
                if not raw:
                    continue
                text = str(raw).strip()
                for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(text, fmt)
                    except ValueError:
                        continue
    except Exception:
        return None
    return None


def get_image_files(folder: Path, order: list[str] | None = None) -> list[Path]:
    folder = Path(folder)
    files: list[Path] = []
    seen: set[str] = set()
    try:
        entries = list(folder.iterdir())
    except FileNotFoundError:
        return []
    for p in entries:
        if not p.is_file():
            continue
        if p.suffix.lower() not in IMAGE_EXTS:
            continue
        key = p.name.lower()
        if key in seen:
            continue
        seen.add(key)
        files.append(p)

    if order:
        rank = {name.lower(): i for i, name in enumerate(order)}
        files.sort(key=lambda p: (rank.get(p.name.lower(), 10_000), p.name.lower()))
        return files

    def sort_key(p: Path):
        exif_dt = _exif_datetime(p)
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0
        return (exif_dt or datetime.fromtimestamp(mtime), p.name.lower())

    files.sort(key=sort_key)
    return files


def extract_tree_number(image_path: Path, reader) -> str | None:
    try:
        result = reader.readtext(str(image_path), detail=0)
        text = " ".join(result)
        match = NUMBER_PATTERN.search(text)
        if match:
            return match.group(0).upper()
    except Exception as e:
        return f"__OCR_ERROR__:{e}"
    return None


def get_model_dir() -> Path:
    model_dir = Path(__file__).resolve().parent / "models"
    model_dir.mkdir(exist_ok=True)
    return model_dir


def init_reader(log=print, gpu=None):
    global _cached_reader
    if gpu is None:
        try:
            import torch

            gpu = bool(torch.cuda.is_available())
        except Exception:
            gpu = False
    if _cached_reader is not None:
        log("辨識引擎已就緒。")
        return _cached_reader

    import easyocr

    model_dir = get_model_dir()
    local_models = all((model_dir / name).is_file() for name in MODEL_FILES)
    log(f"使用模型資料夾：{model_dir}")
    if not local_models:
        log("本地尚未有模型檔，首次會自動下載，可能需要幾分鐘。")
    log("正在初始化 OCR，請稍候……")
    _cached_reader = easyocr.Reader(
        ["en"],
        gpu=gpu,
        model_storage_directory=str(model_dir),
        download_enabled=not local_models,
    )
    log("辨識引擎已載入。")
    return _cached_reader


def rename_photos(folder, log=print, order: list[str] | None = None) -> dict:
    folder = Path(folder)
    result = {"renamed": 0, "skipped": 0, "errors": [], "mapping": []}
    if not folder.exists() or not folder.is_dir():
        log(f"找不到資料夾：{folder}")
        result["errors"].append(f"找不到資料夾：{folder}")
        return result

    reader = init_reader(log=log)
    images = get_image_files(folder, order=order)
    if not images:
        log("找不到照片。請確認上傳的是 JPG、PNG 等圖片。")
        result["errors"].append("找不到照片。")
        return result

    log(f"找到 {len(images)} 張照片。")
    current_number = None
    photo_index = 0

    for img in images:
        number = extract_tree_number(img, reader)
        if isinstance(number, str) and number.startswith("__OCR_ERROR__:"):
            err = number.split(":", 1)[1]
            log(f"OCR 讀取 {img.name} 時發生錯誤：{err}")
            number = None

        if number:
            current_number = number
            photo_index = 0
            log(f"在 {img.name} 找到編號：{number}")
            new_name = f"{number}_Tag{img.suffix}"
            new_path = img.parent / new_name
            if new_path.exists() and new_path.resolve() != img.resolve():
                log(f"  目標檔名已存在，略過：{new_name}")
                result["skipped"] += 1
            elif new_path.resolve() == img.resolve():
                log(f"  已是正確檔名：{new_name}")
                result["mapping"].append((img.name, new_name))
            else:
                img.rename(new_path)
                log(f"  {img.name} → {new_name}")
                result["renamed"] += 1
                result["mapping"].append((img.name, new_name))
            continue

        if current_number is None:
            msg = f"尚未找到編號牌，略過 {img.name}"
            log(msg)
            result["errors"].append(msg)
            result["skipped"] += 1
            continue

        if photo_index == 0:
            suffix_name = WHOLE_VIEW
        elif photo_index == 1:
            suffix_name = CROWN
        else:
            suffix_name = f" ({photo_index - 1})"

        new_name = f"{current_number}_{suffix_name}{img.suffix}"
        new_path = img.parent / new_name
        counter = 1
        while new_path.exists():
            new_name = f"{current_number}_{suffix_name}_{counter}{img.suffix}"
            new_path = img.parent / new_name
            counter += 1
        try:
            old_name = img.name
            img.rename(new_path)
            log(f"  {old_name} → {new_name}")
            result["renamed"] += 1
            result["mapping"].append((old_name, new_name))
            photo_index += 1
        except Exception as e:
            msg = f"無法重新命名 {img.name}：{e}"
            log(msg)
            result["errors"].append(msg)

    log("完成。" + f"已重新命名 {result['renamed']} 張照片。")
    return result
