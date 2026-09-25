# 乐谱反复段展开工具

供排练使用的 Web 应用：逐行输入小节编号与反复记号，系统校验后按嵌套层级
展开出实际演奏的小节顺序，页面展示「演奏序号 / 原小节编号 / 源行号」，
并可下载同内容的 CSV。

技术栈：Python Flask + 原生 HTML/JavaScript，Docker 交付。

## 快速开始

一条命令启动（依赖随容器启动时自动安装）：

```bash
docker compose up --build
```

浏览器访问：**http://localhost:5000**

## 配置

通过环境变量配置（均可省略，使用默认值）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `HOST_PORT` | `5000` | 主机暴露端口，如 `HOST_PORT=8080 docker compose up` 后访问 http://localhost:8080 |
| `PORT` | `5000` | 容器内服务监听端口 |
| `MAX_MEASURES` | `5000` | 展开小节数上限，超过即停止并报错 |

## 输入格式

每行一个小节，语法：`[|:] 小节编号 [:|xN]`

- `|: ` 写在编号**前**：反复起点；
- `:|xN` 写在编号**后**：反复终点，`N` 为反复遍数（2～9）；
- 反复段允许**嵌套**；同一行可同时写起点和终点（如 `|: 5 :|x2`）；
- 空行与 `#` 开头的行会被忽略；兼容全角「｜」「：」「ｘ」。

示例输入：

```
1
|: 2
|: 3
4 :|x2
5 :|x3
6
```

展开结果（共 20 小节）：

```
1, 2, 3, 4, 3, 4, 5,  2, 3, 4, 3, 4, 5,  2, 3, 4, 3, 4, 5,  6
```

## 校验规则

- **格式错误**：定位到具体输入行（如「第 3 行：格式错误：…」），一次报出全部行级错误；
- **起止配对**：反复终点没有匹配的起点、或起点缺少对应终点，均定位到相应行；
- **编号唯一性**：小节编号重复时报错并指出首次出现的行号。

## 展开上限

展开超过 `MAX_MEASURES`（默认 5000）小节时立即停止，并指出导致超限的源行
（正在展开的最内层反复终点所在行；未使用反复时为当前小节行）。

## CSV 下载

展开成功后点击「下载 CSV」，内容与页面表格完全一致
（列：演奏序号、原小节编号、源行号；UTF-8 带 BOM，Excel 可直接打开）。

## HTTP API

- `POST /api/expand` — 请求体 `{"input": "..."}`，返回展开结果或行级错误 JSON；
- `POST /api/csv` — 请求体同上，成功时返回 CSV 文件下载，失败时返回错误 JSON。

```bash
curl -X POST http://localhost:5000/api/expand \
  -H 'Content-Type: application/json' \
  -d '{"input": "1\n|: 2\n3 :|x2"}'
```

## 本地开发与测试

```bash
pip install -r requirements.txt
python app.py                 # 开发模式启动，访问 http://localhost:5000
python -m unittest discover -s tests -v   # 运行测试
```

## 项目结构

```
├── app.py               # Flask 入口与 API
├── repeat_expand.py     # 解析、校验、嵌套展开核心逻辑
├── static/              # 前端页面（原生 HTML/JS/CSS）
├── tests/               # 单元测试与接口测试
├── requirements.txt     # Python 依赖
├── Dockerfile           # 镜像构建（python:3.12-slim）
├── entrypoint.sh        # 容器启动时安装依赖并启动 gunicorn
└── docker-compose.yml   # 一键启动
```
