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
            [
                {"conversation_id": "01", "role": "system", "content": "第一个示例"},
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
    data: list[dict[str, str]],
    result: list[dict[str, str]],
    total_messages: int,
    conversation_count: int,
    messages_by_role: dict[str, int],
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
    for role in ["system", "user", "assistant"]:
        assert role in asdict(result_raw)["messages_by_role"]


def test_main(tmp_path: Path) -> None:
    input_path = tmp_path / "data.jsonl"
    output_path = tmp_path / "test.jsonl"
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump({"conversation_id": "01", "role": "system", "content": "第一个示例"}, f, ensure_ascii=False)
    main(input_path, output_path)
    with open(output_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["total_messages"] == 1
    assert data["conversation_count"] == 1
    assert data["messages_by_role"] == {"system": 1, "user": 0, "assistant": 0}
    assert data["total_characters"] == 5
        

def test_chinese_not_escaped(tmp_path: Path) -> None:
    path = tmp_path / "data.json"

    data = {
        "content": "你好世界"
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    raw_text = path.read_text(encoding="utf-8")

    assert "你好世界" in raw_text
    assert "\\u4f60" not in raw_text


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
    path = tmp_path / "data.jsonl"
    output_path = tmp_path / "test.json"
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    with pytest.raises(exception, match=match):
        main(path, output_path)
    assert not output_path.exists()


def test_same_input_path_and_output_path(tmp_path: Path) -> None:
    input_path = tmp_path / "data.jsonl"
    output_path = tmp_path / "data.jsonl"
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump({"conversation_id": "01", "role": "system", "content": "第一个示例"}, f, ensure_ascii=False)
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
            {"conversation_id": "01", "content": "role 缺失"},
            InvalidMessageError,
            "role 字段缺失",
        ),
        (
            {"conversation_id": "123", "role": "system", "content": "字段类型错误", "age": 23},
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
    ],
)
def test_business_exception(
    tmp_path: Path, data: list[dict[str, str]], exception: type[Exception], match: str
) -> None:
    path = tmp_path / "data.jsonl"
    output_path = tmp_path / "test.json"
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")
    with pytest.raises(exception, match=match):
        main(path, output_path)
    assert not output_path.exists()


def test_file_no_exist(tmp_path: Path) -> None:
    path = BASE_PATH / "yannis.json"
    output_path = tmp_path / "test.json"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write('{"conversation_id": "01", "role": "system", "content": "第一个示例"}')
    with open(output_path, encoding="utf-8") as f:
        data = json.load(f)
    with pytest.raises(FileNotFoundError, match="输入文件不存在"):
        main(path, output_path)
    assert data == {"conversation_id": "01", "role": "system", "content": "第一个示例"}
