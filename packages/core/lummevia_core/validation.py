from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class CoreArtifactModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=False,
        str_strip_whitespace=True,
    )

    @field_validator("*", mode="before")
    @classmethod
    def reject_blank_strings(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            raise ValueError("String fields must not be blank")
        return value
