# TASK-012 — 离线批量评测报告

- **难度：** L2
- **预计有效编码时间：** 90–120 分钟
- **开发分支：** `develop`
- **状态：** 已完成
- **任务设计基线：** `82dfe69`（路线优化完成提交）
- **实现审查基线：** 本任务说明提交；若说明尚未提交，则以 `82dfe69` 为基线并检查未提交修改

## 背景

TASK-008 已能加载固定评测样例，并对一个 `EvalCase` 与一个 `AnalysisResult` 计算可解释的分数。但只看单条分数，无法知道一次评测覆盖了多少样例、几条没有拿到有效模型结果、最终有多少条真正通过。忽略失败样例还会使总体结果显得过于乐观。

本任务为已有评分器增加一个**离线批量汇总层**。调用者提供样例和每条样例的现成结果；批量函数复用 TASK-008 的 `evaluation()`，生成可序列化的逐条成绩与总体计数。它为后续的模型运行器和版本对比提供稳定报告合同，本次不接入真实模型。

## 学习目标

完成后，学习者应该能够：

- [ ] 区分“已有结果评分”“生成模型结果”和“保存报告”三个职责。
- [ ] 解释为什么没有产出有效结果的样例仍必须计入总体分母。
- [ ] 复用现有单条评分器，维护逐条结果与总体计数的一致性。
- [ ] 设计既可序列化又不暴露原始对话、模型输出或异常文本的报告。

## 前置知识

- 复习 TASK-008 的 `verify_evaluation_set()`、`EvalCase`、`EvalResult` 和 `evaluation()`；本任务必须直接复用已有单条评分行为。
- 复习 `AnalysisResult` 的字段，以及 Pydantic 模型的 `model_dump(mode="json")`。
- 理解 `Sequence`、`Mapping` 与 `None` 作为“本次没有有效分析结果”的含义。
- 用纸笔算一个例子：3 条样例中，1 条评分通过、1 条评分未通过、1 条模型执行失败。写出总数、成功评分数、执行失败数、通过数和总体通过率；实现前先核对分母。

## 功能要求

### 1. 公开批量接口

- 在 `exercises/task_008_llm_evaluation/` 下新增 `batch_evaluation.py`，从现有 `llm_evaluation.py` 导入并复用 `EvalCase`、`EvalResult` 和 `evaluation()`；不要复制概念匹配或通过条件。
- 提供公开函数 `evaluate_batch(cases, outcomes)`：
  - `cases` 是按评测集顺序排列的 `Sequence[EvalCase]`。
  - `outcomes` 是按 `case_id` 索引的 `Mapping[str, AnalysisResult | None]`。
  - `AnalysisResult` 表示已经取得有效结果，必须调用既有 `evaluation()` 评分；显式的 `None` 表示该样例本次没有有效结果，不调用单条评分器。
- `cases` 中的 ID 必须唯一，且 `outcomes` 的键集合必须与这些 ID 完全一致。重复、缺失或多余 ID 应抛出不包含原始对话、结果或异常文本的 `ValueError`，不能默默跳过或多算。
- 空的 `cases` 与空的 `outcomes` 是合法输入，返回空报告；空样例配非空结果仍按多余 ID 处理。
- 不修改传入的样例、结果或映射，不调用模型，不读取环境变量，不写文件。

### 2. 报告合同

- 提供公开的 Pydantic 报告模型 `BatchEvalReport`，包含：
  - `total_cases`：输入样例数。
  - `scored_cases`：收到 `AnalysisResult` 并完成评分的样例数，包括单条评分未通过的样例。
  - `failed_cases`：显式结果为 `None` 的样例数。
  - `passed_cases`：单条评分中 `passed=True` 的样例数。
  - `pass_rate`：`passed_cases / total_cases`；总数为零时为 `None`。
  - `case_results`：与 `cases` 同顺序的逐条结果列表。
- 每条逐条结果至少包含 `case_id`、`status` 和 `score`。`status` 仅为 `"scored"` 或 `"failed"`；前者的 `score` 是已有 `EvalResult`，后者的 `score` 为 `None`。
- 报告应满足 `scored_cases + failed_cases == total_cases`、`passed_cases <= scored_cases`，且 `len(case_results) == total_cases`。
- 报告能够通过 `model_dump(mode="json")` 得到可交给 `json.dumps()` 的数据，且不包含原始对话、原始模型输出、API Key、SDK 异常对象或异常消息。此处只返回数据，不设计文件格式或写盘命令。

## 约束

