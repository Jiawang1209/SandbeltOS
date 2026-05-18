# Demo 录制 SOP

> **目标产出**：2–3 分钟视频，展示 5 个核心动作。
> 视频既是对外演示素材，也是回归基线 —— 以后改东西崩了一对照视频立刻知道。
> **不录音**：旁白用后期字幕，避免重录成本。

---

## 录前 Checklist（约 15 分钟）

### 1. 网络环境 ⚠️ 关键

- [ ] **关闭 Clash / 或加 DIRECT 例外**
   - 简单粗暴：菜单栏 Clash → "退出"
   - 优雅做法：Clash 规则里加 `DOMAIN-SUFFIX,googleapis.com,DIRECT` 和 `DOMAIN-SUFFIX,earthengine.com,DIRECT`
   - 不做的后果：动作 #5 的 Landsat tile 全空白（`net::ERR_ABORTED`），后端 GEE OAuth 也会断
- [ ] **确认能 ping 通 googleapis.com**：`curl -sf https://earthengine.googleapis.com/`（应返回 401 而不是 SSL 错误）

### 2. 服务启动顺序

按以下顺序起，每步等上一步就绪再下一步：

```bash
# 终端 1：Postgres（已经是 brew services 跑就跳过）
brew services start postgresql@16
psql -U sandbelt -d sandbelt_db -c "SELECT 1" # 检查能连

# 终端 2：Redis
redis-server --daemonize yes --save '' --appendonly no
redis-cli ping   # 应返回 PONG

# 终端 3：后端（必须 unset proxy，否则 GEE OAuth 断）
conda activate sandbelt
cd backend
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
uvicorn app.main:app --port 8000

# 终端 4：前端
cd frontend && npm run dev
```

健康检查：

```bash
curl -sf --noproxy localhost http://localhost:8000/health    # {"status":"ok"}
curl -sf --noproxy localhost http://localhost:3000           # HTML
```

### 3. 预热缓存 ⚠️ 关键

Prophet 第一次 fit 慢（约 3–5 秒），如果录制时撞上首次 fit，观众会看到一段"转圈"。提前调用让 Redis 缓存住：

```bash
# 科尔沁 + 浑善达克的预测，horizon=12（半年，前端默认）
curl -sf --noproxy localhost "http://localhost:8000/api/v1/prediction/ndvi-forecast?region_id=1&horizon=12" >/dev/null
curl -sf --noproxy localhost "http://localhost:8000/api/v1/prediction/ndvi-forecast?region_id=2&horizon=12" >/dev/null

# 情景默认（科尔沁 + 浑善达克的 baseline 拉取）
curl -sf --noproxy localhost "http://localhost:8000/api/v1/prediction/scenario-defaults?region_id=1" >/dev/null
curl -sf --noproxy localhost "http://localhost:8000/api/v1/prediction/scenario-defaults?region_id=2" >/dev/null

# Landsat tile URL（让 GEE OAuth 先 refresh 一次）
curl -sf --noproxy localhost "http://localhost:8000/api/v1/basemap/landsat?year=2015" >/dev/null
curl -sf --noproxy localhost "http://localhost:8000/api/v1/basemap/landsat?year=2024" >/dev/null
```

Redis 缓存 30 分钟，所以热完就别拖太久。

### 4. LLM 端可用性 ⚠️ 关键

`.env` 里的 LLM 配置当前指向**已下线**的 uni-api `qwen3:235b`。录视频前必须切到能用的：

```bash
# 测一下当前 LLM 通不通
curl -sf --noproxy localhost -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"你好","region":"horqin"}' | head -c 200
# 如果出现 "Error code: 422 - 模型已下线"，必须先换 endpoint
```

**降级方案**：如果实在没现成的可用 LLM，**跳过动作 #4**，视频只演 1/2/3/5 四段；脚本里 #4 那 30 秒用静态截图（已有的历史对话 `02_chat_caragana.png`）+ 字幕说明。

### 5. 浏览器设置

