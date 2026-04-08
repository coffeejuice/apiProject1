from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.services.materials.models import MaterialSource, MaterialVisualPayload, ParsedMaterialFile


class MaterialSourceParser(ABC):
    source: MaterialSource
    supported_suffixes: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedMaterialFile:
        raise NotImplementedError

    @abstractmethod
    def build_visual_payload(
        self,
        material_id: int,
        parsed: ParsedMaterialFile,
    ) -> MaterialVisualPayload:
        raise NotImplementedError
