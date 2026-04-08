from __future__ import annotations

import logging
from pathlib import Path

from app.services.materials.models import MaterialSource, MaterialVisualPayload, ParsedMaterialFile
from app.services.materials.parsers.base import MaterialSourceParser
from app.services.materials.parsers.deform.diagrams import build_deform_material_diagrams
from app.services.materials.parsers.deform.section_readers import (
    parse_flow_stress_surface,
    parse_mtname,
    parse_scalar_value,
    parse_temperature_curve,
    split_deform_sections,
)


LOGGER = logging.getLogger(__name__)


class DeformMaterialParser(MaterialSourceParser):
    source = MaterialSource.DEFORM
    supported_suffixes = (".key", ".KEY")

    def parse(self, file_path: Path) -> ParsedMaterialFile:
        raw_lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        sections = split_deform_sections(raw_lines)

        parsed = ParsedMaterialFile(
            source=self.source,
            file_name=file_path.name,
            display_name=parse_mtname(sections.get("MTNAME")),
            vendor_metadata={
                "format": "DEFORM KEY",
                "section_keys": sorted(sections.keys()),
            },
            raw_sections={key: section.lines[:] for key, section in sections.items()},
        )

        flow_stress = self._safe_parse_flow_stress(sections)
        if flow_stress is not None:
            parsed.surfaces[flow_stress.key] = flow_stress

        for curve in self._parse_curves(sections):
            parsed.curves[curve.key] = curve

        mech_to_heat = parse_scalar_value(sections.get("FRAE2H"))
        if mech_to_heat is not None:
            parsed.scalars["mechanical_to_heat_factor"] = mech_to_heat

        mass_density = parse_scalar_value(sections.get("MASDEN"))
        if mass_density is not None:
            parsed.scalars["mass_density"] = mass_density

        material_density = parse_scalar_value(sections.get("MATDEN"))
        if material_density is not None:
            parsed.scalars["material_density"] = material_density

        return parsed

    def build_visual_payload(
        self,
        material_id: int,
        parsed: ParsedMaterialFile,
    ) -> MaterialVisualPayload:
        return MaterialVisualPayload(
            material_id=material_id,
            source=self.source,
            file_name=parsed.file_name,
            diagrams=build_deform_material_diagrams(parsed),
        )

    def _parse_curves(self, sections: dict[str, object]):
        curve_configs = (
            ("YOUNG", "young", "Young's Modulus", "Young's Modulus"),
            ("POISON", "poisson", "Poisson Ratio", "Poisson Ratio"),
            ("EXPAND", "thermal_expansion", "Thermal Expansion", "Thermal Expansion"),
            ("THRCND", "thermal_conductivity", "Thermal Conductivity", "Thermal Conductivity"),
            ("HEATCP", "heat_capacity", "Heat Capacity", "Heat Capacity"),
        )

        curves = []
        for section_key, curve_key, title, value_label in curve_configs:
            curve = parse_temperature_curve(
                sections.get(section_key),
                curve_key=curve_key,
                title=title,
                value_label=value_label,
            )
            if curve is not None:
                curves.append(curve)
        return curves

    def _safe_parse_flow_stress(self, sections: dict[str, object]):
        try:
            return parse_flow_stress_surface(sections.get("FSTRES"))
        except Exception:  # pragma: no cover - defensive fallback for partial files
            LOGGER.exception("Failed to parse DEFORM flow stress section")
            return None
