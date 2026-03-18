#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DMレコードパーサー: ２８．タイム型データマイニング予想

フルストラクト (JV_DM_MINING) = 303バイトをパースし、
各馬番ごとに展開した行リストを返す。

構造:
  head(11) + id(16) = 27
  MakeHM(4) = 4
  ── pos 31 (0-indexed) ──
  MiningInfo[18]×15 = 270  (pos 31)
    Umaban(2) + DMTime(5) + DMGosaP(4) + DMGosaM(4) = 15
  crlf(2)                  (pos 301)
  Total = 303
"""

from typing import Dict, List, Optional, Union
from src.utils.logger import get_logger


class DMParser:
    """
    DMレコードパーサー（フルストラクト対応）

    ２８．タイム型データマイニング予想
    レコード長: 303 bytes (JV_DM_MINING)
    旧レコード長: 48 bytes (フラット1馬分) — 後方互換のためフォールバック対応

    parse() は List[Dict] を返す（フルストラクト時、1馬 = 1行）。
    フラットレコード時は単一 Dict を返す（後方互換）。
    """

    RECORD_TYPE = "DM"
    RECORD_LENGTH = 303       # full struct (18 horses)
    RECORD_LENGTH_FLAT = 48   # flat (1 horse)
    HEADER_SIZE = 31          # header bytes before MiningInfo array
    MAX_ENTRIES = 18          # MiningInfo[18]
    ENTRY_SIZE = 15           # Umaban(2) + DMTime(5) + DMGosaP(4) + DMGosaM(4)

    def __init__(self):
        self.logger = get_logger(__name__)

    @staticmethod
    def decode_field(data: bytes) -> str:
        try:
            return data.decode("cp932", errors="replace").strip()
        except Exception:
            return ""

    def _parse_header(self, data: bytes) -> Dict[str, str]:
        """Parse common header fields (first 31 bytes)."""
        h = {}
        h["RecordSpec"] = self.decode_field(data[0:2])
        h["DataKubun"] = self.decode_field(data[2:3])
        h["MakeDate"] = self.decode_field(data[3:11])
        h["Year"] = self.decode_field(data[11:15])
        h["MonthDay"] = self.decode_field(data[15:19])
        h["JyoCD"] = self.decode_field(data[19:21])
        h["Kaiji"] = self.decode_field(data[21:23])
        h["Nichiji"] = self.decode_field(data[23:25])
        h["RaceNum"] = self.decode_field(data[25:27])
        h["MakeHM"] = self.decode_field(data[27:31])
        return h

    def parse(self, data: bytes) -> Optional[Union[Dict[str, str], List[Dict[str, str]]]]:
        """
        DMレコードをパースする。

        303バイトのフルストラクトの場合: List[Dict] を返す（各馬1行）。
        48バイトのフラットレコードの場合: 単一 Dict を返す（後方互換）。
        """
        try:
            if len(data) >= self.RECORD_LENGTH:
                return self._parse_full(data)
            elif len(data) >= self.RECORD_LENGTH_FLAT:
                return self._parse_flat(data)
            else:
                self.logger.warning(
                    f"DMレコード長不足: actual={len(data)}"
                )
                return self._parse_flat(data)
        except Exception as e:
            self.logger.error(f"DMレコードパース中にエラー: {e}")
            return None

    def _parse_full(self, data: bytes) -> List[Dict[str, str]]:
        """Parse full 303-byte struct into multiple rows (one per horse)."""
        header = self._parse_header(data)

        rows = []
        for i in range(self.MAX_ENTRIES):
            offset = self.HEADER_SIZE + (self.ENTRY_SIZE * i)
            umaban = self.decode_field(data[offset:offset + 2])
            dmtime = self.decode_field(data[offset + 2:offset + 7])
            dmgosap = self.decode_field(data[offset + 7:offset + 11])
            dmgosam = self.decode_field(data[offset + 11:offset + 15])

            # Skip empty entries (all spaces or zeros)
            if not umaban or umaban == "00" or umaban == "0":
                continue

            row = dict(header)
            row["Umaban"] = umaban
            row["DMTime"] = dmtime
            row["DMGosaP"] = dmgosap
            row["DMGosaM"] = dmgosam
            rows.append(row)

        return rows if rows else [header]

    def _parse_flat(self, data: bytes) -> Optional[Dict[str, str]]:
        """Parse legacy 48-byte flat record (single horse)."""
        result = {}
        result["RecordSpec"] = self.decode_field(data[0:2])
        result["DataKubun"] = self.decode_field(data[2:3])
        result["MakeDate"] = self.decode_field(data[3:11])
        result["Year"] = self.decode_field(data[11:15])
        result["MonthDay"] = self.decode_field(data[15:19])
        result["JyoCD"] = self.decode_field(data[19:21])
        result["Kaiji"] = self.decode_field(data[21:23])
        result["Nichiji"] = self.decode_field(data[23:25])
        result["RaceNum"] = self.decode_field(data[25:27])
        result["MakeHM"] = self.decode_field(data[27:31])
        result["Umaban"] = self.decode_field(data[31:33])
        result["DMTime"] = self.decode_field(data[33:38])
        result["DMGosaP"] = self.decode_field(data[38:42])
        result["DMGosaM"] = self.decode_field(data[42:46])
        result["RecordDelimiter"] = self.decode_field(data[46:48])
        return result
