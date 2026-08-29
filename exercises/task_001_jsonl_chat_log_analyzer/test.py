from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent


path_valid = BASE_DIR / "data" / "task_001_valid.jsonl"
# with open(path_valid, encoding="utf-8") as f:
#     print(json.load(f))
# path_invalid = BASE_DIR / "data" / "task_001_invalid.json"
# with open(path_invalid) as f:
#     print(json.load(f))

with open(path_valid, encoding="utf-8") as f:
    for line_number, line in enumerate(f, start=1):
        print(line_number, line)


def test_file(tmp_path):
    path = tmp_path / "hello.txt"
    path.write_text("hello", encoding="utf-8")
    print(f"\n文件路径: {path}")  # 运行 pytest -s 会显示
    assert path.read_text(encoding="utf-8") == "hello"