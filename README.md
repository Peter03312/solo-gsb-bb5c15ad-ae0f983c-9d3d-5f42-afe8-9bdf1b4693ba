# 陶片拼接系统

面向文物修复人员的陶片拼接 Web 应用：录入毫米制闭合轮廓，基于对应边缘标记
做纯平移 + 旋转的刚体配准，支持预览、采纳、撤销与连通组管理。

## 功能

- **碎片录入**：画布点击或粘贴 JSON 录入毫米制闭合轮廓；自交轮廓整次拒绝。
- **候选拼接**：两片各至少 2 处对应边缘标记（数量一致、同片不重合）。
- **预览**：仅经平移 + 旋转的组合，显示各片位置 (x, y)、角度 (°)、每对
  对应点误差及冲突原因，不落库。
- **采纳校验**（任一不满足即整次拒绝，原拼接组不变）：
  - 同组对应点误差均 ≤ 1 mm；
  - 同组陶片轮廓内部不重叠（允许共边/共点）；
  - 合并两组时整体移动其中一组，组内相对位姿不变；
  - 同组内新增关系（闭环）必须符合已有位姿。
- **撤销**：按剩余有效关系重算连通组，孤片恢复独立状态。
- **有序试拼**：基于当前装配版本快照编排**非空有序**的操作序列（每步为
  「撤销一条现存有效关系」或「以两片陶片 + 成对边缘标记建立关系」），
  在内存快照上逐步推演预演，返回每步结果、最终位姿与分组（或首个失败
  原因），全程不改数据；确认时按同一版本与同一序列整体提交，任一步失败
  或版本过期均不写入任何变化，成功仅递增一次装配版本。
- **轮廓修订**：修复师发现某片陶片轮廓测量有误时，可选中该片提交
  修订后的毫米制闭合轮廓、**该片每一条有效拼接关系**在本片一侧的全新
  边缘标记及期望装配版本，先预览再确认。修订轮廓须通过现有非自交校验；
  新标记须位于修订轮廓边缘、数量与关系另一端一致、至少 2 处且同片不
  重合；随后**保持现有位姿不变**，检查受影响连通组全部有效关系的逐对
  对应点误差 ≤ 1 mm、组成员轮廓内部不重叠。独立碎片只校验轮廓。预览
  返回逐条误差与冲突原因、不落库；确认时重新校验同一输入并原子更新
  轮廓、相关标记与误差——位姿、关系 ID、连通分组与已撤销历史均不变，
  装配版本只 +1。遗漏任何有效关系、任一校验失败均整次拒绝；版本过期
  返回 409。
- **整体校准**：修复师从当前装配选一片作**锚点**，对其所在连通组请求
  整体校准——以组内**全部有效关系**的成对边缘标记共同最小化对应点误差
  平方和（只调整其余碎片的平移和旋转）。**锚点位姿、碎片轮廓、标记、
  关系状态（active / undone_at / created_at）及连通分组均不变**。预览
  展示调整前/后位姿（x、y、角度与位移量）、逐关系逐对对应点误差、误差
  总量变化与轮廓冲突，不写库；**仅当①误差总量严格下降、②每对对应点误差
  均 ≤ 1 mm、③组内轮廓内部不重叠时才可确认**，否则逐条说明原因并保持
  现状。确认携带预览依据的装配版本，在同一事务内重算校验、更新非锚点
  碎片位姿与组内有效关系误差，版本只递增一次并留下不可改快照；版本过期
  返回 409，锚点不存在返回 404，锚点所在组不足两片（独立碎片）返回 400，
  均不写入。校准前/后版本都可在历史中查看与恢复。
- **乐观并发**：采纳 / 撤销 / 删除 / 试拼确认 / 轮廓修订确认 / 整体校准确认
  携带期望版本号，过期版本返回 409 冲突提示。
