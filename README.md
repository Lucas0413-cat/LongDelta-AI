# LongDelta-AI

长三角经济数据分析智能体

## 功能特性

- **智能对话分析**: 自然语言输入，自动解析地区、年份、指标
- **区域对比分析**: 支持多地区数据对比（江浙沪三省比较）
- **短板识别**: 自动识别经济发展中的短板并给出改进建议
- **图表可视化**: Plotly 图表渲染，支持柱状图、饼图、折线图
- **RAG 知识库**: 集成政策文件检索，增强分析上下文
- **流式响应**: SSE 流式输出，实时显示分析进度
- **Middleware**: 请求日志、敏感词过滤、响应时间统计

## 环境要求

- Python 3.11+
- uv 包管理器
- LLM API (DeepSeek / OpenAI)

## 安装依赖

```bash
uv sync
```

## 配置环境变量

创建 `.env` 文件：

```env
# LLM 配置
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=your_api_key_here
```

## 启动服务

### 1. 启动后端 API

```bash
uv run uvicorn src.api.server:app --reload
```

后端运行在: http://localhost:8000

### 2. 启动前端

```bash
uv run streamlit run app.py
```

前端运行在: http://localhost:8501

## Docker 部署

```bash
# 构建并启动
docker-compose up --build

# 后台运行
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/chat` | POST | 同步对话 |
| `/chat/stream` | POST | 流式对话 (SSE) |

## 示例请求

```bash
# 同步请求
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "分析2023年安徽GDP"}'

# 流式请求
curl -N http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "对比江浙沪三产结构"}'
```

## 演示示例

### 示例 1: 态势分析

```
输入: "分析2023年安徽GDP"
输出:
- GDP 数值和增长率
- 与去年对比
- 综合分析结论
- 短板识别和改进建议
```

### 示例 2: 多地区对比

```
输入: "对比江浙沪三产结构"
输出:
- 三省产业结构数据
- 排名表格
- 对比分析
- 结论和建议
```

### 示例 3: 趋势分析

```
输入: "上海近5年GDP变化趋势"
输出:
- 年度数据表格
- 折线图可视化
- 增长趋势分析
```

## 项目结构

```
LongDelta-AI/
├── pyproject.toml         # uv 依赖配置
├── uv.lock                # 依赖锁定文件
├── data/                  # 数据资产
│   ├── raw/               # 原始数据
│   └── processed/         # 处理后数据
├── src/
│   ├── api/               # FastAPI 接口
│   │   ├── schemas.py     # API 请求/响应 Pydantic 模型
│   │   ├── middleware.py  # 中间件（日志、过滤）
│   │   └── server.py      # 服务入口
│   ├── graph/             # LangGraph 核心逻辑
│   │   ├── state.py       # AgentState 定义
│   │   ├── agent.py       # create_agent 逻辑
│   │   ├── nodes.py       # 自定义节点函数
│   │   └── workflow.py    # 图构建与编译
│   ├── tools/             # 工具定义
│   │   ├── definitions.py # @tool 装饰的函数
│   │   ├── implementation.py # 实际数据处理逻辑
│   │   ├── parse.py       # 自然语言解析
│   │   └── chart.py       # 图表生成
│   ├── rag/               # RAG 知识库
│   │   ├── knowledge_base.py
│   │   └── tool.py
│   └── utils/             # 基础设施
│       ├── llm.py         # init_chat_model 工厂
│       └── config.py      # 环境变量加载
├── app.py                 # Streamlit 前端
├── tests/                 # 测试文件
│   └── test_tools.py      # 单元测试
├── docs/                  # 技术文档
│   ├── api.md             # API 接口文档
│   ├── prompts.md         # Agent 系统提示词
│   └── manual.md          # 用户操作手册
├── Dockerfile
├── docker-compose.yml
└── ruff.toml              # Lint 配置
```

## 测试

```bash
# 运行所有测试
uv run pytest tests/ -v

# 代码检查
uv run ruff check src/
```

## 技术栈

- **后端**: FastAPI + LangGraph + LangChain
- **前端**: Streamlit + Plotly
- **数据**: Pandas + Parquet
- **LLM**: DeepSeek / OpenAI
- **向量库**: Chroma (可选)
- **代码质量**: ruff + pytest
