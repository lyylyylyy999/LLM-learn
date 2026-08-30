import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Generator, Optional


BASE_PATH = Path(__file__).resolve().parent.parent.parent


class InvalidMessageError(Exception):
    pass


@dataclass
class ValidData:
    conversation_id: Optional[str] = None
    role: Optional[str] = None
    content: Optional[str] = None

    def __post_init__(self):
        if self.conversation_id is None:
            raise ValueError("conversation_id 字段缺失")
        if self.role is None:
            raise ValueError("role 字段缺失")
        if self.content is None:
            raise ValueError("content 字段缺失")
        if not isinstance(self.conversation_id, str):
            raise InvalidMessageError(f"conversation_id 必须为 str 类型，实际为{type(self.conversation_id)}")
        if not isinstance(self.role, str):
            raise InvalidMessageError(f"role 必须为 str 类型，实际为{type(self.role)}")
        if not isinstance(self.content, str):
            raise InvalidMessageError(f"content 必须为 str 类型，实际为{type(self.content)}")
        role_valid = ["system", "user", "assistant"]
        if self.role not in role_valid:
            raise InvalidMessageError("role 只能是 `system`、`user` 或 `assistant`")
        for name, value in [
            ("conversation_id", self.conversation_id),
            ("content", self.content)
        ]:
            if not value:
                raise InvalidMessageError(f"{name} 不能为空")


@dataclass
class Statistical_Result:
    total_messages: int
    conversation_count: int
    messages_by_role: dict
    total_characters: int


def read_jsonl(path: Path | str) -> Generator[ValidData, None, None]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError("该路径下文件不存在")
    with open(path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if line.strip() == "":
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                raise InvalidMessageError(f"在第{line_number}行是非法 JSON") from e
            if not isinstance(data, dict):
                raise InvalidMessageError(f"在第{line_number}行是非对象 JSON")
            try:
                valid = ValidData(**data)
            except (ValueError, InvalidMessageError) as e:
                raise InvalidMessageError(f"第 {line_number} 行数据无效: {e}") from e
            yield valid


def statistical_data(valid: ValidData) -> Statistical_Result:
    data = list(valid)
    total_messages = len(data)
    conversation_value = []
    role_value = []
    content_value = []
    for i in range(len(data)):
        conversation_value.append(data[i].conversation_id)
        role_value.append(data[i].role)
        content_value.append(data[i].content)
    conversation_count = len(set(conversation_value))
    system_count = 0
    user_count = 0
    assistant_count = 0
    for i in role_value:
        if i == "system":
            system_count += 1
        if i == "user":
            user_count += 1
        if i == "assistant":
            assistant_count += 1
    messages_by_role = {
        "system_count": system_count,
        "user_count": user_count,
        "assistant_count": assistant_count
    }
    total_characters = sum(len(i) for i in content_value)
    return Statistical_Result(
        total_messages=total_messages,
        conversation_count=conversation_count,
        messages_by_role=messages_by_role,
        total_characters=total_characters
    )


def main(input_path: Path, output_path: Path) -> None:
    valid_data = read_jsonl(input_path)
    statistical_result = statistical_data(valid_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(statistical_result), f, ensure_ascii=False)