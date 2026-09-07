# def decorator(func):
#     def wrapper():
#         print("before")
#         a = func()
#         print("after")
#         return a
#     return wrapper

# @decorator
# def hello():
#     print("hello")
#     return 100

# print(hello())

from functools import wraps


def print_name(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@print_name  # add = wrapper(add(a, b))
def add(a: int, b: int) -> int:
    return a + b


result = add(1, 2)
print(add.__name__)
# print(result)


# def wrapper(func):
#     def inner(*args, **kwargs):
#         print("args =", args)
#         print("kwargs =", kwargs)
#         return func(*args, **kwargs)

#     return inner


# @wrapper
# def introduce(name, age, city="Beijing", student=True):
#     print(name, age, city, student)


# introduce(
#     "Yannis",
#     24,
#     city="Shanghai",
#     student=False,
# )


# from functools import wraps


# def decorator_without_wraps(func):
#     def wrapper(*args, **kwargs):
#         return func(*args, **kwargs)

#     return wrapper


# def decorator_with_wraps(func):
#     @wraps(func)
#     def wrapper(*args, **kwargs):
#         return func(*args, **kwargs)

#     return wrapper


# @decorator_without_wraps
# def add1(a, b):
#     """返回两个数之和。"""
#     return a + b


# @decorator_with_wraps
# def add2(a, b):
#     """返回两个数之和。"""
#     return a + b


# print(add1.__name__)
# print(add1.__doc__)

# print(add2.__name__)
# print(add2.__doc__)