- **不可改版本快照与历史恢复**：录入/删除碎片、采纳/撤销拼接、试拼确认、
  轮廓修订确认、整体校准确认每次成功都与装配数据在**同一事务**内固化一条
  版本快照（碎片轮廓与位姿、有效及已撤销关系、连通组），快照一经写入不可改、
  不可删；启用版本历史时（含旧库升级）把当前状态记为**基线**快照；
  预览与失败操作不产生快照。修复师可在「查看装配」页按版本只读回看，
  选择历史版先**预览恢复后的完整装配及与当前版的碎片/关系差异**（不写
  库），确认时提交预览依据的当前版本号：版本过期（409）或目标版不存在
  （404）均拒绝且不写入；成功后原子恢复该版碎片与关系的**原 ID 及状态**
  （含 active / undone_at / created_at、轮廓、标记、位姿），重算连通组，
  装配版本只 +1 并留下新的 `restore` 快照，旧快照全部保留仍可查。

## 一键启动（Docker Compose）

```bash
docker compose up --build
```

构建镜像时自动安装依赖，容器启动时自动初始化 SQLite 表结构与演示数据。

- **访问地址**：http://localhost:8000
- **端口**：`8000`（宿主机映射，可在 `docker-compose.yml` 的 `ports` 中修改）
- **API 文档**：http://localhost:8000/docs

## 本地开发

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000 。

## 配置（环境变量）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_PATH` | `data/app.db`（容器内 `/app/data/app.db`） | SQLite 数据库文件路径 |
| `SEED_DEMO_DATA` | `1` | 首次启动且库为空时写入 4 片演示陶片；设为 `0` 关闭 |

Compose 默认将数据库挂载到命名卷 `pottery-data` 持久化。

## 使用流程

1. **录入碎片**：点击「录入碎片」，在主画布单击添加轮廓顶点（毫米制，
   滚轮缩放、拖拽平移），≥3 个顶点后保存；或直接粘贴坐标 JSON。
2. **新建拼接**：点击「新建拼接」，选择碎片甲 / 乙，在两个小图中点击
   轮廓边缘放置对应标记（每片 ≥2 处、数量一致，按序号一一对应）。
3. **预览**：查看组合后的各片位置、角度、每对误差与冲突原因。
4. **采纳**：校验全部通过才落库；任何冲突整次拒绝，原拼接组不变。
5. **撤销**：在「查看装配」页对有效关系点「撤销」，连通组自动重算。
6. **有序试拼**（多步预演 + 一次确认）：
   - 在「新建拼接」页放好两片标记后点「**加入试拼**」，或在「查看装配」页
     点有效关系旁的「**试拼撤销**」，把操作排入序列；
   - 侧栏「有序试拼」自动向服务器预演，逐步显示可执行 / 冲突原因，主画布
     以蓝色展示预演后的最终位姿与连通组（此时数据未改变）；
   - 全部步骤通过后点「**确认整组提交**」：按当前版本与整个序列原子写入，
     版本只 +1；任一步失败或版本过期则没有任何变化，按提示刷新后重试。
7. **修订轮廓**（测量有误时，先预览再确认）：
   - 在「查看装配」页点碎片卡片上的「**修订轮廓**」，进入修订页；
   - 在主画布单击绘制修订后的闭合轮廓（局部坐标、毫米制，可粘贴 JSON /
     一键重置为现轮廓）；
   - 每条有效拼接关系都有一个小图，在本片修订轮廓边缘点击放置新标记
     （自动吸附边缘，数量须与另一端一致、≥2 处、同片不重合；独立碎片
     无需标记）；
   - 点「**预览**」：以现有位姿在主画布显示受影响组的逐对对应点（绿色
     通过 / 红色冲突），侧栏列出逐关系逐条误差、最大误差、碰撞与冲突
     原因，此时**不写库**；
   - 预览通过后点「**确认修订**」：服务器用同一输入重新校验，原子更新
     轮廓、相关标记与误差；位姿、关系 ID、连通分组、已撤销历史均不变，
     装配版本只 +1；任何冲突整次拒绝且没有任何变化，版本过期按提示刷新。
