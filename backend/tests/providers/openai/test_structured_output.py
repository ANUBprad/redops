"""Tests for structured output support."""

from app.providers.models.options import ChatOptions
from app.providers.openai.mappers.request import map_chat_options


class TestStructuredOutput:
    """Tests for structured output mapping."""

    def test_json_object_response_format(self) -> None:
        options = ChatOptions(
            response_format={"type": "json_object"},
        )
        result = map_chat_options(options)
        assert result["response_format"] == {"type": "json_object"}

    def test_json_schema_response_format(self) -> None:
        schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "weather",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "temperature": {"type": "number"},
                    },
                    "required": ["temperature"],
                },
            },
        }
        options = ChatOptions(response_format=schema)
        result = map_chat_options(options)
        assert result["response_format"]["type"] == "json_schema"
        assert result["response_format"]["json_schema"]["name"] == "weather"

    def test_no_response_format(self) -> None:
        options = ChatOptions(temperature=0.5)
        result = map_chat_options(options)
        assert "response_format" not in result