- [ ] **关 macOS 通知**：勿扰模式开（控制中心 → 勿扰）
- [ ] **关 Slack/微信/邮件**等会弹通知的 app
- [ ] **Chrome 全屏**：Cmd+Ctrl+F
- [ ] **DevTools 关掉**：F12 / Cmd+Opt+I
- [ ] **清浏览器缓存**（可选）：让 OSM 地图瓦片重新加载更真实，但代价是录制中前几秒地图灰

---

## 录制设置

| 项 | 推荐 |
|---|---|
| 工具 | **QuickTime Player**（macOS 自带）或 **OBS** |
| 快捷键 | `Cmd+Shift+5` → 选"录制所选部分" → 框选浏览器窗口 |
| 分辨率 | 1080p（1920×1080）足够；2K/4K 文件大且没必要 |
| 帧率 | 30 fps |
| 鼠标点击效果 | QuickTime 选项里勾"在录制中显示鼠标点击"（让观众看清你点了哪里） |
| 音频 | **不录**，后期加字幕 |
| 时长目标 | **2 分 30 秒 ± 30 秒** |

---

## 录制脚本（5 段 × 约 30 秒）

每段下面是 **操作动作** + **字幕草稿**（后期叠在视频上）。

### 段 1 · 0:00–0:30 双沙地全景

**动作**：
1. 浏览器打开 `http://localhost:3000/dashboard`
2. 等页面完全加载（地图 + 状态栏 + 红色预警条）
3. 鼠标缓慢滑过顶部 4 个 KPI（监测区域 / 监测面积 / 时序跨度 / 数据集）
4. 鼠标停在 L4 极高风险卡上 1 秒

**字幕草稿**：
> SandbeltOS 三北防护林智慧决策支持系统
> 当前监测：科尔沁 + 浑善达克两大沙地，共 24,143 km²
> 综合风险等级：L4 极高 — 红色预警条显示最新 10 条告警

### 段 2 · 0:30–1:00 单沙地 + NDVI + 预测

**动作**：
1. 点击顶部"科尔沁沙地"按钮
2. 等单视图加载（地图 + 4 个指标卡 + 时序图）
3. 鼠标停在 NDVI 时序图右侧延伸的**虚线 + 浅绿置信带**上
4. 鼠标向右扫到图的最右端（2025 中）

**字幕草稿**：
> 进入科尔沁单沙地视图：NDVI / FVC / 碳密度 / 风险等级 四项指标
> 蓝色实线：2020–2024 历史 NDVI 观测
> **绿色虚线 + 浅绿带：Prophet 半年期预测（12 × 16 天）**
> 右下角"演示数据"角标：当前为合成数据基线

> **注**：预测值约 0.03–0.05（冬季外推），虚线在图底部，鼠标停留时高亮便于观众看到。

### 段 3 · 1:00–1:40 情景剧变（柠条 vs 杨树）

**动作**：
1. 滚到"造林情景 SCENARIO LAB"卡
2. 默认是 **柠条 600/ha 5 年** —— 鼠标停在结果区"高风险"和中文建议上 2 秒
3. 切换树种下拉到 **杨树 · 年耗水 ~750 mm**
4. 把"增加密度"滑块从 600 拖到 **2000**
5. 把"投影年限"滑块从 5 拖到 **5**（保持）
6. 等右侧多年趋势图刷新，鼠标停在"极高风险"红色标签上
7. 鼠标移到中文推荐文本上 2 秒

**字幕草稿**：
> 造林情景实验室：6 种树种 × 密度 × 投影年限
> **柠条 600 株/公顷 / 5 年** → 高风险（土壤水分接近极限）
> 切换：**杨树 2000 株/公顷** → 极高风险，水分赤字 1386 mm/年
> 模型基于年降水 380 mm / 风速 5.7 m/s 的真实区域基线
> 中文决策建议自动生成：建议密度 ≤ 300 株/公顷或改用抗旱树种

### 段 4 · 1:40–2:10 RAG 流式问答

> ⚠️ 录前必须确认 LLM 端通（见 Checklist §4）

**动作**：
1. 点顶部"智能助手"链接，进 `/chat`
2. 看到"新对话"页 + 6 个预设快捷问题
3. 点击 **"风险评估"**（科尔沁现在风险等级如何？）
4. 等 SSE 流式 token 逐字出现 —— **不要快进**，观众看到打字机效果才有"真在调 LLM"的感觉
5. 等回答出完，鼠标滑到引用编号 [1] / [4]，停留 1 秒
6. 镜头扫右侧"引用来源"面板（5 条 PDF + page + score）和"实时指标"（NDVI / 风险 / 风速 / 土壤）

