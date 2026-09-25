# MetroCount · 上海地铁计价系统

基于 Django + SQLite 的上海地铁票价查询系统。内置**全网拓扑线路图**（仿百度地图网页版绘制），支持点击站点选站、最短路径计费、换乘方案、机场线/磁悬浮备选与可视化高亮。

## 功能特性

- **全屏分栏布局**：页面撑满浏览器视口、无整页滚动；左侧为线路图（高度撑满、按纵横比自适应），右侧自上而下为搜索/起终点选择、票价结果（独立滚动）与线路图例；窗口宽度 ≤960px 时自动回退为单列纵向布局。
- **整网线路图**：21 条运营线路折线 + 526 个站点标记，按百度地图网页版拓扑布局重绘（`shmetro-map.svg` 内联渲染）。默认整图自适应窗口，按缩放密度分级显示：整图仅显示 9 个门户级枢纽名与 39 枚线路编号徽章，放大后依次显示全部换乘站名、全部站名；站名沿线路上下错位并经碰撞避让排层，支持滚轮缩放、＋/－/全图按钮与双击还原。
- **点击选站**：在地图上点击站点，第一次点击设为起点、第二次点击设为终点，第三次点击自动重置为新起点，点击非站点位置清空选择；选中站点高亮显示，地图选站与下拉选择双向同步。
- **票价查询**：起点 → 终点最短里程计费，显示票价、里程、预计时间、换乘次数与分段乘坐方案；乘坐方案按线路分段着色，换乘站白环高亮，方案外路径虚化。
- **机场线备选**：涉及机场的行程，折叠提供"市域机场线"更快备选（默认不展开）；**仅机场线站点**（景洪路/三林南/康桥东/上海国际旅游度假区）作为起终点时机场线作为主方案。
- **磁悬浮备选**：涉及浦东机场方向的行程，折叠提供"磁悬浮（龙阳路—浦东机场）"更快备选，按地铁+磁悬浮分段计价（磁悬浮 50 元）。
- **二级选择**：起点/终点按"线路 → 站点"二级目录选择，换乘站注明可换乘线路；附站名搜索。
- **安全加固**：API 参数校验、前端输出转义、路径回溯防死循环、DB 查询缓存、生产模式安全头。

## 技术栈

- 后端：Django 5 + SQLite
- 前端：原生 HTML / CSS / JavaScript，内联 SVG 地图
- 数据：526 个站点 / 22 条线路记录（21 条运营线 + 虚拟换乘线）/ 646 条边（含 140 条同站换乘边）/ 实测站间距 / 官方票价规则

## 目录结构

```
metrocount/
├── manage.py                  # Django 管理入口
├── requirements.txt
├── README.md
├── metrocount/                # 项目配置（settings / urls / wsgi）
├── subway/                    # 应用：models / views / urls
├── templates/subway/index.html  # 页面模板（含内联 SVG 地图）
├── static/subway/
│   ├── app.js                 # 前端交互：选择、缩放、高亮、搜索
│   ├── style.css
│   └── maps/shmetro-map.svg   # 整网 SVG 地图源文件
├── gen_baidu_map.py           # SVG 地图生成器（改图运行此脚本；含标签碰撞避让、线路徽章）
├── inline_svg.py              # 将 SVG 重新内联进 index.html
├── fix_network.py             # 网络数据幂等修复（清除异名幽灵换乘边，可重复运行）
├── baidu_paths.json           # 百度地图线路 path 数据
├── baidu_stations.json        # 百度地图站点标记数据
├── line_distances.json        # 官方站间距数据
├── station_gaps_raw.json      # 站间距原始数据
├── import_stations.py         # 站点数据入库脚本
├── import_edges.py            # 边（站间距）入库脚本
├── assign_path_lines.py       # 线路边归属整理脚本
├── apply_gaps.py              # 站间距更新脚本
├── add_maglev.py              # 磁悬浮线路数据导入脚本（幂等）
├── verify_airport.py          # 机场线票价基线回归测试
├── verify_alternatives.py     # 全站备选路径回归测试（5551 OD / 1859 备选）
├── sample_routes.py           # 抽样 OD 方案检查工具
└── smoke_test.py              # 关键 OD 与安全项冒烟测试
```

