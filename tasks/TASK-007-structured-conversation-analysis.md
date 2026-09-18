# TASK-007 — 结构化 LLM 对话分析

- **难度：** L2
- **预计有效编码时间：** 120–180 分钟
- **开发分支：** `develop`
- **状态：** 进行中
- **任务设计基线：** `b140e0f`
- **实现审查基线：** 本任务说明提交；开始编码前记录其提交哈希

## 背景

TASK-006 已经能够安全、可测试地调用 DeepSeek 并返回自由文本摘要。但后端、数据库和评测代码不能可靠依赖模型的自然语言措辞；它们需要字段明确、类型稳定、能够验证的结果。

本任务把自由文本摘要升级为结构化对话分析：由 Pydantic 定义唯一的数据契约，将其 JSON Schema 交给 DeepSeek Responses API，并在本地再次验证模型输出。重点不是增加更多字段，而是理解“请求约束、模型输出、本地验证和错误分类”这条完整边界。

## 学习目标

完成后，学习者应该能够：

- [ ] 解释 JSON、JSON Schema 和 Pydantic 模型分别解决什么问题，以及为什么服务端结构化输出后仍需本地验证。
- [ ] 从 Pydantic 模型生成 JSON Schema，并通过 DeepSeek Responses API 的 `text.format` 请求结构化输出。
- [ ] 区分模型请求失败、非完成响应、空输出和 JSON/Schema 验证失败，并保留有价值的原始异常链。
- [ ] 使用 Mock 完成默认离线测试，并通过一次受控的真实请求验证最终集成。

## 前置知识

- TASK-006 中的客户端注入、单调时钟、usage、日志脱敏和真实冒烟测试边界。
- JSON 对象、数组、字符串、布尔值和缺失字段的基本含义。
- Pydantic `BaseModel`、字段约束、`ConfigDict`、`ValidationError`、`model_json_schema()` 和 `model_validate_json()`。

最少必要阅读：

- [DeepSeek Responses API 参考](https://api-docs.deepseek.com/api/create-response/)：阅读 `text.format` 中 `json_schema`、`name` 和 `schema` 的含义。
- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/)：重点阅读模型验证和 `model_validate_json()`。
- [Pydantic JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/)：重点阅读 `model_json_schema()`。

开始编码前，用一个不超过 10 分钟的小实验确认：Pydantic 模型生成的 Schema 中包含必填字段、数组长度限制以及 `additionalProperties: false`。

## 功能要求

### 1. 项目与依赖

- 实现放在 `exercises/task_007_structured_analysis/`，测试放在 `tests/test_task_007/`。
- 继续使用现有 OpenAI Python SDK 兼容客户端访问 DeepSeek Responses API，不手写 HTTP 请求。
- 代码直接使用 Pydantic，因此必须把 `pydantic` 声明为运行时直接依赖，不能只依赖 `openai` 间接安装它。
- Ruff 和 mypy 作为仓库质量检查命令使用时，也应作为开发直接依赖记录；不要在本任务中引入复杂插件配置。

### 2. 结构化分析契约

使用 Pydantic v2 定义一个对话分析模型，至少包含：

- `summary: str`：非空摘要。
- `key_points: list[str]`：1–5 个非空关键点。
- `action_items: list[str]`：0–5 个非空行动项；没有行动项时返回空列表。

模型必须拒绝额外字段，并拒绝纯空白字符串。字段约束应体现在 Pydantic 验证和生成的 JSON Schema 中，而不是只写在提示词里。

### 3. 请求与结果

提供一个公开的同步分析函数，接收：

- 已构造并指向 DeepSeek `base_url` 的兼容客户端。
- 待分析的对话文本。
- 包含模型名和 `max_output_tokens` 的配置对象。
- 可注入的单调时钟。

函数必须：

- 在请求前拒绝空字符串或纯空白输入，且不得调用客户端。
- 调用 Responses API，并通过 `text.format` 传入 `type="json_schema"`、稳定的 schema 名称和由 Pydantic 生成的 Schema。
- 把稳定规则放入 `instructions`，把原始对话只放入 `input`。
- 仅在响应状态为 `completed` 且 `output_text` 非空时解析结果。
- 使用 Pydantic 从 JSON 文本完成本地验证，不手写重复的字段类型检查。
- 返回结构化分析对象以及 response ID、模型、usage 和耗时等基本元数据。

### 4. 错误边界

