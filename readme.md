# 遊戲自動化系統使用說明

本專案提供一個完整的遊戲自動化解決方案，包含視覺化腳本編輯器、模板管理系統，以及高 FPS 螢幕截圖與自動化控制功能。

## 目錄

1. [視覺化腳本系統](#視覺化腳本系統)
2. [模板管理與偵測標籤](#模板管理與偵測標籤)
3. [GUI 使用指南](#gui-使用指南)

---

# 視覺化腳本系統

## VisualScript JSON 格式

視覺化腳本以 JSON 格式儲存在專案根目錄的 `visual_scripts.json` 檔案中。每個腳本包含以下結構：

```json
{
  "id": "script_name",
  "name": "腳本顯示名稱",
  "nodes": [
    {
      "id": "node_1",
      "type": "click",
      "params": {
        "mode": "label",
        "label": "START_BUTTON",
        "button": "left"
      },
      "position": [100.0, 200.0],
      "outputs": []
    }
  ],
  "connections": {
    "node_1": "node_2"
  }
}
```

### 欄位說明

- **id**: 腳本唯一識別碼（通常與腳本名稱相同）
- **name**: 腳本的顯示名稱
- **nodes**: 節點陣列，每個節點包含：
  - `id`: 節點唯一識別碼（格式：`node_1`, `node_2`, ...）
  - `type`: 節點類型（見下方節點類型說明）
  - `params`: 節點參數（依類型而異）
  - `position`: 節點在編輯器中的位置 `[x, y]`（像素座標）
  - `outputs`: 輸出列表（目前未使用）
- **connections**: 節點連線字典，格式為 `{來源節點ID: 目標節點ID}`

## 節點類型與參數

### 1. click（點擊）

執行滑鼠點擊操作。

**參數：**
- `mode`: `"label"` 或 `"bbox"`（目前主要使用 `"label"`）
- `label`: 模板標籤名稱（對應 `TARGET_DEFINITIONS` 中的標籤）
- `button`: `"left"` 或 `"right"`（預設：`"left"`）
- `duration`: 滑鼠移動時間（秒，預設：`0`）

**執行邏輯：**
- 從 `vision_result["found_targets"]` 中尋找對應 `label` 的偵測結果
- 計算邊界框中心點並點擊

### 2. key（按鍵）

模擬鍵盤按鍵。

**參數：**
- `key`: 按鍵名稱（例如：`"space"`, `"enter"`, `"a"`）

### 3. sleep（等待）

暫停執行指定時間。

**參數：**
- `seconds`: 等待秒數（浮點數）

### 4. find_color（找顏色）

在畫面中尋找指定顏色區域。

**參數：**
- `hsv_min`: HSV 顏色範圍下限 `[h, s, v]`（可選）
- `hsv_max`: HSV 顏色範圍上限 `[h, s, v]`（可選）
- `bgr_min`: BGR 顏色範圍下限 `[b, g, r]`（可選）
- `bgr_max`: BGR 顏色範圍上限 `[b, g, r]`（可選）

**執行邏輯：**
- 使用 `ImageProcessor.find_color()` 在當前畫面中尋找顏色
- 返回是否找到（布林值）

### 5. condition（條件判斷）

根據條件結果分支到不同節點。

**參數：**
- `mode`: `"label"` 或 `"color"`
- `label`: 模板標籤名稱（當 `mode="label"` 時）
- `hsv_min`, `hsv_max`, `bgr_min`, `bgr_max`: 顏色範圍（當 `mode="color"` 時）
- `next_true`: 條件為真時的下一個節點 ID
- `next_false`: 條件為假時的下一個節點 ID

**執行邏輯：**
- 根據 `mode` 檢查條件
- 返回 `next_true` 或 `next_false` 作為下一個節點

**注意：** 條件節點的連線不會出現在 `connections` 字典中，而是儲存在節點的 `next_true` 和 `next_false` 參數中。

### 6. loop（迴圈）

重複執行迴圈體指定次數。

**參數：**
- `count`: 迴圈執行次數（整數）
- `next_body`: 迴圈體的起始節點 ID
- `next_after`: 迴圈結束後的下一個節點 ID

**執行邏輯：**
- 維護每個迴圈節點的計數器
- 當計數 < `count` 時，前往 `next_body`
- 當計數 >= `count` 時，前往 `next_after`

**注意：** 迴圈節點的連線不會出現在 `connections` 字典中，而是儲存在節點的 `next_body` 和 `next_after` 參數中。

### 7. find_image（找圖片）

在畫面中尋找模板圖片。

**參數：**
- `template_name`: 模板標籤名稱（對應 `TARGET_DEFINITIONS` 中的標籤）
- `confidence`: 置信度閾值（預設：`0.8`）

**執行邏輯：**
- 從 `vision_result["found_targets"]` 中尋找對應 `template_name` 的偵測結果
- 檢查置信度是否 >= `confidence`
- 返回是否找到（布林值）

## vision_result 結構

所有節點執行時都會接收 `vision_result` 字典，包含：

- `frame`: 當前畫面（BGR 格式的 numpy 陣列）
- `found_targets`: 偵測到的目標列表，每個目標包含：
  - `label`: 標籤名稱
  - `bbox`: 邊界框 `(x1, y1, x2, y2)`
  - `confidence`: 置信度（0.0-1.0）

---

# 模板管理與偵測標籤

## 模板來源與儲存
- GUI 建立或編輯的模板清單會寫入專案根目錄的 `resources.json`。
- 檔案結構為：
  - `{"templates": {"範本名稱": "圖片檔路徑", ...}}`
- 這是「metadata」清單，描述名稱與檔案路徑。

## 偵測目標定義（TARGET_DEFINITIONS）
- 模組 `game_automation/core/targets.py` 內的 `TARGET_DEFINITIONS` 是偵測系統的統一來源。
- 啟動時會嘗試從 `resources.json` 讀取模板並合併到 `TARGET_DEFINITIONS`，對應的預設參數：
  - `method`: `tm`
  - `threshold`: `0.85`
  - `roi`: `[0.0, 0.0, 1.0, 1.0]`
- 若 `core.targets` 已存在同名定義，預設不覆寫；可使用覆寫模式（程式內部）控制行為。

## 動態重載與即時生效
- 當 GUI 透過 `ResourceSidebar` 新增、重命名、複製或刪除模板時，會自動呼叫 `persist()` 進行存檔。
- `persist()` 會觸發 `core.targets.reload_targets_from_resources()`，將新模板合併到 `TARGET_DEFINITIONS`。
- `core.targets` 維護 `TARGETS_VERSION` 版本號，每次合併變更後提升版本。
- `TemplateMatcher` 於每次匹配前檢查版本，若偵測到 `TARGETS_VERSION` 變更，會自動重新載入模板快取，確保新增的 GUI 範本立即生效（圖片檔有效即可）。
- `TemplateMatcher._load_templates()` 統一從 `TARGET_DEFINITIONS` 讀取模板定義，因此 GUI 管理的模板名稱會自動成為可用的偵測標籤。

## GUI 管理的模板與偵測標籤的對應關係
- GUI 在 `ResourceSidebar` 中管理的模板名稱會自動對應到偵測系統的標籤（label）。
- 當您在 GUI 中新增一個模板並指定圖片路徑後，該模板名稱會自動成為可在腳本中使用的偵測標籤。
- 例如：在 GUI 中新增名為 "START_BUTTON" 的模板後，即可在視覺腳本編輯器的「找圖片」節點中使用 "START_BUTTON" 作為 `template_name` 參數。

## 是否仍需手動編輯 `core.targets`
- 一般情境下不需要；GUI 管理的模板即可成為偵測標籤並使用預設參數。
- 若需要自訂每個範本的 `threshold` 或 `roi`，可手動在 `core.targets` 中為指定標籤寫入更精細的設定（不覆寫模式下，現有定義優先）。
- 手動編輯 `core.targets` 僅在需要調整偵測參數時才需要，新增模板本身不需要手動編輯。

## 既有行為與相容性
- 現有於 `core.targets` 定義的標籤維持原樣與優先權，`resources.json` 新增的名稱會補充其餘標籤。
- 除非以覆寫模式載入，`resources.json` 不會改動已存在的 `TARGET_DEFINITIONS` 項目。

## 故障排除
- 新增模板未生效：
  - 確認 `resources.json` 已包含對應名稱與正確圖片路徑。
  - 確認路徑的圖片存在且可讀。
  - 確認 GUI 已執行存檔（`ResourceSidebar.persist()`），並出現合併（版本提升）。
- 匹配不到：
  - 調整或在 `core.targets` 為該標籤設定較合適的 `threshold` / `roi`。

---

# GUI 使用指南

## 主視窗布局

主視窗分為三個主要區域：

1. **左側邊欄（ResourceSidebar）**：管理腳本列表和模板列表
2. **中央編輯區（VisualScriptEditor）**：視覺化腳本編輯器
3. **右側屬性面板（PropertiesPanel）**：編輯選中節點的參數

## 腳本管理

### 腳本列表

- **新增腳本**：點擊「新增腳本」按鈕，輸入腳本名稱
- **重命名腳本**：選中腳本後點擊「重命名」
- **複製腳本**：選中腳本後點擊「複製」，會建立一個副本（包含所有節點和連線，節點 ID 會自動重新映射）
- **刪除腳本**：選中腳本後點擊「刪除」

所有腳本自動儲存到 `visual_scripts.json`。

### 腳本載入與切換

- 在左側腳本列表中點擊腳本名稱即可載入該腳本到編輯器
- 切換腳本時，當前編輯的腳本會自動儲存

## 視覺化腳本編輯器

### 基本操作

- **新增節點**：點擊工具列上的節點類型按鈕（🐭 點擊、⌨️ 按鍵等）
- **移動節點**：拖曳節點到新位置
- **選中節點**：點擊節點，選中後會在右側屬性面板顯示參數
- **刪除節點**：右鍵點擊節點，選擇「刪除節點」
- **移除連線**：右鍵點擊節點，選擇「移除連線」

### 連線節點

1. 點擊工具列上的「🔗 連接模式」按鈕啟用連接模式
2. 點擊來源節點右側的連接點（小圓圈）
3. 點擊目標節點的連接點
4. 對於條件/迴圈節點，第一個連線會設定 `next_true`/`next_body`，第二個連線會設定 `next_false`/`next_after`

**注意：** 條件和迴圈節點的連線會立即在畫面上顯示為邊線，與標準連線一致。

### 縮放與平移

- **縮放**：使用滑鼠滾輪（範圍：0.25x 至 3.0x）
- **平移**：按住中鍵（或 Ctrl+右鍵）拖曳

### 編輯節點參數

1. 選中節點（點擊節點）
2. 在右側屬性面板中編輯參數
3. 參數變更會自動儲存

## 工具列按鈕

- **開始截圖**：啟動背景截圖執行緒，開始捕獲螢幕畫面
- **執行腳本**：執行當前載入的腳本
- **錄製模式（即將推出）**：功能開發中，按鈕已停用
- **單步執行（即將推出）**：功能開發中，按鈕已停用
- **暫停（即將推出）**：功能開發中，按鈕已停用
- **保存**：手動儲存所有腳本到 `visual_scripts.json`
- **載入**：從 `visual_scripts.json` 重新載入所有腳本

## 模板管理

在左側邊欄的模板列表中：

- **新增範本**：點擊「新增範本」，輸入名稱並選擇圖片檔案
- **重命名範本**：選中範本後點擊「重命名」
- **複製範本**：選中範本後點擊「複製」
- **刪除範本**：選中範本後點擊「刪除」

新增的模板會自動成為可用的偵測標籤，可在「找圖片」節點中使用。

## 執行流程

1. **啟動截圖**：點擊「開始截圖」按鈕
2. **建立腳本**：在左側新增腳本，或在編輯器中新增節點
3. **設定參數**：選中節點，在屬性面板中設定參數（例如：點擊節點的 `label` 參數）
4. **連線節點**：使用連接模式將節點依序連接
5. **執行腳本**：點擊「執行腳本」按鈕

腳本會從第一個節點開始執行，根據連線和條件分支依序執行各節點。

## 範例腳本

以下是一個簡單的範例腳本 JSON：

```json
{
  "id": "example_script",
  "name": "範例腳本",
  "nodes": [
    {
      "id": "node_1",
      "type": "find_image",
      "params": {
        "template_name": "START_BUTTON",
        "confidence": 0.85
      },
      "position": [100.0, 100.0],
      "outputs": []
    },
    {
      "id": "node_2",
      "type": "click",
      "params": {
        "mode": "label",
        "label": "START_BUTTON",
        "button": "left"
      },
      "position": [300.0, 100.0],
      "outputs": []
    },
    {
      "id": "node_3",
      "type": "sleep",
      "params": {
        "seconds": 2.0
      },
      "position": [500.0, 100.0],
      "outputs": []
    }
  ],
  "connections": {
    "node_1": "node_2",
    "node_2": "node_3"
  }
}
```

這個腳本會：
1. 尋找 "START_BUTTON" 模板
2. 如果找到，點擊該按鈕
3. 等待 2 秒

## 注意事項

- 腳本執行時會阻塞 GUI 執行緒，長時間執行的腳本可能會讓介面暫時無回應
- 條件和迴圈節點的連線儲存在節點參數中（`next_true`/`next_false` 或 `next_body`/`next_after`），而非 `connections` 字典
- 複製腳本時，所有節點 ID、連線和條件/迴圈節點的 `next_*` 參數會自動重新映射，確保複製的腳本可以獨立執行
- 模板圖片路徑可以是絕對路徑或相對路徑（相對於專案根目錄）