8. **按版本查看与恢复**（历史只读 → 恢复预览 → 确认）：
   - 在「查看装配」页底部「**历史版本**」列表（新版本在前，标注变更来源
     与当前版）点「**查看**」，主画布以紫色只读展示该版的碎片轮廓、位姿、
     连通组与有效/已撤销关系，当前数据不变；
   - 点「**恢复预览**」（或历史版页的「恢复到此版本…」），主画布以蓝色
     展示恢复后的完整装配，侧栏列出与当前版的差异：碎片重现/删除/变更
     （轮廓、位姿等字段）、关系恢复/删除/变更（含「由撤销→有效」），
     以及恢复后连通组；预览**不写库**；
   - 点「**确认恢复**」：提交预览依据的当前版本号，成功则原子恢复该版
     碎片与关系的原 ID、原状态，重算连通组，装配版本只 +1，留下来源为
     「版本恢复」的新快照，旧快照仍可在列表中查看；版本过期或目标版已
     不存在则按提示刷新，不写入任何变化。
9. **整体校准**（以一片为锚点，先预览再确认）：
   - 在「查看装配」页对拼接组内任一碎片卡片点「**整体校准**」（独立碎片
     无此入口），即选该片为锚点；
   - 主画布以**橙色高亮锚点、蓝色显示校准后位姿**，灰色虚线叠加校准前
     轮廓，绿色/红色连出组内全部有效关系校准后的逐对对应点（标注毫米
     误差），侧栏列出确认条件、调整前→后位姿表、逐关系逐对误差与轮廓
     重叠明细，此时**不写库**；
   - 仅当误差总量严格下降、每对误差均 ≤ 1 mm、组内轮廓内部不重叠时
     「**确认校准**」可用；确认后仅更新非锚点碎片位姿与有效关系误差，
     锚点位姿/轮廓/标记/关系状态/连通分组不变，装配版本只 +1 并留下
     「整体校准确认」快照；条件不满足会逐条说明原因，保持现状；版本过期
     按提示刷新后重新预览。校准前后版本均可在「历史版本」中查看/恢复。

## API 概览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/fragments` | 录入碎片（自交轮廓 400 拒绝） |
| `GET` | `/api/fragments` | 碎片列表 |
| `DELETE` | `/api/fragments/{id}?expected_version=N` | 删除碎片及其关系 |
| `POST` | `/api/relations/preview` | 预览拼接（不落库） |
| `POST` | `/api/relations` | 采纳拼接（携带 `expected_version`） |
| `POST` | `/api/relations/{id}/undo` | 撤销关系（携带 `expected_version`） |
| `GET` | `/api/relations` | 关系列表（含已撤销历史） |
| `GET` | `/api/assembly` | 装配快照：版本、位姿、连通组、关系 |
| `GET` | `/api/assembly/versions` | 历史版本清单（版本/来源/快照时间，新版本在前） |
| `GET` | `/api/assembly/versions/{v}` | 只读查看历史版完整装配（轮廓/位姿/有效及已撤销关系/连通组） |
| `POST` | `/api/assembly/versions/{v}/restore/preview` | 恢复预览：恢复后完整装配 + 与当前版碎片/关系差异（不落库） |
| `POST` | `/api/assembly/versions/{v}/restore/confirm` | 确认恢复（原子恢复原 ID 与状态、重算连通组，版本只 +1，留新快照） |
| `POST` | `/api/trials/rehearse` | 有序试拼预演（不落库） |
| `POST` | `/api/trials/commit` | 有序试拼整组确认（原子，版本只 +1） |
| `POST` | `/api/fragments/{id}/revision/preview` | 轮廓修订预览（逐条误差/冲突，不落库） |
| `POST` | `/api/fragments/{id}/revision/confirm` | 轮廓修订确认（重新校验同一输入，原子更新，版本只 +1） |
| `POST` | `/api/calibration/preview?anchor_id=K` | 整体校准预览（锚点固定，调整前后位姿/逐关系误差/轮廓冲突，不落库） |
| `POST` | `/api/calibration/confirm?anchor_id=K` | 整体校准确认（同事务重算校验、更新位姿与有效关系误差，版本只 +1） |

