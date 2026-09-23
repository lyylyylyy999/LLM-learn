# TASK-009 — FastAPI 对话分析接口

- **难度：** L2
- **预计有效编码时间：** 60–90 分钟
- **开发分支：** `develop`
- **状态：** 进行中
- **任务设计基线：** `d7043b4`
- **实现审查基线：** 本任务说明提交

## 背景

TASK-007 已经提供了经过验证的结构化对话分析结果，但它目前只能作为 Python 函数调用。真实应用还需要一个稳定的 HTTP 边界：接收 JSON 请求、验证输入、返回明确的响应结构，并把模型层的预期失败转换成客户端能够处理的 HTTP 错误。

本任务只实现一个最小 FastAPI 接口，把已有分析能力暴露为 HTTP API。重点是理解请求模型、响应模型、同步依赖注入和异常到状态码的映射，不在第一步同时加入服务启动配置、异步、数据库或真实模型调用。

## 学习目标

完成后，学习者应该能够：

- [ ] 解释 HTTP 请求体、响应体和状态码各自承担的接口契约。
- [ ] 使用 FastAPI 和 Pydantic 定义并公开请求、成功响应和错误响应。
- [ ] 使用窄接口注入已有分析能力，使 HTTP 层不依赖真实模型或环境变量。
- [ ] 说明请求验证失败与上游模型失败为什么需要不同的 HTTP 行为。

## 前置知识