## 启动运行

```powershell
cd D:\metrocount
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

浏览器访问 <http://127.0.0.1:8000/>。

> 注意：修改 `templates/`、`subway/views.py` 后需重启服务器；修改静态文件（`app.js`、`style.css`）后需同步更新 `index.html` 中对应的 `?v=` 缓存版本号。

### 安全环境变量（生产部署时）

| 变量 | 默认 | 说明 |
|---|---|---|
| `METROCOUNT_SECRET_KEY` | 本地开发密钥 | 生产必须注入随机密钥 |
| `METROCOUNT_DEBUG` | `1`（开发模式） | 生产设 `0`：自动开启 HTTPS 重定向、安全 Cookie、HSTS 等 |

## 票价规则

- **普通计价**：按最短乘坐里程计费，6 km 以内 3 元，超出部分每 10 km 加 1 元（`3 + ceil((km - 6) / 10)`）。
- **市域机场线**：7 站（虹桥2号航站楼 — 浦东1号2号航站楼）按官方站间票价表计价（4/7/9/11/14/15/17/20/24/26 元）；跨线行程按"机场线段查表 + 普通段连续计价"合并计算，最低 4 元。
- **磁悬浮**：龙阳路—浦东机场单程 50 元，约 8 分钟；作为机场方向行程的**折叠备选**（默认不展开），跨线行程按"普通段计价 + 磁悬浮 50 元"计算。
- **同站换乘**：同一物理站点不同线路（如虹桥2号航站楼机场线站 ↔ 2号线站）无实际乘车，票价按 0 元处理。
- **路径规划**：以乘坐里程为第一权重求最短路径计价，以时间为第二权重求最快方案用于展示换乘信息；换乘步行惩罚中途 8 分钟，起点同站组 0 分钟（进站直接选站台）、终点同站组 3 分钟；机场线/磁悬浮备选各自独立计算，仅当快于主方案时展示；磁悬浮备选剔除起终点同侧的回环路径（出口段重走入口段时回溯链会断裂）。

## 回归测试

服务器运行后执行：

```powershell
.\.venv\Scripts\python.exe verify_airport.py       # 机场线 21 项 + 普通 7 锚点
.\.venv\Scripts\python.exe verify_alternatives.py  # 全站 5551 OD / 1859 备选
.\.venv\Scripts\python.exe smoke_test.py           # 关键 OD + 安全项冒烟
```

## 地图再生成

修改线路颜色、站名字号、站点尺寸、标签布局等视觉参数后：

```powershell
.\.venv\Scripts\python.exe gen_baidu_map.py   # 重新生成 static/subway/maps/shmetro-map.svg
.\.venv\Scripts\python.exe inline_svg.py      # 重新内联进 templates/subway/index.html
```

生成器要点：

- 站点圆点与标签均带 `data-name`/`data-color`，供前端点击选站与高亮；线路徽章容器设 `pointer-events:none`，不拦截点击。
- 标签统一收集后按"门户枢纽 > 换乘站 > 普通站、长名优先"贪心排层：沿线路上下各 3 层错位并做矩形碰撞检测，虹桥两场站等物理相邻点由 `MANUAL_DY` 手工错位。
- 门户级枢纽（≥4 线换乘站 + 虹桥/上海站/上海南站/人民广场等城市门户）带 `lbl-hub-major`，整图档仅显示这些站名；密度档位由 `app.js` 按屏幕缩放写 `data-density`（low/mid/high）与 CSS 变量控制。
- 改完生成链后需同步 `app.js` 内 viewBox 兜底常量、`index.html` 中静态资源 `?v=` 版本号并重启服务。

## 数据来源

- 线路走向与站点位置：百度地图地铁线路图（`map.baidu.com/subways`）SVG 数据
- 站点间实际距离：上海地铁官方站间距（GitHub `ljy1005/shmetro`）
- 票价规则：上海地铁官网票价试行方案；磁悬浮票价/时刻表来自官方公开信息