错误约定：`400` 校验拒绝（轮廓自交 / 标记重合 / 标记不在边缘 / 标记数量
不一致 / 遗漏有效关系 / 误差超限 / 碰撞 / 空序列 / 撤销目标非法 / 目标
版本即当前版 / **锚点所在组不足两片 `group_too_small` / 误差总量未严格
下降或校准后不满足确认条件**），`404` 对象不存在（碎片、关系、**目标
版本快照**、**校准锚点 `anchor_not_found`**，版本恢复时
`detail.code=version_not_found`），`409` 版本冲突或重复撤销（含恢复
预览/确认、整体校准预览/确认的期望版本过期），`422` 请求体结构不合法。

## 有序试拼 API

两个端点请求体相同：`expected_version`（所基于的装配版本）+ 非空 `steps`。
每个 step 通过 `action` 区分：

```jsonc
// 建立关系：两片陶片 + 成对边缘标记（每片 ≥2 处、数量一致、同片不重合）
{ "action": "relate", "fragment_a": 1, "fragment_b": 2,
  "markers_a": [[35,0],[38,15]], "markers_b": [[1,0],[4,15]],
  "client_id": "s1" }          // 可选，序列内唯一，供后续撤销步引用

// 撤销：relation_id 撤销已落库关系；client_id 撤销序列内前序新建关系
{ "action": "undo", "relation_id": 3 }
{ "action": "undo", "client_id": "s1" }
```

### 预演（不落库）

```bash
curl -X POST http://localhost:8000/api/trials/rehearse \
  -H 'Content-Type: application/json' \
  -d '{
    "expected_version": 1,
    "steps": [
      {"action":"relate","fragment_a":1,"fragment_b":2,
       "markers_a":[[35,0],[38,15],[33,30]],
       "markers_b":[[1,0],[4,15],[-1,30]],"client_id":"s1"},
      {"action":"undo","client_id":"s1"},
      {"action":"relate","fragment_a":1,"fragment_b":2,
       "markers_a":[[35,0],[38,15]],
       "markers_b":[[1,0],[4,15]],"client_id":"s2"}
    ]
  }'
```

成功响应：`ok=true`，`steps[]` 含每步类型、对应点误差、涉及碎片位姿、
当步后的连通组；`assembly` 为最终位姿 / 分组 / 关系快照（预演新建关系使用
负的临时 id，`assembly.version` 仍为所基于的版本）。

任一步失败时 HTTP 仍为 `200`，但 `ok=false`：`failed_at` 与 `failure`
给出首个失败步、错误码（如 `relation_inactive` / `fragment_missing` /
`relation_not_found` / `client_relation_not_found` / `rejected`）、人类可读
原因与冲突明细；`steps[]` 只含失败步之前的成功步，`assembly` 为失败前一刻
快照。版本过期返回 `409`。

### 确认（整体提交）

```bash
curl -X POST http://localhost:8000/api/trials/commit \
  -H 'Content-Type: application/json' \
  -d '{"expected_version":1,"steps":[
    {"action":"relate","fragment_a":1,"fragment_b":2,
     "markers_a":[[35,0],[38,15]],"markers_b":[[1,0],[4,15]],
     "client_id":"s1"}
  ]}'
# 201: {"ok":true,"version":2,"committed_steps":1,
#       "relation_ids":{"s1":1},"assembly":{...}}
```

- 全部步骤通过 → `201`，返回新版本号、`client_id → 真实关系 id` 映射和
  最新装配快照，整个序列只递增一次版本；
- 任一步失败 → `400/404/409`，`detail` 含 `failed_at / step / action /
  code / message`，**不写入任何变化**；
- `expected_version` 过期 → `409`，同样不写入。