- 阅读 FastAPI 官方文档的 [Request Body](https://fastapi.tiangolo.com/tutorial/body/)，重点理解 Pydantic 模型如何成为请求体和 OpenAPI Schema。
- 阅读 [Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)，只需理解“业务依赖可以被替换”这一目的；本任务使用应用工厂参数完成最小依赖注入。
- 阅读 [Handling Errors](https://fastapi.tiangolo.com/tutorial/handling-errors/)，重点理解 `HTTPException` 和状态码。
- 复习 TASK-007 的 `AnalysisResponse`、`LLMError` 和 `StructuredOutputError`。

开始编码前先回答：请求 JSON 不合法、请求合法但模型未完成响应、服务器出现未知编程错误，这三类失败是否应该返回同一种状态和内容？

## 功能要求

### 1. 项目结构与依赖

- 生产代码放在 `exercises/task_009_fastapi_analysis/`。
- 在 `requirements.txt` 中直接声明 FastAPI 运行时依赖。
- 本任务暂不安装或配置 Uvicorn，不要求启动监听端口的服务器进程。
- 不修改 TASK-007 的公开行为；直接复用它的 `AnalysisResponse`、`LLMError` 和 `StructuredOutputError`。

### 2. 可替换的分析依赖

定义一个窄的同步可调用接口：接收一段对话字符串，返回 TASK-007 的 `AnalysisResponse`。

提供公开应用工厂 `create_app(analyzer) -> FastAPI`：

- `analyzer` 使用上述窄接口，而不是直接接收 OpenAI 客户端。
- 路由通过注入的 `analyzer` 完成分析。
- 创建应用或导入模块时不得读取 API Key、创建真实模型客户端或访问网络。
- 同一个合法请求只调用一次 `analyzer`。

### 3. 请求与成功响应

提供 `POST /analyses`：

- 请求 JSON 只有一个字段 `conversation`。
- `conversation` 必须是去除首尾空白后仍非空的字符串。
- 拒绝额外字段。
- 路由使用普通同步 `def`，与当前同步分析依赖保持一致。
- 成功时返回 `200 OK`。
- 使用明确的 Pydantic 响应模型，完整保留 `AnalysisResponse` 中的分析结果、响应 ID、模型名、可空 token 用量和耗时。
- 响应 Schema 必须出现在 FastAPI 生成的 OpenAPI 文档中。

### 4. 错误映射

错误响应采用稳定结构，至少包含机器可读的 `code` 和适合客户端展示的通用 `message`。

| 条件 | HTTP 状态 | `code` |
| --- | --- | --- |
| 请求缺失字段、类型错误、纯空白或包含额外字段 | FastAPI 默认 `422` | 使用框架默认验证响应 |
| `analyzer` 抛出 `LLMError` | `502 Bad Gateway` | `llm_response_error` |
| `analyzer` 抛出 `StructuredOutputError` | `502 Bad Gateway` | `structured_output_error` |

- 两种 `502` 响应不得包含原异常文本、原始对话、API Key 或模型原始输出。
- 不捕获所有 `Exception` 并伪装成上述两种已知错误；未知缺陷应保持可观察。

## 约束

- 不调用真实 DeepSeek API，不新增真实模型冒烟测试。
- 不实现 Uvicorn 启动脚本、配置加载、全局模型客户端或默认生产 `app`。
- 不实现健康检查、鉴权、限流、重试、缓存、数据库、任务队列或流式响应。
- 不把同步模型调用放进 `async def` 路由。
- 不引入 LangChain、LlamaIndex、ORM 或额外 Web 框架。
- 不复制或重新定义 TASK-007 的领域结果模型；API 请求/响应模型可以独立定义，以表达 HTTP 契约。
- 不为测试修改 TASK-007 的实现。

## 验收标准

- [ ] 应用能够通过注入的本地假分析函数创建，导入和创建过程不访问网络。
- [ ] 合法请求调用分析依赖一次，并返回与领域结果一致的 `200` JSON。
- [ ] 缺失、类型错误、纯空白和额外字段由请求模型拒绝，分析依赖不会被调用。
- [ ] 两种已知模型层异常分别返回规定的安全 `502` 响应。
- [ ] 未知异常没有被错误映射成已知模型失败。
- [ ] `/analyses` 的请求和成功响应 Schema 出现在 OpenAPI 中。
- [ ] 全量 pytest、Ruff 和 mypy 检查通过。

## 测试要求

本任务执行 AGENTS.md 中从 TASK-009 开始的测试协作模式：

1. 学习者先只实现生产代码并完成基本手动验证。
2. 学习者明确通知“生产代码已完成，请编写测试”。
3. 导师添加 `tests/test_task_009/` 下的测试，并在需要时把 FastAPI `TestClient` 所需的 `httpx` 作为直接开发依赖加入 `requirements-dev.txt`；现有 `httpx2` 不因此删除。
4. 学习者审阅测试，并负责修复测试暴露的生产代码缺陷；导师负责修复测试自身缺陷。

导师编写的离线测试至少覆盖：

- [ ] 正常请求的状态码、完整响应和依赖调用参数。
- [ ] 缺失字段、错误类型、纯空白和额外字段，并确认依赖未被调用。
- [ ] 可空 token 用量能够按合同返回。
- [ ] `LLMError` 和 `StructuredOutputError` 的状态码、错误码及脱敏。
- [ ] 未知异常没有被误分类。
- [ ] OpenAPI 中存在规定路径、请求模型和成功响应模型。

最终至少实际运行并记录：

```text
python -m pytest
python -m ruff check .
python -m mypy exercises tests
```

## 边界情况

- `conversation` 缺失、为 `null`、不是字符串、为空字符串或只含空白。
- 请求包含未声明字段。
- token 用量全部为 `None`。
- 分析结果中 `action_items` 为空列表。
- 已知模型异常的原始消息包含类似密钥或完整对话的敏感标记。
- 注入的依赖抛出未预期异常。

## 进阶任务

- 使用 FastAPI `Depends` 和依赖覆盖机制管理分析服务。
- 增加环境配置和 Uvicorn 启动入口，连接真实 DeepSeek 客户端。
- 把模型超时与一般上游错误映射成不同 HTTP 状态。

进阶任务不属于本次完成条件，不应在基础任务完成前实现。

## 完成定义

- [ ] 功能要求、约束和验收标准全部满足。
- [ ] 学习者已审阅导师编写的测试，并能解释关键测试的保护目标、替身边界和失败原因。
- [ ] 默认离线测试、Ruff 和 mypy 检查通过，实际命令与结果已记录。
- [ ] 已检查本任务说明提交到当前状态的完整差异以及所有未提交修改。
- [ ] 没有未处理的严重问题；主要问题已修复或记录接受风险的理由。
- [ ] 代码通过最终审查，导师提出的 3–5 个针对性问题已准确回答。
- [ ] 已获得建议提交信息；是否提交和推送由学习者决定。
- [ ] 已按 L2 简版模板共同完成任务复盘，且没有遗留模板占位内容。
