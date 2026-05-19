# 联合分析 & 跨材料对比 — 设计文档

**日期**：2026-05-19
**状态**：已批准，待实现

---

## 背景与目标

### 功能 1：联合分析（Joint Analysis）

用户同时上传同一材料的 FTIR、DSC、TGA 报告时，希望 AI 将三种谱图作为整体一次性分析，而不是每个文件独立处理。AI 应识别每张图的测试类型，并在报告中交叉关联三种技术的结果（IR 峰位 ↔ DSC 热转变 ↔ TGA 分解行为）。

### 功能 2：跨材料对比（Cross-Material Comparison）

用户持有一张未知材料的谱图，希望与知识库中已知的多种参考材料（同一测试类型）进行对比，AI 逐一比较差异并给出最匹配的材料鉴定结论。结果以流式文字 + 多曲线叠加可视化呈现。

---

## 功能 1：联合分析

### 用户交互流程

1. 用户在 `FailureAnalysis.vue` 上传多个文件（FTIR + DSC + TGA）
2. 勾选「联合分析模式」开关
3. 点击发送 → 前端强制走 `/api/v1/chat/stream`，`analysis_type=joint`
4. AI 流式返回综合报告，自然交叉引用三种谱图
5. 流结束后追加 `spectra_data` 事件（复用现有机制，仅含 FTIR 峰位）

### 前端改动：`FailureAnalysis.vue`

在文件列表下方、发送按钮上方新增开关：

```html
<el-switch v-model="jointMode" active-text="联合分析模式（所有文件属于同一材料）" />
```

发送逻辑修改：

```javascript
// 原逻辑：files.length > 1 → /compare
// 新逻辑：jointMode=true 时，无论文件数量，强制走 /stream + analysis_type=joint
const analysisType = jointMode.value ? 'joint' : (files.length > 1 ? null : analysisTypeForm.value)
const endpoint = jointMode.value || files.length === 1 ? '/api/v1/chat/stream' : '/api/v1/chat/compare'
```

### 后端改动：`backend/core/prompts.py`

新增 `joint` 分析类型模板：

```python
"joint": """
这些图像来自【同一材料样品】的多种检测（可能包含 FTIR 红外光谱、DSC 差示扫描量热、TGA 热重分析中的几种）。

请按以下步骤进行联合分析：
1. 识别：逐一说明每张图像对应的测试类型及主要特征
2. 各谱图解读：
   - FTIR：材料鉴定，官能团归属，特征峰波数
   - DSC：Tm/Tg/ΔHm，结晶度，热历史异常
   - TGA：起始分解温度，分解阶段，残留量，添加剂推断
3. 交叉关联分析：
   - IR 官能团 ↔ DSC 热转变的相互印证
   - DSC 结晶行为 ↔ TGA 热稳定性关系
   - 任何谱图间的矛盾点及可能原因
4. 综合结论：材料鉴定结果，置信度，建议后续验证测试
"""
```

`PromptTemplates.get_template(analysis_type)` 已有路由逻辑，直接新增 `"joint"` 分支即可，其余调用链（RAG、Claude Vision、SSE）不变。

---

## 功能 2：跨材料对比

### 用户交互流程

1. 用户进入新页面 `/cross-compare`（侧边栏入口「跨材料对比」）
2. 左栏：选择测试类型（FTIR / DSC / TGA）+ 从知识库条目中勾选 2–5 个参考材料
3. 右栏：上传待测谱图（1 张）
4. 点击「开始对比分析」→ `POST /api/v1/chat/cross-compare`
5. 流式文字输出 + 结束后渲染多曲线 `SpectraCompare` 卡片

### 前端新页面：`frontend/src/views/CrossCompare.vue`

**布局：**

```
┌──────────────────────────────────────────────────────┐
│  跨材料对比分析                                        │
├──────────────────────┬───────────────────────────────┤
│  参考材料（知识库）    │  待测样品                       │
│                      │                               │
│  类型: [FTIR ▾]      │  [ 上传谱图 ]                  │
│                      │                               │
│  ☑ PP  聚丙烯        │  unknown_ir.png ✕             │
│  ☑ PA6 尼龙6         │                               │
│  ☐ PE  聚乙烯        │                               │
│  ☑ ABS ABS树脂       │                               │
│  最多选 5 个          │                               │
│                      │                               │
│         [ 开始对比分析 ]                               │
└──────────────────────────────────────────────────────┘

── 分析结果 ──────────────────────────────────────────
[流式文字输出区]

[SpectraCompare 多曲线卡片]
```

**数据流：**

```javascript
// 请求
const formData = new FormData()
formData.append('file', unknownFile)
formData.append('material_ids', JSON.stringify(selectedIds))   // ["PP","PA6","ABS"]
formData.append('spec_type', specType)                         // "ftir"

// SSE 解析（与 FailureAnalysis 逻辑相同）
if (p.type === 'spectra_data' && p.mode === 'cross_compare') {
  result.spectraData = p  // 含 standard_materials[]
}
```

**路由注册**（`frontend/src/router/index.js` 或同等文件）：

```javascript
{ path: '/cross-compare', component: () => import('../views/CrossCompare.vue') }
```

### 数据来源说明

**参考材料来源：知识库（ChromaDB `materials` 集合）**，通过 `/api/v1/knowledge/entry/{id}` 获取各材料的 `ftir_peaks` / `dsc_parameters` / `tga_characteristics` 等结构化数据，以文字形式注入 prompt。不依赖 `StandardSpectrum` 表（该表存储的是用户手动上传的参考图，可能为空）。

