from __future__ import annotations

import json
from importlib.resources import files
from typing import ClassVar

from lummevia_datasets.schemas import PromptDataset


class DatasetRegistry:
    _default_instance: ClassVar["DatasetRegistry" | None] = None

    def __init__(self) -> None:
        fixtures = files("lummevia_datasets").joinpath("fixtures")
        self._dataset_files = {
            "pm_business_brief_dataset": fixtures.joinpath(
                "pm_business_brief_dataset.json"
            ),
        }
        self._datasets: dict[str, PromptDataset] = {}

    @classmethod
    def default(cls) -> "DatasetRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def get(self, dataset_id: str) -> PromptDataset:
        dataset = self._datasets.get(dataset_id)
        if dataset is not None:
            return dataset

        dataset_file = self._dataset_files.get(dataset_id)
        if dataset_file is None:
            raise KeyError(f"Dataset '{dataset_id}' is not registered.")

        loaded = PromptDataset.model_validate(json.loads(dataset_file.read_text("utf-8")))
        self._datasets[dataset_id] = loaded
        return loaded


def get_dataset(dataset_id: str) -> PromptDataset:
    return DatasetRegistry.default().get(dataset_id)
