# 遊戲自動化系統使用說明

本專案提供一個完整的遊戲自動化解決方案，包含視覺化腳本編輯器、模板管理系統，以及高 FPS 螢幕截圖與自動化控制功能。

## 目錄

1. [視覺化腳本系統](#視覺化腳本系統)
2. [模板管理與偵測標籤](#模板管理與偵測標籤)
3. [GUI 使用指南](#gui-使用指南)
4. [待實作功能清單](#待實作功能清單)

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
- `min_confidence`: 置信度閾值（當 `mode="label"` 時，預設：`0.0`，與 `find_image.confidence` 的差異見下方說明）
- `hsv_min`, `hsv_max`, `bgr_min`, `bgr_max`: 顏色範圍（當 `mode="color"` 時）
- `next_true`: 條件為真時的下一個節點 ID
- `next_false`: 條件為假時的下一個節點 ID

**執行邏輯：**
- 根據 `mode` 檢查條件
- 當 `mode="label"` 時，從 `vision_result["found_targets"]` 中尋找對應 `label` 的偵測結果，並檢查 `det["confidence"] >= min_confidence` 才視為條件成立
- 返回 `next_true` 或 `next_false` 作為下一個節點

**注意：** 條件節點的連線不會出現在 `connections` 字典中，而是儲存在節點的 `next_true` 和 `next_false` 參數中。

**`min_confidence` 與 `find_image.confidence` 的差異：**
- `find_image.confidence`：用於 `find_image` 節點，決定是否找到圖片（影響節點返回的布林值）
- `condition.min_confidence`：用於 `condition` 節點的 label 模式，決定條件是否成立（影響 `next_true` 或 `next_false` 的選擇）
- 兩者可以設定不同的值，例如：`find_image` 使用較低的置信度（0.7）來偵測圖片，而 `condition` 使用較高的置信度（0.9）來確保條件成立

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

**重要說明：**
- `find_image` 節點**不會進行點擊**，只負責偵測圖片並回傳是否找到（布林值）
- 此節點只影響流程控制或供後續 `condition` / `loop` 節點使用
- 若需要點擊，請在 `find_image` 後接上一個 `click` 節點

**使用範例：**

**範例 1：找到圖片才點擊**
```json
{
  "nodes": [
    {
      "id": "node_1",
      "type": "condition",
      "params": {
        "mode": "label",
        "label": "START_BUTTON",
        "next_true": "node_2",
        "next_false": "node_3"
      }
    },
    {
      "id": "node_2",
      "type": "click",
      "params": {
        "mode": "label",
        "label": "START_BUTTON",
        "button": "left"
      }
    },
    {
      "id": "node_3",
      "type": "sleep",
      "params": {
        "seconds": 1.0
      }
    }
  ],
  "connections": {
    "node_1": "node_2"
  }
}
```
此腳本會先使用 `condition` 節點檢測是否找到 "START_BUTTON"，如果找到（`next_true`），則執行 `click` 節點點擊；如果沒找到（`next_false`），則執行 `sleep` 節點等待。

**範例 2：看到 A 但同時看到 B 就不點**
```json
{
  "nodes": [
    {
      "id": "node_1",
      "type": "condition",
      "params": {
        "mode": "label",
        "label": "BUTTON_A",
        "next_true": "node_2",
        "next_false": "node_4"
      }
    },
    {
      "id": "node_2",
      "type": "condition",
      "params": {
        "mode": "label",
        "label": "BUTTON_B",
        "next_true": "node_4",
        "next_false": "node_3"
      }
    },
    {
      "id": "node_3",
      "type": "click",
      "params": {
        "mode": "label",
        "label": "BUTTON_A",
        "button": "left"
      }
    },
    {
      "id": "node_4",
      "type": "sleep",
      "params": {
        "seconds": 0.5
      }
    }
  ],
  "connections": {
    "node_1": "node_2",
    "node_2": "node_3"
  }
}
```
此腳本會先檢查是否看到 "BUTTON_A"，如果看到，再檢查是否同時看到 "BUTTON_B"。只有在看到 A 但沒看到 B 時才會點擊 A。

### 8. verify_image_color（驗證圖片顏色）

先找到圖片，再驗證圖片指定位置的顏色是否符合條件。這是一個二重驗證流程，用於確保找到的圖片確實是預期的目標。

**參數：**
- `template_name`: 模板標籤名稱（對應 `TARGET_DEFINITIONS` 中的標籤）
- `offset_x`: 相對於圖片中心的 X 像素偏移（預設：`0`）
- `offset_y`: 相對於圖片中心的 Y 像素偏移（預設：`0`）
- `hsv_min`, `hsv_max`: HSV 顏色範圍（可選）
- `bgr_min`, `bgr_max`: BGR 顏色範圍（可選）
- `radius`: 檢查半徑（像素，預設：`0.0`）

**執行邏輯：**
1. 在 `vision_result["found_targets"]` 中找到對應 `template_name` 的偵測結果
2. 取得其邊界框（bbox），計算中心點
3. 根據 `offset_x` 和 `offset_y` 計算實際檢查座標
4. 以檢查座標為中心，向四周擴展 `radius` 像素作為檢查區域（ROI 半徑）
5. 使用 `ImageProcessor.find_color` 檢查該區域的顏色是否落在指定範圍內
6. 返回是否驗證通過（布林值）

**顏色範圍優先順序：**
- 當同時提供 HSV 與 BGR 範圍時，系統會**優先使用 HSV 範圍**做判斷
- BGR 範圍僅在 HSV 未提供時使用

**使用範例：**

**範例：先找圖片再驗證顏色再點擊**
```json
{
  "nodes": [
    {
      "id": "node_1",
      "type": "find_image",
      "params": {
        "template_name": "BUTTON",
        "confidence": 0.8
      }
    },
    {
      "id": "node_2",
      "type": "verify_image_color",
      "params": {
        "template_name": "BUTTON",
        "offset_x": 10,
        "offset_y": 5,
        "bgr_min": [200, 200, 200],
        "bgr_max": [255, 255, 255],
        "radius": 2.0
      }
    },
    {
      "id": "node_3",
      "type": "condition",
      "params": {
        "mode": "label",
        "label": "BUTTON",
        "next_true": "node_4",
        "next_false": "node_5"
      }
    },
    {
      "id": "node_4",
      "type": "click",
      "params": {
        "mode": "label",
        "label": "BUTTON",
        "button": "left"
      }
    },
    {
      "id": "node_5",
      "type": "sleep",
      "params": {
        "seconds": 1.0
      }
    }
  ],
  "connections": {
    "node_1": "node_2",
    "node_2": "node_3"
  }
}
```
此腳本會先使用 `find_image` 找到 "BUTTON"，然後使用 `verify_image_color` 驗證按鈕中心偏移 (10, 5) 位置的顏色是否為白色範圍，最後使用 `condition` 判斷是否通過驗證，通過則點擊。

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

### 模板路徑格式
- `resources.json` 中的模板路徑預期為**相對於專案根目錄的路徑**（例如：`"temp_templates/inline_image_123.png"`）。
- 若模板位於專案外部，可使用絕對路徑（例如：`"/path/to/external/image.png"`）。
- GUI 會在載入時自動將相對路徑轉換為絕對路徑（使用 `game_automation.core.path_utils.to_absolute_path()` 統一路徑轉換工具），並在儲存時轉回相對路徑。
- 內部處理統一使用絕對路徑，以確保 `TemplateMatcher` 能正確讀取圖片（`cv2.imread` 需要絕對路徑）。
- **GUI 層級的路徑處理**：`ResourceSidebar._templates` 字典和 `templatesChanged` 信號發送的值都是絕對路徑。所有消費 `templatesChanged` 信號的代碼都應假設接收到的路徑是絕對路徑，無需再與專案根目錄進行路徑拼接。
- 外部工具或測試腳本如需讀取 `resources.json`，應使用 `game_automation.core.path_utils.to_absolute_path()` 或 `to_relative_path()` 作為標準路徑轉換工具。取得專案根目錄請使用 `game_automation.core.path_utils.get_base_dir()`。

## 偵測目標定義（TARGET_DEFINITIONS）
- 模組 `game_automation/core/targets.py` 內的 `TARGET_DEFINITIONS` 是偵測系統的統一來源。
- 啟動時會嘗試從 `resources.json` 讀取模板並合併到 `TARGET_DEFINITIONS`，對應的預設參數：
  - `method`: `tm`
  - `threshold`: `0.85`
  - `roi`: `[0.0, 0.0, 1.0, 1.0]`
- 若 `core.targets` 已存在同名定義，預設不覆寫；可使用覆寫模式（程式內部）控制行為。

### TARGET_DEFINITIONS 合約與持久化要求
**重要合約：** 所有非內建目標（`_BUILTIN_TARGETS`）都必須透過 `resources.json` 定義。

- **內建目標**：定義在 `game_automation/core/targets.py` 中的 `TARGET_DEFINITIONS` 初始值（例如：`DAILY_BOOK_BUTTON`、`QINGYUN_CARD` 等）會被標記為內建目標，永遠不會被修剪。
- **非內建目標**：所有其他目標都必須在 `resources.json` 中定義，否則會被自動移除。
- **自動修剪機制**：當 `ResourceSidebar.persist()` 被呼叫時，會以 `prune_missing=True` 重新載入目標定義。這會移除所有不在 `resources.json` 中且不是內建目標的項目，確保 `TARGET_DEFINITIONS` 與持久化的 `resources.json` 保持同步。
- **動態添加目標**：如果您需要在程式碼中動態添加目標，必須同時更新 `resources.json`（透過 `ResourceSidebar.persist()` 或直接修改檔案），否則這些目標會在下次 `persist()` 時被修剪。
- **建議做法**：所有模板管理操作都應透過 GUI 的 `ResourceSidebar` 進行，它會自動處理持久化和同步。

**開發者警告：** 如果您在程式碼中直接修改 `TARGET_DEFINITIONS` 字典（例如：`TARGET_DEFINITIONS["new_target"] = {...}`），這些修改**不會自動持久化**。當 GUI 執行任何模板操作（新增、重命名、刪除等）時，`ResourceSidebar.persist()` 會被呼叫，所有未在 `resources.json` 中定義的非內建目標都會被自動移除。因此，任何程式化的目標添加都必須同時更新 `resources.json`，否則這些目標將在下次 GUI 操作時丟失。

**外部動態擴充注意事項：** 如果您有外部腳本或工具需要動態添加目標，有兩種做法：
1. **推薦做法**：透過 GUI 的 `ResourceSidebar` API 進行操作，它會自動處理持久化。
2. **進階做法**：直接修改 `TARGET_DEFINITIONS` 的同時，也必須更新 `resources.json` 檔案（使用與 `ResourceSidebar.persist()` 相同的結構），否則這些目標會在下次 `reload_targets_from_resources(prune_missing=True)` 時被移除。如果您需要完全動態、非持久化的目標（例如：臨時測試目標），請避免在 GUI 中進行任何模板操作，或使用配置標誌來禁用修剪功能（需要修改程式碼）。

**重要：非持久化的程式化目標添加不受支援**：任何未透過 `resources.json` 持久化的程式化目標添加都是不受支援的，並會在下次 GUI 模板操作時被自動移除。如果您需要在程式碼中動態添加目標，必須同時更新 `resources.json`（透過 `ResourceSidebar.persist()` 或直接修改檔案）。當 `reload_targets_from_resources(prune_missing=True)` 被呼叫時，所有未持久化的非內建目標都會被記錄到控制台並被移除。

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

使用拖拽方式連接節點：

1. **從來源節點拖拽**：將滑鼠移動到來源節點右側的輸出區域（會顯示連接把手）
2. **按住滑鼠左鍵並拖拽**：從來源節點拖拽到目標節點
3. **釋放滑鼠**：在目標節點上釋放滑鼠按鈕以完成連接
4. **視覺反饋**：
   - 拖拽時會顯示虛線臨時連接線
   - 當滑鼠懸停在可連接的節點上時，節點邊框會高亮顯示
   - 無法連接時（如已有連接），會顯示紅色邊框提示

**特殊節點連線：**
- 對於條件節點（`condition`）：第一個連線會設定 `next_true`，第二個連線會設定 `next_false`
- 對於迴圈節點（`loop`）：第一個連線會設定 `next_body`，第二個連線會設定 `next_after`

**注意：** 條件和迴圈節點的連線會立即在畫面上顯示為邊線，與標準連線一致。連接模式切換按鈕已被移除，所有連接操作都使用拖拽方式完成。

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
- **停止執行**：停止正在執行的腳本
- **單步執行**：切換為單步模式，每次執行一個節點
- **繼續執行**：從單步模式切換回連續執行模式
- **暫停**：暫停/繼續腳本執行
- **驗證腳本**：檢查腳本是否有錯誤或問題
- **保存**：手動儲存所有腳本到 `visual_scripts.json`
- **載入**：從 `visual_scripts.json` 重新載入所有腳本
- **錄製模式（即將推出）**：功能開發中，按鈕已停用

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
4. **連線節點**：從來源節點右側拖拽到目標節點（詳見上方「連線節點」說明）
5. **執行腳本**：點擊「執行腳本」按鈕

腳本會從第一個節點開始執行，根據連線和條件分支依序執行各節點。

## 故障排除

### 前置條件檢查

開始執行腳本前，請確保：

1. **已啟動截圖**：
   - 已在主視窗上按「開始截圖」，或等待系統自動啟動截圖並顯示 FPS
   - 若忘記啟動，系統會嘗試自動啟動，但第一次可能要等 1–2 秒才有畫面

2. **模板圖片檔案存在**：
   - 所有模板圖片檔案（包含 `resources.json` 的 inline_image 檔案）都存在且可讀取
   - 若 `find_image` 或點擊完全沒反應，請開啟 `resources.json` 確認路徑與檔案是否存在
   - 確認模板路徑正確（相對路徑或絕對路徑）

### 常見問題

- **find_image 節點永遠失敗**：檢查模板是否已正確註冊到 `resources.json`，確認圖片檔案路徑正確
- **點擊節點無法點擊**：確認 `click` 節點的 `label` 參數已設定，且對應的模板已在畫面中被偵測到
- **腳本執行無反應**：確認已啟動截圖，且狀態列顯示 FPS 數值

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

- 條件和迴圈節點的連線儲存在節點參數中（`next_true`/`next_false` 或 `next_body`/`next_after`），而非 `connections` 字典
- 複製腳本時，所有節點 ID、連線和條件/迴圈節點的 `next_*` 參數會自動重新映射，確保複製的腳本可以獨立執行
- 模板圖片路徑可以是絕對路徑或相對路徑（相對於專案根目錄）
- 腳本執行在背景執行緒中進行，不會阻塞 GUI（已實作）

## 進階功能

### 變數監視器

在左側的「變數監視器」dock 面板中，可以即時查看：

- **畫面偵測結果**：顯示當前畫面中偵測到的所有目標及其信心度
- **迴圈計數器**：顯示所有活躍迴圈節點的執行次數
- **節點執行結果**：顯示最近執行的節點及其執行狀態（成功/失敗）

變數監視器會在腳本執行期間自動更新，方便除錯與監控腳本執行狀態。

### 執行模式控制

- **連續模式**：腳本會自動連續執行所有節點，直到完成或遇到錯誤
- **單步模式**：每次點擊「單步執行」按鈕只執行一個節點，適合逐步除錯
- **暫停功能**：可以隨時暫停腳本執行，檢查當前狀態後再繼續

### 效能報告

腳本執行完成後，會在「執行日誌」面板中自動顯示效能報告，包含：

- 總執行時間
- 各節點的執行次數、總時間、平均時間、最小/最大時間
- 按節點類型分組的執行時間摘要

效能報告有助於識別腳本中的效能瓶頸，優化腳本執行效率。

## 待實作功能清單

以下功能已規劃但尚未完全實作：

1. **錄製模式**：監聽全域滑鼠/鍵盤事件，自動轉換為 VisualNode 並插入當前腳本
2. **批次執行**：批次佇列 UI，依序執行多個腳本並顯示進度
3. **變數面板**：進階變數管理與監視功能（基本變數監視器已實作）

這些功能屬於進階 UX 增強，不影響核心功能使用。