- 保持 TASK-008 单条评测器的公开接口和现有行为，不改其规则来迁就批量统计。
- 本任务不创建真实或模拟的模型运行器；调用者直接传入已取得的 `AnalysisResult` 或显式 `None`。
- 不新增 CLI、JSONL 报告文件、真实 API 调用、价格估算、token/延迟汇总、两次运行比较、数据库或 HTTP 接口。
- 不使用 pandas、NumPy 或第三方评测框架；用已有依赖与标准库完成。
- 默认测试必须完全离线，不读取 API Key 或调用 DeepSeek。
- 学习者先独立完成生产代码和基本手动验证，并明确通知导师；导师随后编写 `tests/test_task_012/` 中的测试。除非学习者明确要求完整修复，生产缺陷由学习者修正，测试自身缺陷由导师修正。

## 验收标准

- [ ] 两条有结果的样例分别通过和未通过，第三条显式失败时，报告为 `total_cases=3`、`scored_cases=2`、`failed_cases=1`、`passed_cases=1`、`pass_rate=1/3`。
- [ ] 逐条结果与输入样例顺序一致；有结果的样例保留 TASK-008 的完整 `EvalResult`，失败样例仅标明失败而不泄露异常细节。
- [ ] 全部失败时 `pass_rate=0.0`；空批次返回零计数、空列表和 `pass_rate=None`。
- [ ] 重复、缺失和多余 ID 均被安全拒绝；不丢失失败样例，也不以 `scored_cases` 代替总分母。
- [ ] 报告可 JSON 序列化，序列化内容不含原始对话或模型输出；输入没有被修改。
- [ ] TASK-008 既有评分测试及全量测试、Ruff、mypy 均通过。

## 测试要求

按 AGENTS.md 的测试协作模式，导师在学习者明确通知生产代码完成后编写测试。测试从公开接口和可观察的报告内容出发。

导师测试至少覆盖：

- [ ] 全通过、评分未通过和显式失败混合的统计与顺序；验证失败样例确实进入总分母。
- [ ] 全部失败、空批次和单条样例。
- [ ] 重复、缺失、多余 ID，以及错误输入不会产生误导性的报告。
- [ ] 复用已有单条评分结果，包括“无行动项却生成行动项”这一未通过路径。
- [ ] `model_dump(mode="json")` 可被 `json.dumps()` 序列化，并检查真实进入样例与结果的敏感标记没有进入报告。
- [ ] 输入样例、结果和映射未被修改；默认测试没有模型或网络调用。

最终至少实际运行并记录：

```text
D:\Anaconda_envs\envs\LLM\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp
D:\Anaconda_envs\envs\LLM\python.exe -m ruff check .
D:\Anaconda_envs\envs\LLM\python.exe -m mypy exercises tests
git diff --check
```

上述命令是最终验证要求；学习者在导师编写测试前先完成不访问模型的基本手动验证。

## 边界情况

- `None` 表示明确的执行失败；映射里完全没有某个 ID 表示输入不一致，不能当作同一种情况。
- `scored_cases` 包含评分为未通过的样例，不能仅统计 `passed=True`。
- 输入顺序与映射遍历顺序不同；输出顺序必须由 `cases` 决定。
- 空批次的通过率没有分母，使用 `None`；非空批次全失败时通过率为 `0.0`。
- `EvalCase` 的 `case_id` 应为不含敏感信息的稳定标识；报告使用它关联成绩，不输出对话、原始结果或异常文本。

## 进阶任务

- 用可注入的模型替身批量产生结果，并把调用失败显式转换为本任务的 `None` 输入。
- 在明确数据格式与脱敏边界后保存、加载和比较两个版本的报告。
- 在真实调用经学习者显式开启后，记录模型版本、提示词版本、token、延迟与估算成本。

进阶任务不属于本次基础完成条件。

## 完成定义

- [ ] 功能要求和验收标准全部满足，离线演示可复现。
- [ ] 导师编写的 TASK-012 测试及全量测试通过，学习者记录实际命令与结果，并审阅关键测试及 Mock 边界。
- [ ] 边界情况已处理；未处理项及原因明确记录。
- [ ] 没有未处理的严重问题；主要问题已修复或记录并说明接受风险的理由。
- [ ] 已检查任务说明提交或 `82dfe69` 至当前状态的完整差异，以及未提交修改，变更范围与本任务一致。
- [ ] 代码通过最终审查，导师依据最终实现提出 3–5 个针对性问题，学习者准确回答。
- [ ] 已给出建议提交信息；是否提交、推送或合并由学习者决定。
- [ ] 导师和学习者按 L2 简版模板共同完成复盘，没有遗留模板占位内容。
