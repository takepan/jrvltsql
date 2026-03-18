"""Parser for SLOP record - 坂路調教 (Slope Training).

Record 22 in JV-Data spec. Record length: 60 bytes.
Data spec: SLOP
Raw record type in data: "HC"
"""

from typing import Dict, List, Optional

from src.parser.base import BaseParser, FieldDef


class SLOPParser(BaseParser):
    """Parser for 坂路調教 (Slope Training) records.

    JV-Data raw record type is "HC". After parsing, RecordSpec is
    rewritten to "SLOP" to route to NL_SLOP table.
    """

    record_type = "HC"

    def parse(self, record: bytes) -> Optional[Dict]:
        """Parse HC record and rewrite RecordSpec to SLOP."""
        result = super().parse(record)
        if result is not None:
            result["RecordSpec"] = "SLOP"
        return result

    def _define_fields(self) -> List[FieldDef]:
        """Define field positions for 坂路調教 record.

        Returns:
            List of FieldDef objects with type conversion settings
        """
        return [
            FieldDef("RecordSpec", 0, 2, description="レコード種別ID"),
            FieldDef("DataKubun", 2, 1, description="データ区分"),
            FieldDef("MakeDate", 3, 8, convert_type="DATE", description="データ作成年月日"),
            FieldDef("TresenKubun", 11, 1, description="トレセン区分"),
            FieldDef("ChokyoDate", 12, 8, description="調教年月日"),
            FieldDef("ChokyoTime", 20, 4, description="調教時刻"),
            FieldDef("KettoNum", 24, 10, description="血統登録番号"),
            FieldDef("HaronTime4Total", 34, 4, description="4ハロンタイム合計(800M～0M)"),
            FieldDef("LapTime_800M_600M", 38, 3, description="ラップタイム(800M～600M)"),
            FieldDef("HaronTime3Total", 41, 4, description="3ハロンタイム合計(600M～0M)"),
            FieldDef("LapTime_600M_400M", 45, 3, description="ラップタイム(600M～400M)"),
            FieldDef("HaronTime2Total", 48, 4, description="2ハロンタイム合計(400M～0M)"),
            FieldDef("LapTime_400M_200M", 52, 3, description="ラップタイム(400M～200M)"),
            FieldDef("LapTime_200M_0M", 55, 3, description="ラップタイム(200M～0M)"),
            FieldDef("RecordDelimiter", 58, 2, description="レコード区切"),
        ]
