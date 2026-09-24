"""
Data models for museum accession identifiers.
"""

from dataclasses import dataclass


@dataclass
class AccessionID:
    year: str
    batch: str
    item: str
    part: str = ""

    @property
    def formatted_year(self) -> str:
        return self.year.zfill(4) if self.year.isdigit() else self.year

    @property
    def rest_identifier(self) -> str:
        b_pad = self.batch.zfill(2) if self.batch.isdigit() else self.batch
        i_pad = self.item.zfill(2) if self.item.isdigit() else self.item
        return f"{b_pad}.{i_pad}{self.part}"

    @property
    def full_identifier(self) -> str:
        return f"{self.formatted_year}.{self.rest_identifier}"

    def to_tuple(self) -> tuple[str, str]:
        return (self.formatted_year, self.rest_identifier)
