import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Generator, Iterable


class InvalidMessageError(Exception):
    pass


@dataclass
class ValidData:
    conversation_id: str
    role: str
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.conversation_id, str):
            raise InvalidMessageError(
                f"conversation_id 必须为 str 类型，实际为 {type(self.conversation_id).__name__}"
            )
        if not isinstance(self.role, str):
            raise InvalidMessageError(
                f"role 必须为 str 类型，实际为 {type(self.role).__name__}"
            )
        if not isinstance(self.content, str):
            raise InvalidMessageError(
                f"content 必须为 str 类型，实际为 {type(self.content).__name__}"
            )
        role_valid = ["system", "user", "assistant"]
        if self.role not in role_valid:
            raise InvalidMessageError("role 只能是 `system`、`user` 或 `assistant`")
        for name, value in [
            ("conversation_id", self.conversation_id),
            ("content", self.content),
        ]:
            if not value.strip():
                raise InvalidMessageError(f"{name} 不能为空")


@dataclass
class StatisticalResult:
    total_messages: int
    conversation_count: int
    messages_by_role: dict[str, int]
    total_characters: int


def read_jsonl(path: Path | str) -> Generator[ValidData, None, None]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError("输入文件不存在")
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
                field = {"conversation_id", "role", "content"}
                for field_name in field:
                    if field_name not in data:
                        raise ValueError(f"{field_name} 字段缺失")
                extra_fields = set(data) - field
                if extra_fields:
                    raise InvalidMessageError(
                        f"存在额外字段: {', '.join(sorted(extra_fields))}"
                    )
                valid = ValidData(**data)
            except (ValueError, InvalidMessageError) as e:
                raise InvalidMessageError(f"第{line_number}行数据无效: {e}") from e
            yield valid


def statistical_data(valid: Iterable[ValidData]) -> StatisticalResult:
    total_messages = 0
    conversation_ids: set[str] = set()
    system_count = 0
    user_count = 0
    assistant_count = 0
    total_characters = 0
    for message in valid:
        total_messages += 1
        conversation_ids.add(message.conversation_id)
        if message.role == "system":
            system_count += 1
        if message.role == "user":
            user_count += 1
        if message.role == "assistant":
            assistant_count += 1
        total_characters += len(message.content)
    messages_by_role = {
        "system": system_count,
        "user": user_count,
        "assistant": assistant_count,
    }
    conversation_count = len(conversation_ids)
    return StatisticalResult(
        total_messages=total_messages,
        conversation_count=conversation_count,
        messages_by_role=messages_by_role,
        total_characters=total_characters,
    )


def main(input_path: Path, output_path: Path) -> None:
    if input_path.resolve() == output_path.resolve():
        raise InvalidMessageError("输入路径和输出路径不能够相同！")
    valid_data = read_jsonl(input_path)
    statistical_result = statistical_data(valid_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(statistical_result), f, ensure_ascii=False)
