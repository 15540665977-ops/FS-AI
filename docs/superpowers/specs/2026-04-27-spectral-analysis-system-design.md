# 谱图智能分析系统 — 设计文档

**日期**：2026-04-27
**作者**：理想汽车 非金属材料工程师
**状态**：已批准，待实现

---

## 背景与目标

理想汽车非金属材料团队（主管塑料、弹性体类材料）需要一套 AI 辅助系统，用于分析红外光谱（FTIR）、差示扫描量热（DSC）、热重分析（TGA）等谱图数据，支持失效分析（主要场景）和一致性检验。

**核心要求**：
- 专业且准确，输出必须包含具体峰位（cm⁻¹）、温度（°C）、置信度和推断依据
- 结论区分"确认"与"疑似"，不允许模糊表述
- 可联网补充检索技术文献和材料数据表

---

## 输入格式

- **文件类型**：PDF 报告、PPT 文件、图片（截图/拍照）
- **不支持原始数值文件**（CSV/SPC 等），所有输入均为图像形式
- 来源：供应商检测报告、内部检测报告、仪器软件导出报告

---

## 核心使用场景

### 主场景：失效分析（失效件谱图对比分析）

用户上传失效件谱图（PDF/PPT/图片），可：
- 同时上传好件谱图作为临时对照（A 型）
- 从标准谱图库自动调取对应型号认可谱图（B 型）
- 仅上传失效件，依赖 AI 知识判断（补充）

### 次场景：一致性检验

来料批次谱图 vs. 认可标准谱图，输出相似度评分与差异说明。

---

## 系统架构

```
用户浏览器（Vue 3）
    ↕ HTTP / SSE
FastAPI 后端
    ├── 文件解析器（pymupdf / python-pptx / Pillow）→ 提取图像
    ├── 分析编排器
    │     ├── Claude claude-sonnet-4-6 Vision（读图 + 推理）
    │     ├── RAG 检索（ChromaDB 向量库 → 本地知识库）
    │     └── Tavily 联网搜索（技术文献 / 材料 TDS）
    └── 数据层
          ├── ChromaDB（专业知识向量索引）
          ├── SQLite（标准谱图档案 / 案例记录）
          └── 本地文件系统（谱图图像存储）
```

**部署**：Docker Compose，内网服务器，局域网 IP 访问，多用户共用。

---

## AI 分析流程

1. 用户上传文件，后端提取所有页面图像
2. Claude vision 读取谱图图像，识别特征峰位、热特征参数
3. RAG 检索本地知识库（材料峰位指纹 + 失效模式）
4. 若有对照谱图（标准库或临时上传），并行提取作为参考
5. Tavily 搜索补充联网信息（材料牌号 TDS、文献失效案例）
6. 综合以上信息构建 Prompt，Claude 生成流式分析回复
7. 分析结束后自动保存为案例记录

**输出规范**：
- 每个峰位观察必须标注波数（cm⁻¹）或温度（°C）
- 失效推断必须标注置信度（高 / 中 / 低）
- 每条 AI 回复标注知识来源（本地库 / 标准谱图库版本 / 联网文献）
- 推荐后续验证测试（如 OIT 测试、分子量测定等）

---

## 知识库设计

### 模块 1：材料特征峰指纹库（~30 种）

每条记录包含：材料名称、聚合物类型、FTIR 特征峰列表（峰位 + 归属 + 强度描述）、DSC 热参数（Tm/Tg/ΔHm）、TGA 分解特征（起始温度/残留量）、鉴别要点。

**初始覆盖材料**：
- 塑料：PP、PE-HD、PE-LD、PA6、PA66、PC、ABS、POM、PMMA、PVC、PBT、PC/ABS
- 弹性体：EPDM、TPO、SEBS/SBS、TPU、NBR、CR、硅橡胶（VMQ）、氟橡胶（FKM）
- 其他：PP-GF（玻纤增强）、PA-GF 系列

### 模块 2：失效模式特征库（~15 种）

每条记录包含：失效名称、机理描述、FTIR 变化特征（新增峰/消失峰/强度变化）、DSC 变化特征、TGA 变化特征、典型发生材料、鉴别置信度说明。

**初始覆盖失效模式**：
- 热氧老化（PP/PE/EPDM）：1735 cm⁻¹ 羰基峰出现，3400 O-H 增强
- PA 水解降解：酰胺Ⅱ峰减弱，末端羧基 1710 cm⁻¹ 增强
- 增塑剂迁移（PVC/TPU）：增塑剂特征峰强度下降
- 硅油污染：1260 cm⁻¹ Si-CH₃ 特征峰出现
- 错料替换：基础树脂指纹区整体不符
- 碳黑/填料含量异常：TGA 残留量偏离规格
- UV 光降解：羰基区变化 + 共轭结构峰
- 溶剂/化学品侵蚀：特定溶剂特征峰残留
- 过度交联（橡胶）：DSC Tg 升高，TGA 残留炭增加
- 欠硫化（橡胶）：可溶性组分峰残留

