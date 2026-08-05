"""Dataset loading and evaluation dataset domain objects.

Real evaluation content enters the platform through dataset
loaders, is represented by EvaluationDataset instances, and is
resolved for runs through dataset stores.
"""

from app.evaluation.data.dataset import DatasetItem, EvaluationDataset
from app.evaluation.data.loaders import (
    DatasetLoader,
    DatasetLoadError,
    DictDatasetLoader,
    JsonDatasetLoader,
    JsonlDatasetLoader,
    dataset_from_items,
)
from app.evaluation.data.store import (
    DatasetNotFoundError,
    DatasetStore,
    InMemoryDatasetStore,
)

__all__ = [
    "DatasetItem",
    "DatasetLoadError",
    "DatasetLoader",
    "DatasetNotFoundError",
    "DatasetStore",
    "DictDatasetLoader",
    "EvaluationDataset",
    "InMemoryDatasetStore",
    "JsonDatasetLoader",
    "JsonlDatasetLoader",
    "dataset_from_items",
]
