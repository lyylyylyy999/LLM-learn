from types import SimpleNamespace

response = SimpleNamespace(
    status="completed",
    output_text="Hello from fake response",
    usage=SimpleNamespace(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
    ),
)

print(response.status)
print(response.output_text)
print(response.usage.total_tokens)