### 模块 3：标准谱图档案

字段：`material_id`、`material_name`、`grade`、`supplier`、`approved_date`、`version`、`ir_image_path`、`dsc_image_path`、`tga_image_path`、`key_peaks`（JSON）、`key_thermal`（JSON）、`notes`、`created_by`。

---

## 数据库模型（SQLite）

### `standard_spectra`（标准谱图档案）
```sql
id, material_name, grade, supplier, approved_date, version,
ir_image_path, dsc_image_path, tga_image_path,
key_peaks TEXT,        -- JSON: [{wavenumber, assignment, intensity}]
key_thermal TEXT,      -- JSON: {tm, tg, tga_onset, tga_residue}
notes TEXT, created_by, created_at
```

### `analysis_cases`（分析案例记录）
```sql
id, case_no,           -- FA-YYYY-NNN 自动生成
material_name, failure_description,
uploaded_files TEXT,   -- JSON: 文件路径列表
reference_source,      -- "library" | "manual_upload" | "none"
reference_id,          -- 关联 standard_spectra.id（若来自标准库）
analysis_result TEXT,  -- 完整对话 JSON
conclusion,            -- 最终结论文本
confidence_level,      -- high/medium/low
created_by, created_at
```

---

## 前端页面

### 1. 失效分析（主页）
- 左栏：功能切换 + 历史案例列表
- 右侧：对话区（文件上传 + 流式 AI 回复 + 追问）
- 上方选择对照来源：标准库匹配 / 手动上传对照 / 纯知识分析

### 2. 一致性检验
- 上传批次报告 + 选择基准版本 → 生成一致性报告

### 3. 标准谱图库管理
- 录入：填写材料信息 + 上传三张谱图图像
- 检索：按材料名/供应商/日期筛选

### 4. 案例记录
- 按日期/材料/结论筛选历史案例
- 查看完整对话记录

---

## 技术栈

| 层级 | 选型 |
|------|------|
| 后端框架 | FastAPI |
| PDF 解析 | pymupdf (fitz) |
| PPT 解析 | python-pptx |
| 图像处理 | Pillow |
| AI 模型 | claude-sonnet-4-6（vision + tool use） |
| 联网搜索 | tavily-python |
| 向量数据库 | chromadb |
| 结构化数据库 | SQLite + SQLAlchemy |
| 前端框架 | Vue 3 + Vite + Element Plus |
| 流式输出 | Server-Sent Events (SSE) |
| 部署 | Docker Compose |

---

## 项目目录结构

```
spectral_analysis_system/
├── backend/
│   ├── main.py                  # FastAPI 入口
│   ├── api/
│   │   ├── chat.py              # 对话 & 分析路由
│   │   ├── library.py           # 标准谱图库路由
│   │   └── cases.py             # 案例记录路由
│   ├── core/
│   │   ├── analyzer.py          # 分析编排主逻辑
│   │   ├── file_parser.py       # PDF/PPT/图片 → 图像
│   │   ├── rag.py               # ChromaDB 向量检索
│   │   ├── web_search.py        # Tavily 联网搜索
│   │   └── prompts.py           # 专业 Prompt 模板
│   ├── knowledge/
│   │   ├── materials.json       # 材料峰位指纹（初始数据）
│   │   ├── failure_modes.json   # 失效模式知识（初始数据）
│   │   └── seed_knowledge.py    # 初始化向量库脚本
│   ├── db/
│   │   ├── models.py            # SQLAlchemy 模型
│   │   └── database.py          # DB 连接
│   └── uploads/                 # 上传文件临时目录
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── FailureAnalysis.vue
│   │   │   ├── ConsistencyCheck.vue
│   │   │   ├── StandardLibrary.vue
│   │   │   └── CaseRecords.vue
│   │   └── components/
│   │       ├── ChatMessage.vue
│   │       └── FileUpload.vue
│   └── package.json
├── docker-compose.yml
└── .env.example                 # ANTHROPIC_API_KEY / TAVILY_API_KEY
```

---

## 关键约束

1. **API 密钥**：需要 `ANTHROPIC_API_KEY`（Claude API）和 `TAVILY_API_KEY`（联网搜索）
2. **图像质量**：分析精度依赖谱图图像清晰度，系统在接收低质量图像时需给出明确提示
3. **知识库初始化**：部署前需运行 `seed_knowledge.py` 完成向量库初始化
4. **数据安全**：材料谱图数据属于公司内部资产，系统仅限内网访问，不对外暴露
