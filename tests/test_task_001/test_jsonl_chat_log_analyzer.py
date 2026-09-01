import pytest
import json
from pathlib import Path
from exercises.task_001_jsonl_chat_log_analyzer.jsonl_chat_log_analyzer import (
    main,
    InvalidMessageError,
)


@pytest.mark.parametrize(
    (
        "data",
        "total_messages",
        "conversation_count",
        "messages_by_role",
        "total_characters",
    ),
    [
        (
            [
                {"conversation_id": "01", "role": "system", "content": "第一个示例"},
                {"conversation_id": "02", "role": "user", "content": "第二个示例"},
                {"conversation_id": "03", "role": "assistant", "content": "第三个示例"},
            ],
            3,
            3,
            {"system": 1, "user": 1, "assistant": 1},
            15,
        ),
        (
            [
                {"conversation_id": "01", "role": "system", "content": "第一个示例"},
                None,
                {
                    "conversation_id": "03",
                    "role": "assistant",
                    "content": "第三个示例  \n",
                },
            ],
            2,
            2,
            {"system": 1, "user": 0, "assistant": 1},
            13,
        ),
        (
            [
                None,
                None,
            ],
            0,
            0,
            {"system": 0, "user": 0, "assistant": 0},
            0,
        ),
        (
            [],
            0,
            0,
            {"system": 0, "user": 0, "assistant": 0},
            0,
        ),
    ],
)
def test_valid_jsonl(
    tmp_path: Path,
    data: list[object],
    total_messages: int,
    conversation_count: int,
    messages_by_role: dict[str, int],
    total_characters: int,
) -> None:
    input_path = tmp_path / "data.json"
    output_path = tmp_path / "test.json"
    with open(input_path, "w", encoding="utf-8") as f:
        for obj in data:
            if obj is None:
                f.write("\n")
            else:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    main(input_path, output_path)
    with open(output_path, encoding="utf-8") as f:
        data_output = json.load(f)
    assert data_output["total_messages"] == total_messages
    assert data_output["conversation_count"] == conversation_count
    assert data_output["messages_by_role"] == messages_by_role
    assert data_output["total_characters"] == total_characters
    for role in ["system", "user", "assistant"]:
        assert role in data_output["messages_by_role"]


@pytest.mark.parametrize(
    ("data", "exception", "match"),
    [
        (
            '{"conversation_id": "01", "role": "system", "content": "第一个示例"',
            InvalidMessageError,
            "在第1行是非法 JSON",
        ),
        (
            '{"conversation_id": "01", "role": "system", "content": "第一个示例"}\n{"conversation_id": "01", "role": "system", "content": "第一个示例"',
            InvalidMessageError,
            "在第2行是非法 JSON",
        ),
    ],
)
def test_invalid_jsonl(
    tmp_path: Path, data: str, exception: type[Exception], match: str
) -> None:
    path = tmp_path / "data.json"
    output_path = tmp_path / "test.json"
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    with pytest.raises(exception, match=match):
        main(path, output_path)
    assert not output_path.exists()


def test_same_input_path_and_output_path(tmp_path: Path) -> None:
    input_path = tmp_path / "data.json"
    output_path = tmp_path / "data.json"
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(
            {"conversation_id": "01", "role": "system", "content": "第一个示例"},
            f,
            ensure_ascii=False,
        )
    with pytest.raises(InvalidMessageError, match="输入路径和输出路径不能够相同！"):
        main(input_path, output_path)
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data == {"conversation_id": "01", "role": "system", "content": "第一个示例"}


@pytest.mark.parametrize(
    ("data", "exception", "match"),
    [
        (
            123,
            InvalidMessageError,
            "在第1行是非对象 JSON",
        ),
        (
            {"conversation_id": "01", "role": "system"},
            InvalidMessageError,
            "content 字段缺失",
        ),
        (
            {"conversation_id": "01", "content": "role 缺失"},
            InvalidMessageError,
            "role 字段缺失",
        ),
        (
            {"role": "user", "content": "role 缺失"},
            InvalidMessageError,
            "conversation_id 字段缺失",
        ),
        (
            {
                "conversation_id": "123",
                "role": "system",
                "content": "字段类型错误",
                "age": 23,
            },
            InvalidMessageError,
            "第1行数据无效: 存在额外字段: age",
        ),
        (
            {"conversation_id": 123, "role": "system", "content": "字段类型错误"},
            InvalidMessageError,
            "第1行数据无效: conversation_id 必须为 str 类型，实际为 int",
        ),
        (
            {"conversation_id": "123", "role": 123, "content": "字段类型错误"},
            InvalidMessageError,
            "第1行数据无效: role 必须为 str 类型，实际为 int",
        ),
        (
            {"conversation_id": "123", "role": "system", "content": True},
            InvalidMessageError,
            "第1行数据无效: content 必须为 str 类型，实际为 bool",
        ),
        (
            {"conversation_id": "01", "role": "yannis", "content": "字段类型错误"},
            InvalidMessageError,
            "role 只能是 `system`、`user` 或 `assistant`",
        ),
        (
            {"conversation_id": "01", "role": "user", "content": "  "},
            InvalidMessageError,
            "第1行数据无效: content 不能为空",
        ),
        (
            {"conversation_id": "", "role": "user", "content": "convwesation 为空白"},
            InvalidMessageError,
            "第1行数据无效: conversation_id 不能为空",
        ),
        (
            {"conversation_id": "\t", "role": "user", "content": "convwesation 为空白"},
            InvalidMessageError,
            "第1行数据无效: conversation_id 不能为空",
        ),
    ],
)
def test_business_exception(
    tmp_path: Path, data: object, exception: type[Exception], match: str
) -> None:
    path = tmp_path / "data.json"
    output_path = tmp_path / "test.json"
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")
    with pytest.raises(exception, match=match):
        main(path, output_path)
    assert not output_path.exists()


def test_output_exist_with_business_exception(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    output_path = tmp_path / "test.json"
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {"conversation_id": "01", "role": "user", "content": "  "},
                ensure_ascii=False,
            )
            + "\n"
        )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {"conversation_id": "01", "role": "system", "content": "第一个示例"},
            f,
            ensure_ascii=False,
        )
    with pytest.raises(InvalidMessageError, match="第1行数据无效: content 不能为空"):
        main(path, output_path)
    with open(output_path, encoding="utf-8") as f:
        data_output = json.load(f)
        assert data_output == {
            "conversation_id": "01",
            "role": "system",
            "content": "第一个示例",
        }


def test_file_no_exist(tmp_path: Path) -> None:
    output_path = tmp_path / "test.json"
    with pytest.raises(FileNotFoundError, match="输入文件不存在"):
        main(tmp_path / "yannis.json", output_path)