- SDK 认证、连接、限流等异常保持原异常向上传播。
- 非 `completed` 状态或空输出继续使用明确的 LLM 响应错误表达。
- JSON 无效、字段缺失、类型错误、额外字段或业务约束失败时，抛出专门的结构化输出异常。
- 结构化输出异常必须使用异常链保留原始 Pydantic `ValidationError`，但异常消息和日志不得包含完整模型输出或原始对话。
- 本任务不实现自动重试、JSON 修复或二次请求；先把失败暴露清楚。

### 5. 日志与安全

- 成功日志记录模型、response ID、token、耗时和结构验证成功状态。
- 失败日志可以记录响应状态或验证失败类别，但不得记录 API Key、原始对话、完整模型输出或完整 Pydantic 输入值。
- 不把真实 Key 写入源码、测试、文档示例或 Git。

### 6. 真实冒烟测试

- 增加默认跳过的 DeepSeek 结构化输出冒烟测试；只有显式开关、`DEEPSEEK_API_KEY` 和 `DEEPSEEK_MODEL` 均存在时才运行。
- 使用公开的合成对话，验证返回值通过 Pydantic 契约；不要断言固定摘要措辞。
- 记录实际命令、最终模型配置和脱敏结果摘要。实现或测试发生影响请求结构的变化后，旧记录不再视为最终证据。

## 约束

- 不引入 LangChain、LlamaIndex、Agent 框架或 Provider 抽象层。
- 不使用仅靠提示词要求 JSON 的方案；必须使用 Responses API 的 JSON Schema 输出格式。
- 不维护一份与 Pydantic 模型分离的手写 Schema。
- 不实现评测集、重试修复链、流式输出、FastAPI 或数据库集成。
- 保留 TASK-006 的现有公开行为和测试，不为完成本任务破坏旧接口。

## 验收标准

- [ ] Pydantic 模型能接受合法结果，并拒绝缺失字段、错误类型、额外字段、空白文本和越界数组。
- [ ] 请求中的 JSON Schema 来自 Pydantic 模型，并通过 DeepSeek Responses API 的 `text.format` 发送。
- [ ] 合法响应映射为结构化结果和完整元数据。
- [ ] SDK 异常、响应状态错误、空输出和 Schema 验证错误具有可区分的行为。
- [ ] 日志包含必要元数据且不泄露 Key、对话或模型原始输出。
- [ ] 默认测试完全离线，并至少有一次基于最终实现的真实 DeepSeek 结构化输出验证记录。
- [ ] 全量 pytest、Ruff 和 mypy 检查通过。

## 测试要求

至少覆盖：

- [ ] Pydantic 模型的合法值和各项边界约束。
- [ ] 正常响应的请求参数、Schema、结构化结果、usage 和耗时。
- [ ] 空输入时客户端和时钟均未调用。
- [ ] 非完成状态与空输出。
- [ ] 无效 JSON，以及有效 JSON 中的缺失字段、错误类型、额外字段和业务约束失败。
- [ ] 结构化输出异常保留原始 `ValidationError` 作为异常链。
- [ ] SDK 异常对象保持原样传播。
- [ ] 成功和失败日志确实产生、包含必要元数据且不包含敏感标记。
- [ ] 真实测试默认跳过；显式开启但缺少 Key 或模型时明确失败。

至少实际运行并记录：

```text
python -m pytest
python -m ruff check .
python -m mypy exercises tests
```

## 边界情况

- 输入是空字符串、空白或换行。
- `output_text` 是空白、截断 JSON 或合法 JSON 但不符合 Schema。
- 列表为空、超过上限或含纯空白元素。
- 模型返回任务未定义的额外字段。
- usage 缺失时仍能返回通过验证的业务结果，token 字段为 `None`。
- 日志和异常不得因验证失败而泄露模型原始输出。

## 进阶任务

- 比较 `json_object` 与 `json_schema` 两种格式的约束强度，并用失败样例说明差异。
- 为结构化结果增加显式 schema 版本，但不得改变基础任务的验收条件。

## 完成定义

- [ ] 功能要求、约束和验收标准全部满足。
- [ ] 默认离线测试、Ruff 和 mypy 检查通过，命令与结果已记录。
- [ ] 真实 DeepSeek 冒烟测试基于最终实现成功，结果已脱敏记录。
- [ ] 已检查 TASK-007 任务说明提交到当前状态的完整差异以及所有未提交修改。
- [ ] 没有未处理的严重问题；主要问题已修复或记录接受风险的理由。
- [ ] 代码通过最终审查，导师提出的针对性问题已准确回答。
- [ ] 已获得建议提交信息；是否提交和推送由学习者决定。
- [ ] 已按 L2 简版模板共同完成任务复盘，且没有遗留模板占位内容。
