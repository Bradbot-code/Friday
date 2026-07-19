from __future__ import annotations

import inspect
import json
import types
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Callable, Union, get_args, get_origin, get_type_hints


@dataclass
class RegisteredTool:
    name: str
    description: str
    function: Callable[..., Any]
    requires_confirmation: bool = False


@dataclass
class ToolExecutionResult:
    success: bool
    tool_name: str
    message: str
    data: Any = None


class ToolManager:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        name: str,
        description: str,
        function: Callable[..., Any],
        requires_confirmation: bool = False,
    ) -> None:
        clean_name = name.strip()

        if not clean_name:
            raise ValueError("Tool name cannot be empty.")

        if clean_name in self._tools:
            raise ValueError(
                f"A tool named '{clean_name}' is already registered."
            )

        self._tools[clean_name] = RegisteredTool(
            name=clean_name,
            description=description.strip(),
            function=function,
            requires_confirmation=requires_confirmation,
        )

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def get_tool(self, name: str) -> RegisteredTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(
                f"Tool is not registered: {name}"
            ) from exc

    def list_tools(self) -> list[RegisteredTool]:
        return list(self._tools.values())

    def get_tool_descriptions(self) -> str:
        if not self._tools:
            return "No tools are currently available."

        lines: list[str] = []

        for tool in self._tools.values():
            signature = inspect.signature(tool.function)

            confirmation_text = (
                "Requires user confirmation."
                if tool.requires_confirmation
                else "Does not require confirmation."
            )

            lines.append(
                f"- {tool.name}{signature}: "
                f"{tool.description} "
                f"{confirmation_text}"
            )

        return "\n".join(lines)

    def get_openai_tools(self) -> list[dict[str, Any]]:
        """Return registered tools in Responses API function-tool format."""
        definitions: list[dict[str, Any]] = []

        for tool in self._tools.values():
            signature = inspect.signature(tool.function)
            type_hints = get_type_hints(tool.function)
            properties: dict[str, Any] = {}
            required: list[str] = []

            for name, parameter in signature.parameters.items():
                if name in {"self", "cls"}:
                    continue

                annotation = type_hints.get(name, parameter.annotation)
                properties[name] = self._annotation_to_schema(annotation)

                if parameter.default is inspect.Parameter.empty:
                    required.append(name)

            definitions.append(
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                        "additionalProperties": False,
                    },
                    "strict": False,
                }
            )

        return definitions

    @staticmethod
    def result_to_json(result: ToolExecutionResult) -> str:
        """Serialize a tool result into a model-readable JSON string."""
        data = result.data

        if is_dataclass(data) and not isinstance(data, type):
            data = asdict(data)

        return json.dumps(
            {
                "success": result.success,
                "tool_name": result.tool_name,
                "message": result.message,
                "data": data,
            },
            default=str,
        )

    @classmethod
    def _annotation_to_schema(cls, annotation: Any) -> dict[str, Any]:
        if annotation in {inspect.Parameter.empty, Any}:
            return {}

        origin = get_origin(annotation)
        arguments = get_args(annotation)

        if origin in {list, tuple, set}:
            item_annotation = arguments[0] if arguments else Any
            return {
                "type": "array",
                "items": cls._annotation_to_schema(item_annotation),
            }

        if origin is dict:
            return {"type": "object"}

        if origin in {Union, types.UnionType}:
            schemas = [
                {"type": "null"}
                if argument is type(None)
                else cls._annotation_to_schema(argument)
                for argument in arguments
            ]
            return {"anyOf": schemas}

        scalar_types = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
        }

        if annotation in scalar_types:
            return {"type": scalar_types[annotation]}

        return {"type": "string"}

    def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        confirmed: bool = False,
    ) -> ToolExecutionResult:
        arguments = arguments or {}

        try:
            tool = self.get_tool(name)

            if (
                tool.requires_confirmation
                and not confirmed
            ):
                return ToolExecutionResult(
                    success=False,
                    tool_name=name,
                    message=(
                        "This tool requires user confirmation "
                        "before it can be executed."
                    ),
                )

            result = tool.function(**arguments)

            if hasattr(result, "success"):
                result_success = bool(
                    getattr(result, "success")
                )

                result_message = str(
                    getattr(
                        result,
                        "message",
                        "Tool execution completed.",
                    )
                )

                return ToolExecutionResult(
                    success=result_success,
                    tool_name=name,
                    message=result_message,
                    data=result,
                )

            return ToolExecutionResult(
                success=True,
                tool_name=name,
                message="Tool execution completed.",
                data=result,
            )

        except TypeError as exc:
            return ToolExecutionResult(
                success=False,
                tool_name=name,
                message=(
                    "The tool received invalid arguments: "
                    f"{exc}"
                ),
            )

        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                tool_name=name,
                message=f"Tool failed: {exc}",
            )
