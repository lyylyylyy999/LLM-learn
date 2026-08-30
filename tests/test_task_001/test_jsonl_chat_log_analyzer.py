import pytest
import json
from pathlib import Path
from dataclasses import asdict
from exercises.task_001_jsonl_chat_log_analyzer.jsonl_chat_log_analyzer import (
    read_jsonl,
    statistical_data,
    main,
    InvalidMessageError,
)


BASE_PATH = Path(__file__).resolve().parent.parent.parent


@pytest.mark.parametrize(
    (
        "data",
        "result",
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
            [
                {"conversation_id": "01", "role": "system", "content": "第一个示例"},
                {"conversation_id": "02", "role": "user", "content": "第二个示例"},
                {"conversation_id": "03", "role": "assistant", "content": "第三个示例"},
            ],
            3,
            3,
            {"system_count": 1, "user_count": 1, "assistant_count": 1},
            15,
        ),
        (
            [
                {"conversation_id": "01", "role": "system", "content": "第一个示例"},
                None,
                {"conversation_id": "03", "role": "assistant", "content": "第三个示例"},
            ],
            [
                {"conversation_id": "01", "role": "system", "content": "第一个示例"},
                {"conversation_id": "03", "role": "assistant", "content": "第三个示例"},
            ],
            2,
            2,
            {"system_count": 1, "user_count": 0, "assistant_count": 1},
            10,
        ),
    ],
)
def test_valid_jsonl(
    tmp_path: Path,
    data: list,
    result: list,
    total_messages: int,
    conversation_count: int,
    messages_by_role: dict,
    total_characters: int,
) -> None:
    path = tmp_path / "data.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for obj in data:
            if obj is None:
                f.write("\n")
            else:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    data_raw = read_jsonl(path)
    data_get = []
    for data_i in data_raw:
        data_get.append(data_i)
    for index in range(len(data_get)):
        assert asdict(data_get[index]) == result[index]
    data_raw = read_jsonl(path)
    result_raw = statistical_data(data_raw)
    assert asdict(result_raw)["total_messages"] == total_messages
    assert asdict(result_raw)["conversation_count"] == conversation_count
    assert asdict(result_raw)["messages_by_role"] == messages_by_role
    assert asdict(result_raw)["total_characters"] == total_characters


def test_invalid_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "data.jsonl"
    output_path = BASE_PATH / "output" / "test.json"
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"conversation_id": "01", "role": "system", "content": "第一个示例"')
    with pytest.raises(InvalidMessageError, match="在第1行是非法 JSON"):
        main(path, output_path)
    assert not output_path.exists()


@pytest.mark.parametrize(
    ("data", "exception", "match"),
    [
        (
            [123],
            InvalidMessageError,
            "在第1行是非对象 JSON",
        ),
        (
            [{"conversation_id": "01", "role": "system"}],
            InvalidMessageError,
            "content 字段缺失",
        ),
        (
            [{"conversation_id": "01", "content": "role 缺失"}],
            InvalidMessageError,
            "role 字段缺失",
        ),
        (
            [{"conversation_id": 123, "role": "system", "content": "字段类型错误"}],
            InvalidMessageError,
            "第 1 行数据无效: conversation_id 必须为 str 类型，实际为 int",
        ),
        (
            [{"conversation_id": "01", "role": "yannis", "content": "字段类型错误"}],
            InvalidMessageError,
            "role 只能是 `system`、`user` 或 `assistant`",
        ),
        (
            [{"conversation_id": "01", "role": "user", "content": "  "}],
            InvalidMessageError,
            "第 1 行数据无效: content 不能为空",
        ),
    ],
)
def test_exception(
    tmp_path: Path, data: list, exception: type[Exception], match: str
) -> None:
    path = tmp_path / "data.jsonl"
    output_path = BASE_PATH / "output" / "test.json"
    with open(path, "w", encoding="utf-8") as f:
        for obj in data:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    with pytest.raises(exception, match=match):
        main(path, output_path)
    assert not output_path.exists()


def test_file_no_exist() -> None:
    path = BASE_PATH / "yannis.json"
    output_path = BASE_PATH / "output" / "test.json"
    with pytest.raises(FileNotFoundError, match="输入文件不存在"):
        main(path, output_path)
    assert not output_path.exists()
