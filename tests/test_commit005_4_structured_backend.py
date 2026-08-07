from pydantic import BaseModel, Field

from course_factory.llm_backend import (
    OllamaBackend,
    StructuredOutputError,
)
from course_factory.structured_output import (
    extract_first_json_value,
    parse_first_json_value,
)


class Example(BaseModel):
    name: str
    values: list[int] = Field(min_length=1)


class FakeOllama(OllamaBackend):
    def __init__(self, responses):
        super().__init__(
            model="fake",
            structured_max_attempts=3,
        )
        self.responses = list(responses)
        self.calls = []

    def _chat(
        self,
        *,
        system,
        user,
        format_value,
        temperature,
    ):
        self.calls.append({
            "system": system,
            "user": user,
            "format_value": format_value,
            "temperature": temperature,
        })
        return self.responses.pop(0)


def test_extracts_first_json_and_ignores_trailing_text():
    raw = (
        'preface\n'
        '{"name":"x","values":[1,{"nested":"}"}]}\n'
        'trailing explanation'
    )
    assert extract_first_json_value(raw) == (
        '{"name":"x","values":[1,{"nested":"}"}]}'
    )


def test_extract_handles_markdown_fence():
    raw = '```json\n{"name":"x","values":[1]}\n```'
    assert parse_first_json_value(raw) == {
        "name": "x",
        "values": [1],
    }


def test_native_schema_is_sent_to_ollama_format():
    backend = FakeOllama([
        '{"name":"x","values":[1]}'
    ])
    result = backend.generate_structured(
        Example,
        system="system",
        user="user",
    )

    assert result.name == "x"
    assert (
        backend.calls[0]["format_value"]
        == Example.model_json_schema()
    )

    # Schema is not dumped into prompts for native structured output.
    assert "properties" not in backend.calls[0]["user"]
    assert "Return only" not in backend.calls[0]["system"]


def test_trailing_characters_are_recovered_in_backend():
    backend = FakeOllama([
        '{"name":"x","values":[1]}\nExtra prose.'
    ])
    result = backend.generate_structured(
        Example,
        system="system",
        user="user",
    )
    assert result == Example(
        name="x",
        values=[1],
    )
    assert len(backend.calls) == 1


def test_multiple_json_values_uses_first_complete_value():
    backend = FakeOllama([
        (
            '{"name":"first","values":[1]}'
            '\n{"name":"second","values":[2]}'
        )
    ])
    result = backend.generate_structured(
        Example,
        system="system",
        user="user",
    )
    assert result.name == "first"


def test_semantically_invalid_output_retries_same_schema():
    backend = FakeOllama([
        '{"name":"x","values":[]}',
        '{"name":"x","values":[7]}',
    ])
    result = backend.generate_structured(
        Example,
        system="system",
        user="user",
    )

    assert result.values == [7]
    assert len(backend.calls) == 2
    assert (
        backend.calls[0]["format_value"]
        == backend.calls[1]["format_value"]
        == Example.model_json_schema()
    )


def test_failure_preserves_raw_and_extracted_content():
    backend = FakeOllama([
        '{"name":"x","values":[]}',
        '{"name":"x","values":[]}',
        '{"name":"x","values":[]}',
    ])

    try:
        backend.generate_structured(
            Example,
            system="system",
            user="user",
        )
    except StructuredOutputError as exc:
        assert exc.attempts == 3
        assert exc.raw_content is not None
        assert exc.extracted_content is not None
        assert '"values":[]' in (
            exc.extracted_content.replace(" ", "")
        )
    else:
        raise AssertionError(
            "Expected StructuredOutputError"
        )