**字幕草稿**：
> RAG 智慧问答：bge-m3 + 重排 + 磐石大模型
> 预设 6 个快捷问题，分"风险&趋势 / 方法论 / 实务决策"
> 流式 SSE：回答逐字出现
> 右侧自动展开：5 条文献引用（含页码 + 相似度）+ 当前区域实时指标

**LLM 不可用降级**：跳到段 5，最后字幕加一行 "RAG 模块演示见 docs/demos/02_chat_caragana.png"。

### 段 5 · 2:10–2:40 Landsat 时空对比

**动作**：
1. 顶部回点"科尔沁沙地"
2. 地图右上角点 **"对比 Compare"** 按钮
3. 等 Landsat 底图加载（约 3–5 秒，瓦片从 GEE 拉）
4. 拖动中间的 **swipe 分割线**：从左拖到右、再拖回中间
5. 在右下角"对比前 / 对比后"下拉切年份：把"对比前"从 2015 改到 **1990**，让差距更醒目
6. 再拖一次 swipe

**字幕草稿**：
> Landsat 历史对比：1990–2025 任选两年
> 默认 **2015 vs 2024**：可拖动中间 swipe 对比同位置植被差异
> 切到 **1990 vs 2024**：30+ 年治沙成效一目了然
> 数据：USGS Landsat Collection 2 L2，经 GEE 服务端合成

---

## 录制小贴士

| 习惯 | 原因 |
|---|---|
| 操作放慢，每一步停 1–2 秒 | 字幕加进去要时间，给观众读 |
| 不要快速来回切沙地按钮 | 每次切换都触发 4–6 个 API，频繁切会让网络面板"忙乱" |
| 鼠标轨迹要"指向意图" | 移动→停留→点击，而不是乱飘 |
| 录两遍 | 第一遍找节奏感，第二遍正式录；中间发现 bug 现修 |
| 录前 deep breath | 紧张会手抖鼠标乱飞 |

---

## 后期处理（约 30 分钟）

1. **导入 iMovie / ScreenFlow / Final Cut**
2. **剪掉录制开头/结尾**多余的 1–2 秒
3. **加字幕**：用上面"字幕草稿"，每段字幕展示 5–8 秒
   - iMovie：标题 → 选"中下方" → 拖到时间轴对应段
4. **加段落标题卡**（可选）：每段开头用 1.5 秒纯色标题
   - "Part 1 / 5 — Combined View" 之类
5. **导出 1080p MP4**，目标文件 < 30 MB
6. **存到** `docs/demos/SandbeltOS_baseline_2026-05-18.mp4`（按需提交 git，或上传到外部链接，README 加跳转）

---

## 失败 fallback

| 录到一半发现 | 怎么办 |
|---|---|
| LLM 突然 422 | 段 4 跳过，重录从段 5 开始；字幕里说明 "RAG 详见 02_chat_caragana.png" |
| Landsat tile 转圈 | 检查 Clash 是否又开了 / 重启后端 + 重新预热 |
| Prophet 转圈很久 | 录制中断，去终端 `redis-cli flushall && [再跑预热]`，重录 |
| 浏览器弹通知 | 立刻 esc 关，剪辑时剪掉那 1 秒 |
| 字幕来不及打 | 录视频时鼠标轨迹放慢就行，字幕长度由你后期决定 |

---

## 录完后必做

- [ ] 视频里**没出现**密码 / token / `secrets/` 路径
- [ ] 视频里**没出现**其他敏感页面（聊天软件、邮箱、密码管理器）
- [ ] 文件命名带日期：`SandbeltOS_baseline_2026-05-18.mp4`
- [ ] 更新 `docs/test-status.md` 里"下一里程碑"那段，把 "录 demo 视频" 划掉
- [ ] commit 视频或外链：commit 时 LFS / 或写 README 指向

---

*版本：v1 | 拟稿日期：2026-05-18 | 配套基线 commit：f2f18d4*