明确的报错约定：重复撤销（关系已失效）→ `409 relation_inactive`；碎片缺失
→ `404 fragment_missing`；关系 id 缺失 → `404 relation_not_found`；撤销
未知 `client_id` → `404 client_relation_not_found`；同片建立关系、标记数量
不足 / 重合、误差 >1mm、轮廓内部重叠、闭环不符位姿 → `400 rejected`
（冲突明细在 `conflicts[]`）；空序列 / 撤销同时给或不给目标 /
`client_id` 重复 → `400`。

## 轮廓修订 API

选中碎片 `#1`，提交**修订后的毫米制闭合轮廓** `contour`、**该片每一条有效
关系**在本片一侧的新边缘标记 `relations[]`，以及所基于的
`expected_version`。每个条目按 `relation_id` 指定关系、`markers` 给出本片
（关系的 A 侧或 B 侧由系统判定）修订后的标记；关系另一端的标记不可在此
修改。

新标记的约束与建拼一致并额外要求**位于修订轮廓边缘**：数量与另一端一致、
每侧 ≥2 处、同片不重合；遗漏任何一条有效关系整次拒绝。独立碎片
（无有效关系）提交空 `relations`，只做轮廓非自交校验。

### 预览（不落库）

```bash
curl -X POST http://localhost:8000/api/fragments/1/revision/preview \
  -H 'Content-Type: application/json' \
  -d '{
    "expected_version": 3,
    "contour": [[0,0],[35,0],[38,15],[33,30],[37,45],[34,60],[0,60]],
    "relations": [
      {"relation_id": 1, "markers": [[35,0],[38,15],[33,30]]}
    ]
  }'
```

HTTP 恒为 `200`（版本过期为 `409`、碎片/关系不存在为 `404`），响应：

```jsonc
{
  "ok": true,
  "fragment_id": 1,
  "expected_version": 3,
  "independent": false,
  "missing_relation_ids": [],            // 未提交的有效关系 id（有则必拒绝）
  "contour": [[0.0,0.0], "..."],         // 规范化后的修订轮廓
  "conflicts": [],                       // 全局冲突原因（轮廓/标记/误差/碰撞）
  "involved_fragment_ids": [1, 2],       // 受影响连通组
  "relations": [
    { "relation_id": 1, "revised": true, "side": "a",
      "fragment_a": 1, "fragment_b": 2, "other_fragment_id": 2,
      "required_count": 3, "marker_count": 3,
      "errors": [0.0, 0.0, 0.0],         // 逐对对应点误差（mm，位姿保持不变）
      "max_error_mm": 0.0,
      "conflicts": [],                   // 该关系自身的冲突（超限/标记问题）
      "markers_a": [[35,0],"..."],       // 预览生效后的两侧标记（仅替换本片侧）
      "markers_b": [[1,0],"..."] }
  ],
  "overlaps": []                         // 组成员轮廓内部重叠明细（mm²）
}
```

- 受影响连通组内**不直接涉及**修订片的关系也会在 `relations[]` 中逐条核验
  （`revised=false`），其误差必须仍 ≤ 1 mm；
- `ok=false` 时 `conflicts[]` 汇总全部冲突，`relations[].conflicts` 给出逐
  关系明细，`overlaps[]` 给出碰撞双方与重叠面积；预览不写库，可修改后重预。

### 确认（原子更新，版本只 +1）

请求体与预览**完全相同**（服务端重新校验同一输入）：

```bash
curl -X POST http://localhost:8000/api/fragments/1/revision/confirm \
  -H 'Content-Type: application/json' \
  -d '{
    "expected_version": 3,
    "contour": [[0,0],[35,0],[38,15],[33,30],[37,45],[34,60],[0,60]],
    "relations": [
      {"relation_id": 1, "markers": [[35,0],[38,15],[33,30]]}
    ]
  }'
# 201: {"ok":true,"fragment_id":1,"version":4,"assembly":{...}}
```

