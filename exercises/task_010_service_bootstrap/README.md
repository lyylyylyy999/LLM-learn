## 本地运行

启动服务前需要配置以下环境变量：

- `DEEPSEEK_API_KEY`：DeepSeek API 密钥，必填且不能为空。示例中只能使用占位文本，例如 `your-deepseek-api-key`。
- `DEEPSEEK_MODEL`：调用的 DeepSeek 模型名称，必填且不能为空。
- `DEEPSEEK_MAX_OUTPUT_TOKENS`：最大输出 token 数，可选；未设置时默认使用 `2000`，必须是整数且不小于 `16`。

PowerShell 示例：

```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-api-key"
$env:DEEPSEEK_MODEL="your-model-name"
$env:DEEPSEEK_MAX_OUTPUT_TOKENS="2000"
```

在仓库根目录使用 Uvicorn 的应用工厂模式启动服务：

```powershell
python -m uvicorn <模块路径>:create_api_app --factory --reload --host 127.0.0.1 --port 8000
```

其中 `<模块路径>` 替换为实际包含 `create_api_app()` 的 Python 模块路径，例如：

```powershell
python -m uvicorn exercises.task_010_service_bootstrap.service_bootstrap:create_api_app --factory --reload --host 127.0.0.1 --port 8000
```

服务仅监听本机 `127.0.0.1`。

启动成功后，可以在浏览器访问：

```text
http://127.0.0.1:8000/docs
```

查看 Swagger UI，或访问：

```text
http://127.0.0.1:8000/openapi.json
```

查看 OpenAPI 描述。

需要测试分析接口时，在 `/docs` 中展开 `POST /analyses`，点击 `Try it out` 并提交请求。不额外增加用于浏览器测试的 GET 分析路由。

例如可以使用一条不包含真实个人信息的合成对话：

```json
{
  "conversation": "用户：项目的数据清洗已经完成，我计划本周完成特征工程，下周开始训练模型。助手：目前有什么风险？用户：缺失值较多，而且需要周五前提交初步结果。"
}
```

`POST /analyses` 会实际调用 DeepSeek API，因此可能产生费用。是否执行真实请求由学习者自行决定；仅查看 `/docs` 或 `/openapi.json` 不需要主动发送分析请求。

如果执行真实调用，只使用一条无敏感信息的合成对话，并在记录运行结果时对密钥等敏感配置进行脱敏。例如：

```text
DEEPSEEK_API_KEY=<redacted>
DEEPSEEK_MODEL=<model>
POST /analyses -> 200 OK
```

不要把真实 API Key 写入文档、日志、截图或 Git 仓库。

停止服务时，在运行 Uvicorn 的终端按：

```text
Ctrl+C
```

结果如下：
```json
{
  "analysis": {
    "summary": "用户汇报项目数据清洗已完成，并说明后续特征工程和模型训练的时间安排；在助手询问风险后，用户指出缺失值较多，且周五前需提交初步结果。",
    "key_points": [
      "数据清洗已经完成。",
      "计划本周完成特征工程，下周开始训练模型。",
      "当前风险是缺失值较多。",
      "周五前需要提交初步结果。"
    ],
    "action_items": [
      "本周完成特征工程。",
      "下周开始训练模型。",
      "周五前提交初步结果。"
    ]
  },
  "response_id": "c2140c8a-d0ac-4b38-95e4-9db8b2f6fd34",
  "model": "deepseek-flash",
  "input_tokens": 372,
  "output_tokens": 819,
  "total_tokens": 1191,
  "elapsed_seconds": 9.296236199996201
}
```