- 参考材料选择器调用 `/api/v1/knowledge/entries`（与 SpectraCompare、IRViewer 一致）
- 多曲线可视化通过 `/api/v1/knowledge/entry/{id}` 获取 `ftir_peaks` 合成曲线（与现有 SpectraCompare 一致）

**待测样品**：用户上传的图像，作为唯一的视觉输入发给 Claude。

### 后端新端点：`backend/api/chat.py`

```python
@router.post("/cross-compare")
async def cross_compare(
    file: UploadFile = File(...),
    material_ids: str = Form(...),   # JSON 字符串 ["PP","PA6","ABS"]
    spec_type: str = Form("ftir"),   # ftir | dsc | tga
    db: Session = Depends(get_db),
):
```

**处理流程：**

1. 解析 `material_ids` JSON（校验 1–5 个）
2. 通过 `VectorRetriever` 从 ChromaDB 加载各材料的峰位/热参数数据
3. 保存上传文件到 `uploads/sessions/{session_id}/`
4. 构建 prompt（`analysis_type="cross_compare"`）：

```
参考材料数据库资料：
  【PP 聚丙烯】FTIR特征峰：2920 cm⁻¹(CH₂反对称伸缩，很强)；1456 cm⁻¹(CH₂弯曲，中)；998 cm⁻¹(CH₃摇摆，强)...
  【PA6 尼龙6】FTIR特征峰：3300 cm⁻¹(N-H伸缩，强)；1640 cm⁻¹(酰胺I带，很强)；1540 cm⁻¹(酰胺II带，强)...
  【ABS ABS树脂】FTIR特征峰：...

待测样品图像见附图（图1）。

请根据上方参考数据，逐一对比待测样品与每种参考材料的特征峰异同，
评估相似程度，给出最可能的材料鉴定结论及置信度。
```

5. 单次 Claude Vision 流式调用（仅含待测图像，参考材料以文字 context 传入）
6. 流结束后调用 `extract_peaks_structured()` → 发出扩展 `spectra_data` 事件：

```json
{
  "type": "spectra_data",
  "mode": "cross_compare",
  "observed_peaks": [...],
  "standard_materials": [
    {"id": "PP",  "label": "聚丙烯"},
    {"id": "PA6", "label": "尼龙6"},
    {"id": "ABS", "label": "ABS树脂"}
  ],
  "image_urls": ["/uploads/sessions/xxx/unknown.png"]
}
```

**错误处理：**

| 情况 | 处理 |
|------|------|
| 参考材料在 DB 中无对应图路径 | 跳过该材料，继续分析剩余 |
| 选中材料数 < 1 | 返回 400 |
| 选中材料数 > 5 | 返回 400 |
| 上传文件非图像/PDF | 返回 415 |

---

## 功能 2 共享：SpectraCompare 多曲线扩展

### 新增 prop

```typescript
standardMaterials: Array<{id: string, label: string}>
// 不为空时替代原 suggestedMaterial 单值逻辑
// 为空时保持原有单曲线行为（向后兼容）
```

### 颜色调色板（固定 5 色）

```javascript
const CURVE_COLORS = [
  'rgba(77,  156, 245, 0.75)',  // 蓝
  'rgba(52,  211, 153, 0.75)',  // 绿
  'rgba(251, 146,  60, 0.75)',  // 橙
  'rgba(192, 132, 252, 0.75)',  // 紫
  'rgba(251, 191,  36, 0.75)',  // 黄
]
```

### 图例扩展

单材料时（原行为）：
```
━━ 标准   ┃ 观测峰
```

多材料时：
```
━━ PP 聚丙烯   ━━ PA6 尼龙6   ━━ ABS ABS树脂   ┃ 观测峰
```

### Hover tooltip 扩展

新增 `materialLabel` 字段，标准峰显示来源材料：
```
1735 cm⁻¹
C=O 酯基伸缩
强度：很强
来源：PA6 参考
```

### 内部数据结构

```javascript
// allStandardPeaks: [{...peak, materialId, materialLabel, color}]
// 合并所有材料峰位后统一做 hover 检测
```

---

## 文件清单

| 操作 | 路径 | 说明 |
|------|------|------|
| 修改 | `backend/core/prompts.py` | 新增 `joint`、`cross_compare` 模板 |
| 修改 | `backend/api/chat.py` | 新增 `/cross-compare` 端点 |
| 修改 | `backend/tests/test_api.py` | 新增两端点测试 |
| 修改 | `frontend/src/views/FailureAnalysis.vue` | 联合分析开关 |
| 新建 | `frontend/src/views/CrossCompare.vue` | 跨材料对比页面 |
| 修改 | `frontend/src/components/SpectraCompare.vue` | 多曲线支持 |
| 修改 | `frontend/src/router/index.js`（或等效） | 注册 `/cross-compare` 路由 |

---

## 不改动范围

- `/api/v1/chat/stream` 端点签名不变
- `/api/v1/chat/compare` 端点不变
- `SpectraCompare` 现有单曲线行为向后兼容（`standardMaterials` 为空时行为不变）
- 知识库 ChromaDB 不改动
- `AnalysisCase` 数据库表不改动（跨材料对比结果作为新 `case_no` 存入，`failure_description` 字段记录「跨材料对比」）
