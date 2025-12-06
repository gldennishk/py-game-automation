# Game Automation Studio（明亮主題版）

本專案以 PySide6 建構現代化 GUI，結合 mss 高 FPS 截圖、OpenCV 模板匹配與 pyautogui 控制，支援 Windows 11 與 125% 縮放相容；所有 UI 採用淺色（Light Mode）配色，適合明亮環境使用。

## 功能
- 高 FPS（≥60）螢幕截圖，端到端延遲優化
- 模板匹配（Template Matching）＋可插拔 OCR
- 腳本序列編輯器（可存 JSON 與 Markdown）
- 明亮主題 GUI：白底、深色文字、淺色按鈕與邊框
- ROI/threshold 調參工具，截圖保存

## 結構
- `game_automation/main.py`：GUI 入口
- `game_automation/core/`：截圖、視覺、模板匹配、縮放、動作控制、性能監控
- `game_automation/ui/`：主視窗、腳本編輯器、明亮主題 QSS
- `game_automation/tools/`：`debug_match_viewer.py` 調參工具
- `game_automation/tests/`：單元與整合測試

## 安裝與執行
```bash
python -m pip install -r game_automation/requirements.txt
python game_automation/main.py
```

## 調參工具
```bash
python game_automation/tools/debug_match_viewer.py
```
- 請將模板 PNG 放置於 `game_automation/templates/`，並在 `core/targets.py` 設定 `roi` 與 `threshold`。

## 測試
```bash
cd game_automation
python -m pytest -q
```

## 推送到 GitHub
1. 建立 Git 倉庫（已在本地初始化）
2. 在 GitHub 建立遠端倉庫（建議名稱：`game-automation-studio`）
3. 設定遠端並推送：
```bash
git remote add origin https://github.com/<你的帳號>/<你的倉庫名>.git
git branch -M main
git push -u origin main
```

若安裝了 GitHub CLI 且已登入，可用無互動方式建立並推送：
```bash
gh repo create <你的倉庫名> --private --source . --remote origin --push
```
> 注意：CLI 未登入或需互動時請改用手動建立遠端，並使用上述 `git remote add` 指令。

## 授權
MIT License