- 全部通过 → `201`：原子写入修订轮廓、每条相关关系本片侧的新标记及最新
  最大误差；**位姿（x/y/theta）、关系 id、连通分组（group_id）、已撤销
  历史（active/undone_at/created_at）保持不变**，装配版本只 +1，返回最新
  装配快照；
- 任一校验失败 → `400`，`detail` 内附与预览相同结构的逐条结果
  （`conflicts / relations / overlaps / missing_relation_ids`），**不写入
  任何变化**；
- `expected_version` 过期 → `409` 冲突提示，不写入；碎片不存在 → `404`；
  提交了库里不存在的关系 id → `404 relation_not_found`；提交已撤销 / 不涉及
  本片的关系、同关系重复提交、遗漏有效关系、标记数量不一致 / 不足 2 处 /
  同片重合 / 不在修订轮廓边缘 → `400`。

## 整体校准 API

以锚点碎片 `anchor_id`（query 参数）所在连通组为对象，用组内**全部有效
关系**的成对边缘标记联合最小化对应点误差平方和（Levenberg–Marquardt，
解析雅可比），只调整其余碎片的平移和旋转；锚点位姿、轮廓、标记、关系
状态与连通分组不变。两个端点请求体都只含预览所依据的
`expected_version`。

### 预览（不落库）

```bash
curl -X POST 'http://localhost:8000/api/calibration/preview?anchor_id=1' \
  -H 'Content-Type: application/json' -d '{"expected_version": 6}'
```

HTTP 恒为 `200`（版本过期为 `409`、锚点不存在为 `404 anchor_not_found`、
锚点为独立碎片为 `400 group_too_small`），响应：

```jsonc
{
  "ok": true,                          // 三条确认条件同时满足才为 true
  "anchor_id": 1,
  "expected_version": 6,
  "fragment_ids": [1, 2, 3],           // 锚点所在连通组
  "relation_count": 3, "iterations": 4,
  "sse_before_mm2": 0.32, "sse_after_mm2": 0.146224,
  "sse_delta_mm2": -0.173776,
  "strictly_improved": true,           // 误差总量是否严格下降（忽略 ≤1e-9 噪声）
  "fragments": [
    { "fragment_id": 1, "name": "陶片A-左半", "anchor": true, "moved": false,
      "group_id": 1,
      "x_before": 0.0, "y_before": 0.0, "theta_deg_before": 0.0,
      "x_after": 0.0, "y_after": 0.0, "theta_after": 0.0, "theta_deg_after": 0.0,
      "dx": 0.0, "dy": 0.0, "dtheta_deg": 0.0 },
    { "fragment_id": 2, "anchor": false, "moved": true, "...": "调整前后位姿与 Δ",
      "theta_deg_before": 0.0, "theta_deg_after": 1.2219,
      "dx": 0.1029, "dy": 0.0092, "dtheta_deg": 1.2219 }
  ],
  "relations": [
    { "relation_id": 1, "fragment_a": 1, "fragment_b": 2, "marker_pairs": 2,
      "errors_before": [0.0, 0.0], "errors_after": [0.0681, 0.0523],
      "max_error_before_mm": 0.0, "max_error_after_mm": 0.0681,
      "markers_a": ["..."], "markers_b": ["..."] }
  ],
  "overlaps": [],                      // 校准后组内轮廓内部重叠明细（mm²）
  "conflicts": []                      // 未满足确认条件的逐条原因
}
```

- 三条确认条件：`strictly_improved=true`（总量严格下降）、全部
  `errors_after ≤ 1`（逐对）、`overlaps` 为空（允许共边/共点）；
- `ok=false` 时 `conflicts[]` 汇总原因（未严格下降 / 逐对超限 / 碰撞），
  预览不写库，可更换锚点后重新预览。

### 确认（同一事务，版本只 +1）

请求体与预览相同，以同一锚点在服务端重新演算：

```bash
curl -X POST 'http://localhost:8000/api/calibration/confirm?anchor_id=1' \
  -H 'Content-Type: application/json' -d '{"expected_version": 6}'
# 201: {"ok":true,"anchor_id":1,"version":7,"assembly":{...}}
```

