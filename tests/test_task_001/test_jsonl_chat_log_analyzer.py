import pytest
import json
from dataclasses import asdict
from exercises.task_001_jsonl_chat_log_analyzer.jsonl_chat_log_analyzer import read_jsonl, statistical_data, InvalidMessageError


def test_valid_jsonl(tmp_path) -> None:
    path = tmp_path / "data.jsonl"
    lines = [
        {"conversation_id": "01", "role": "system", "content": "第一个示例"},
        {"conversation_id": "02", "role": "user", "content": "第二个示例"},
        {"conversation_id": "03", "role": "assistant", "content": "第三个示例"},
    ]
    with open(path, "w", encoding="utf-8") as f:
        for obj in lines:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    data = read_jsonl(path)
    data_a = []
    for i in data:
        data_a.append(i)
    assert asdict(data_a[0]) == {"conversation_id": "01", "role":"system", "content": "第一个示例"}
    assert asdict(data_a[1]) == {"conversation_id": "02", "role":"user", "content": "第二个示例"}
    assert asdict(data_a[2]) == {"conversation_id": "03", "role":"assistant", "content": "第三个示例"}
    data = read_jsonl(path)
    result = statistical_data(data)
    assert asdict(result)["total_messages"] == 3
    assert asdict(result)["conversation_count"] == 3
    assert asdict(result)["messages_by_role"] == {
        "system_count": 1,
        "user_count": 1,
        "assistant_count": 1,
    }
    assert asdict(result)["total_characters"] == 15
    

def test_invalid_jsonl(tmp_path) -> None:
    path = tmp_path / "data.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(123, ensure_ascii=False) + "\n")
    with pytest.raises(InvalidMessageError, match="在第1行是非对象 JSON"):
        next(read_jsonl(path))