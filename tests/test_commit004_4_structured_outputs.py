import json

import pytest
from pydantic import BaseModel, ConfigDict, Field

from course_factory import JobContext
from course_factory.course_specification import CourseSpecification
from course_factory.input_builder_agent import InputBuilderAgent
from course_factory.llm_backend import (
    OllamaBackend,
    StaticJSONBackend,
    StructuredOutputError,
)


class Person(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    age: int = Field(ge=0)


def test_static_backend_generate_structured_returns_model():
    backend = StaticJSONBackend({"name": "Ada", "age": 36})
    person = backend.generate_structured(
        Person,
        system="Return a person",
        user="Ada is 36",
    )
    assert person == Person(name="Ada", age=36)


def test_invalid_structured_shape_is_rejected():
    backend = StaticJSONBackend({"name": "Ada", "age": "bad"})
    with pytest.raises(StructuredOutputError):
        backend.generate_structured(
            Person,
            system="Return a person",
            user="Ada",
        )


def test_ollama_receives_actual_pydantic_json_schema(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "message": {
                    "content": json.dumps(
                        {"name": "Ada", "age": 36}
                    )
                }
            }

    def fake_post(url, json, timeout):
        captured["payload"] = json
        return Response()

    monkeypatch.setattr(
        "course_factory.llm_backend.requests.post",
        fake_post,
    )
    backend = OllamaBackend(model="qwen3:14b")
    person = backend.generate_structured(
        Person,
        system="Return person",
        user="Ada",
    )
    assert person.age == 36
    assert captured["payload"]["format"] == Person.model_json_schema()


def test_input_builder_can_use_structured_only_backend():
    class StructuredOnly:
        def generate_structured(
            self, model_type, *, system, user, temperature=0.2
        ):
            return CourseSpecification(
                title="Introduction to ggplot2",
                topic="ggplot2",
                audience="Beginners",
                duration_minutes=180,
                learning_objectives=("Create plots",),
                required_packages=("ggplot2",),
                exercise_count=1,
            )

    result = InputBuilderAgent(StructuredOnly()).run(
        JobContext.create(
            user_request="Create a ggplot2 course"
        )
    )
    assert result.status.value == "success"


def test_old_generate_json_backend_is_still_supported():
    class OldBackend:
        def generate_json(self, *, system, user, schema_hint):
            return {
                "title": "Introduction to ggplot2",
                "topic": "ggplot2",
                "audience": "Beginners",
                "duration_minutes": 180,
                "language": "English",
                "delivery_mode": "online",
                "level": "beginner",
                "prerequisites": [],
                "learning_objectives": ["Create plots"],
                "required_packages": ["ggplot2"],
                "exercise_count": 1,
                "assumptions": [],
                "clarification_required": False,
                "clarification_question": None,
            }

    result = InputBuilderAgent(OldBackend()).run(
        JobContext.create(user_request="Create a course")
    )
    assert result.status.value == "success"
