class PrintClass():
    def __enter__(self):
        print("进入__enter__")
        return self

    def __exit__(self, exc_type, exc, tb):
        print("进入__exit__")
        print(f"exc_type={exc_type}")
        print(f"exc={exc}")
        return True

with PrintClass():
    print("执行正常代码块")

try:
    with PrintClass():
        print("执行 with 代码块")
        raise ValueError("出错了")
except ValueError as exc:
    print(f"外部捕获异常: {exc}")


from unittest.mock import Mock

clock = Mock(side_effect=[10.0, 10.25])
start = clock()
end = clock()
time = end - start
print(start)
print(end)
print(time)
