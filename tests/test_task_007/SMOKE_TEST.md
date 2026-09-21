## DeepSeek 冒烟测试

真实 API 测试默认关闭，仅在显式设置环境变量后运行。

### 调用命令

PowerShell：

```powershell
$env:DEEPSEEK_API_KEY="<real-key>"
$env:DEEPSEEK_MODEL="deepseek-flash"
$env:RUN_DEEPSEEK_SMOKE="1"

python -m pytest tests/test_task_007/test_structured_analysis.py -m integration -q
```

其中：

* `DEEPSEEK_API_KEY` 通过环境变量提供，不写入源码、测试数据、日志或提交历史。
* `RUN_DEEPSEEK_SMOKE=1` 用于显式开启真实 API 测试。
* `DEEPSEEK_MODEL` 是冒烟测试使用的模型。
* 未设置 `RUN_DEEPSEEK_SMOKE=1` 时，该测试默认跳过。

### 模型配置

```text
provider: DeepSeek
sdk: openai Python SDK
api: Responses API
base_url: https://api.deepseek.com
model: deepseek-flash
max_output_tokens: 2000
```

DeepSeek 官方 Responses API 支持通过 OpenAI Python SDK 调用，`base_url` 为 `https://api.deepseek.com`；当前 Responses API 支持 `deepseek-flash` 和 `deepseek-v4-pro`。本测试使用 `deepseek-flash`。

### 脱敏运行结果

实际运行日期：2026-09-20

```text
--- DeepSeek structured analysis smoke test result ---
model: deepseek-flash
response_id: d82...0d6
input_tokens: 390
output_tokens: 929
total_tokens: 1319
elapsed_seconds: 5.628071
summary_length: 142
key_points_count: 5
action_items_count: 4
```

该记录仅保留验证调用成功所需的运行元数据，不保存真实 API Key、完整输入文本或模型输出文本。
