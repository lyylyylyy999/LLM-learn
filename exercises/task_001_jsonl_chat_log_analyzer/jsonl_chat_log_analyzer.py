import json
from pathlib import Path
from dataclasses import dataclass
from typing import Generator, Optional


BASE_PATH = Path(__file__).resolve().parent.parent.parent
path = BASE_PATH / "data"


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
    line_number: int
    line: dict


def read_jsonl(path: Path | str) -> Generator[ValidData, None, None]:
    if not path.exists():
        raise FileNotFoundError("该路径下文件不存在")
    with open(path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
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


def statistical_data(valid: ValidData) -> dict[str, int]:
    