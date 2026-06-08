# testLLM

检测 LLM API 中转商是否真正提供了它声称的模型。

部分 API 中转商或代理商声称提供高端模型（如 GPT-4o），实际上却偷偷将请求转发到更廉价的替代模型。**testLLM** 通过运行一系列探测探针，从行为、元数据、能力等多个维度对目标 API 进行测试，最终汇总为加权评分和判定结论。

## 工作原理

testLLM 运行 11 个探测探针，每个探针产出一个置信度分数（0–1），表示目标 API 提供的是所声称模型的概率。结果按可配置的权重聚合，最终给出判定结论：

| 判定结论 | 含义 |
|---------|------|
| LIKELY CORRECT | 高置信度，声称的模型很可能是真实的 |
| UNCERTAIN | 信号不一致，需要人工审查 |
| HIGH RISK | 强烈证据表明提供商**没有**提供所声称的模型 |

### 探测探针

| 探针 | 权重 | 测试内容 |
|------|------|---------|
| `system_prompt_leak` | 0.35 | 通过 Responses API 提取系统提示词中的真实模型身份 |
| `logprobs` | 0.25 | 分析 token 概率分布（模型特有） |
| `reasoning` | 0.20 | 测试数学、逻辑和编程能力，与已知答案对比 |
| `context_window` | 0.20 | 二分搜索估算实际上下文窗口大小（消耗较大） |
| `knowledge_cutoff` | 0.15 | 知识边界问题，与参考数据对比 |
| `multimodal` | 0.10 | 视觉/音频能力检测 |
| `special_triggers` | 0.10 | 已知的模型特定行为触发器 |
| `self_report` | 0.10 | 让模型自我报告身份（容易被伪造） |
| `api_metadata` | 0.05 | 检查 API 响应中的 `model` 字段 |
| `api_models` | 0.05 | 查询 `/models` 端点 |
| `style_fingerprint` | 0.05 | 分析输出格式特征 |

## 环境要求

- Python 3.10+
- `httpx`
- `pyyaml`
- `rich`

## 安装

```bash
pip install httpx pyyaml rich
```

## 使用方法

```bash
# 基本用法
python detect.py --base-url https://api.openai.com --api-key sk-xxx --model gpt-4o

# 测试中转商
python detect.py --base-url https://proxy.example.com/v1 --api-key sk-xxx --model gpt-4o

# 只运行指定探针
python detect.py --base-url https://api.openai.com --api-key sk-xxx --model gpt-4o \
  --probes self_report,api_metadata,reasoning

# 跳过消耗较大的探针（如 context_window）
python detect.py --base-url https://api.openai.com --api-key sk-xxx --model gpt-4o \
  --skip-expensive

# 强制指定协议（默认自动检测）
python detect.py --base-url https://api.openai.com --api-key sk-xxx --model gpt-4o \
  --wire-api chat_completions

# 列出可用的参考模型
python detect.py --list-models
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--base-url` | API 端点 URL | （必填） |
| `--api-key` | API 密钥 | （必填） |
| `--model` | 声称的模型名称（如 `gpt-4o`） | （必填） |
| `--probes` | 逗号分隔的探针名称，只运行指定探针 | 全部 |
| `--skip-expensive` | 跳过消耗较大的探针（如 `context_window`） | 关闭 |
| `--timeout` | API 超时时间（秒） | 60 |
| `--wire-api` | 强制指定 `chat_completions` 或 `responses` | 自动检测 |
| `--list-models` | 列出参考模型后退出 | - |

## 项目结构

```
detect.py                    # 命令行入口
client.py                    # 异步 HTTP 客户端（httpx）
config.py                    # 配置与探针权重
scoring.py                   # 加权聚合与判定逻辑
report.py                    # 终端报告输出（rich）
probes/
  base.py                    # BaseProbe 抽象类与注册机制
  self_report.py             # 模型自我身份报告
  api_metadata.py            # API 响应元数据检查
  api_models.py              # /models 端点探测
  system_prompt_leak.py      # 系统提示词提取
  knowledge_cutoff.py        # 知识边界问题
  reasoning.py               # 数学/逻辑/编程测试
  style_fingerprint.py       # 输出格式分析
  context_window.py          # 上下文窗口估算
  logprobs.py                # token 概率分析
  multimodal.py              # 视觉/音频能力测试
  special_triggers.py        # 模型特定触发器
reference/
  loader.py                  # YAML 参考文件加载器
  models/
    gpt-4o.yaml              # GPT-4o 参考配置
    gpt-5.5.yaml             # GPT-5.5 参考配置
```

## 添加参考模型

在 `reference/models/` 下创建 YAML 文件（如 `claude-3-opus.yaml`）：

```yaml
knowledge_cutoff: "2024-04"
reasoning:
  - prompt: "What is 17 * 23?"
    expected: "391"
context_window:
  expected_tokens: 200000
style:
  code_fence: "```"
  uses_headers: true
multimodal:
  vision: true
  audio: false
```

## 添加自定义探针

1. 在 `probes/` 下创建新文件（如 `my_probe.py`）。
2. 定义一个继承 `BaseProbe` 的类，实现 `async def run(self, client, config) -> ProbeResult`。
3. 使用 `@register_probe` 装饰器注册。
4. 在 `probes/__init__.py` 中添加 import。

## 许可证

MIT
