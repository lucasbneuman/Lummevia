from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DatasetBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class PromptDatasetCase(DatasetBaseSchema):
    case_id: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    input_prompt: str = Field(min_length=1)
    expected_keywords: list[str] = Field(default_factory=list)
    expected_sections: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptDataset(DatasetBaseSchema):
    dataset_id: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    cases: list[PromptDatasetCase] = Field(min_length=1)
