# 樹木相片重新命名工具

用瀏覽器開啟的網上程式，依照片中的 `TG-Txxxx` 編號牌，自動把後續照片重新命名。

- 偵測到編號牌的照片：`TG-Txxxx_Tag`
- 之後第 1 張：`TG-Txxxx_Whole view`
- 之後第 2 張：`TG-Txxxx_Crown`
- 再之後：`TG-Txxxx_ (1)`、`TG-Txxxx_ (2)`……

請依拍攝順序上傳：先拍編號牌，再拍該棵樹的整體、樹冠及其他細節。程式會優先用照片的拍攝時間排序。

網上版會在伺服器上處理副本，不會改動你電腦裡的原檔。處理完成後可下載重新命名後的 zip。

## 本機使用

需要已安裝 [Python 3.10 或以上](https://www.python.org/downloads/)。

```bash
git clone https://github.com/windart119/tree-photo-renamer.git
cd tree-photo-renamer
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

然後用瀏覽器開啟 http://127.0.0.1:5000

首次啟動會下載辨識模型，可能需要幾分鐘。之後會快很多。

## 授權

僅供個人與工作使用。