- 全部条件满足 → `201`：同一事务内更新非锚点碎片的 x/y/theta、组内有效
  关系的 `max_error`（以新位姿重算），重算校验，装配版本只 +1，留下
  `source=calibration` 的不可改快照；**锚点位姿、碎片轮廓、两侧标记、
  关系 ID 与 active/undone_at/created_at、连通分组均不变**；
- 任一条件不满足 → `400`，`detail` 内附与预览同结构的结果
  （`conflicts / fragments / relations / overlaps / sse_*`），**不写入
  任何变化**；`expected_version` 过期 → `409`；锚点不存在 → `404`；
  锚点所在组不足两片 → `400 group_too_small`。

## 历史版本 API

碎片录入 / 删除、拼接采纳 / 撤销、试拼确认、轮廓修订确认、整体校准确认
每次成功都在同一
事务内写入不可改快照；服务启用时（含旧库升级、首次空库初始化）若尚无快照，
把当前状态记为 `baseline` 基线。快照来源 `source` 取值：

| source | 含义 |
| --- | --- |
| `baseline` | 基线（启用版本历史时记录，旧库升级为当前版补记） |
| `create` / `delete` | 录入 / 删除碎片 |
| `accept` / `undo` | 采纳 / 撤销拼接 |
| `trial` | 有序试拼整组确认 |
| `revision` | 轮廓修订确认 |
| `calibration` | 整体校准确认（锚点固定的组内联合最小二乘） |
| `restore` | 历史版本恢复（恢复后留下的新快照） |

预览（拼接 / 试拼预演 / 修订预览 / **整体校准预览** / 恢复预览）与任何
失败、过期操作都**不产生快照**。

### 版本清单

```bash
curl http://localhost:8000/api/assembly/versions
```

```jsonc
{
  "current_version": 3,
  "versions": [
    { "version": 3, "source": "undo", "source_label": "撤销拼接",
      "created_at": "2026-10-05T08:01:38+00:00", "current": false },
    { "version": 2, "source": "accept", "source_label": "采纳拼接", "...": "…" },
    { "version": 1, "source": "baseline", "source_label": "基线（启用版本历史时记录）",
      "created_at": "…", "current": false }
  ]
}
```

### 查看历史版（只读）

```bash
curl http://localhost:8000/api/assembly/versions/2
```

响应与 `GET /api/assembly` 同结构，并附版本元信息；`assembly.historical=true`，
`assembly.version` 为被查看的版本。可查看该版**碎片轮廓、位姿（x/y/theta）、
连通组、全部关系（含 active=false 的已撤销关系及其 undone_at）**：

```jsonc
{
  "version": 2, "source": "accept", "source_label": "采纳拼接", "created_at": "…",
  "assembly": {
    "version": 2, "historical": true,
    "fragments": [ { "id": 1, "name": "陶片A-左半", "contour": [[0,0], "..."],
                     "x": 0, "y": 0, "theta": 0, "group_id": 1, "created_at": "…" } ],
    "groups": [ { "id": 1, "fragment_ids": [1, 2] } ],
    "relations": [ { "id": 1, "fragment_a": 1, "fragment_b": 2,
                     "markers_a": ["..."], "markers_b": ["..."], "max_error": 0.0,
                     "active": true, "created_at": "…", "undone_at": null } ]
  }
}
```

目标版本快照不存在 → `404 {"detail":{"code":"version_not_found", …}}`。

### 恢复预览（不落库）

请求体只含预览所依据的**当前**装配版本：

```bash
curl -X POST http://localhost:8000/api/assembly/versions/2/restore/preview \
  -H 'Content-Type: application/json' -d '{"expected_version":3}'
```

响应给出恢复后的完整装配（`restored_assembly`，按目标版碎片重算连通组）与
逐对象差异 `diff`；`new_version` 为确认成功后的版本（当前 +1）。预览不改
当前数据、不产生快照：

