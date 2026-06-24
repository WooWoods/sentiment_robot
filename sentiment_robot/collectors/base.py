"""Collector abstract base class."""

from abc import ABC, abstractmethod


class BaseCollector(ABC):
    @abstractmethod
    def run(self) -> list[dict]:
        """Fetch data and return list of result dicts.

        Each dict must have:
          - source: str       (e.g. 'stocktwits', 'yfinance_news')
          - ticker: str|None  (None for macro/global)
          - content: str      (the fetched/formatted data)
          - fetched_at: str   (ISO-8601 timestamp)
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Short unique name, e.g. 'stocktwits'."""
        ...
