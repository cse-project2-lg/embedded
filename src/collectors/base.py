from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseCollector(ABC):
    """센서 수집기의 공통 인터페이스."""

    @abstractmethod
    def read(self) -> Dict[str, Any]:
        """센서 데이터를 한 번 읽어서 dict로 반환한다."""
        raise NotImplementedError