```jsonc
{
  "ok": true, "expected_version": 3, "target_version": 2,
  "source": "accept", "source_label": "采纳拼接", "snapshot_created_at": "…",
  "new_version": 4,
  "restored_assembly": { "version": 2, "historical": true,
    "fragments": ["..."], "groups": ["..."], "relations": ["..."] },
  "diff": {
    "current_version": 3, "target_version": 2,
    "fragments": {
      "restored": [ { "id": 5, "target": { "…": "目标版碎片（恢复后重现）" } } ],
      "removed":  [ { "id": 6, "current": { "…": "当前版碎片（恢复后删除）" } } ],
      "changed":  [ { "id": 2, "changed_fields": ["x","theta"],
                      "current": {"…": "…"}, "target": {"…": "…"} } ],
      "unchanged": [ { "id": 1 } ]
    },
    "relations": {
      "restored": [ { "id": 1, "target": { "active": true, "…": "曾被删除的关系随恢复重现" } } ],
      "removed":  [ { "id": 7, "current": { "…": "目标版之后建立、恢复后删除" } } ],
      "changed":  [ { "id": 1, "changed_fields": ["active","undone_at"],
                      "current": { "active": false, "undone_at": "…" },
                      "target":  { "active": true,  "undone_at": null } } ],
      "unchanged": [ { "id": 3, "active": true } ]
    },
    "groups": { "current":  ["..."], "target": ["..."] },
    "summary": { "fragments": { "restored": 1, "removed": 1, "changed": 1, "unchanged": 2 },
                 "relations": { "restored": 0, "removed": 1, "changed": 1, "unchanged": 0 } }
  }
}
```

- 期望版本过期 → `409`（同其它端点的版本冲突约定）；
- 目标版不存在 → `404 version_not_found`；目标版即当前版 →
  `400 target_is_current`（无需恢复）。

### 确认恢复（原子，版本只 +1）

请求体与预览**完全相同**（只提交 `expected_version`，即预览依据的当前版）：

```bash
curl -X POST http://localhost:8000/api/assembly/versions/2/restore/confirm \
  -H 'Content-Type: application/json' -d '{"expected_version":3}'
# 201:
# {"ok":true,"restored_from_version":2,"expected_version":3,"version":4,
#  "assembly":{ "version":4, "fragments":[…], "groups":[…], "relations":[…] }}
```

- 成功：在锁与同一事务内**原子恢复目标版碎片与关系的原 ID 及状态**
  （轮廓、位姿、标记、`max_error`、`active`、`created_at`、`undone_at`
  全部按该版原样），目标版之后新增的碎片/关系删除、删除的按原 ID 重现，
  随后按有效关系**重算连通组**；装配版本只 +1，并留下 `source=restore`
  的新快照；**旧快照（含被恢复版本身）全部保留、仍可查看/再次恢复**；
- `expected_version` 与当前版不符（预览后数据已被他人变更）→ `409`，
  不写入；目标版不存在 → `404 version_not_found`，不写入；目标版即当前版
  → `400`，不写入。

## 项目结构

```
app/
  main.py          # FastAPI 路由、单条拼接、版本控制、试拼/修订/整体校准/历史恢复端点
  history.py       # 历史版本：来源标签、连通组重算、碎片/关系差异演算（只读）
  revision.py      # 轮廓修订：边缘标记校验、受影响组误差/碰撞演算（只读）
  calibration.py   # 整体校准：锚点连通组联合最小二乘、前后误差/重叠演算（只读）
  trial.py         # 有序试拼：内存快照逐步推演 + 整组提交 + 位姿演算
  geometry.py      # 刚体配准（最小二乘）、整体校准 LM 求解、轮廓/标记校验、重叠检测
  database.py      # SQLite 持久化、连通组重算、不可改版本快照、按版恢复
  static/          # 浏览器二维画布前端（原生 JS）
Dockerfile
docker-compose.yml
requirements.txt
```
