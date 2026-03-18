#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
O3レコードパーサー: ９．オッズ3（ワイド）

Source: 公式JV-Data仕様書 Ver.4.9.0.1

レコード構造:
  Header(40B) + [Kumi(4)+OddsLow(5)+OddsHigh(5)+Ninki(3)] × N組 + Vote(11) + crlf(2)
  N = max 153 (18頭なら C(18,2)=153)
"""

from typing import Dict, List, Optional
from src.utils.logger import get_logger


class O3Parser:
    """
    O3レコードパーサー

    ９．オッズ3（ワイド）
    """

    RECORD_TYPE = "O3"
    HEADER_SIZE = 40
    ENTRY_SIZE = 17  # Kumi(4) + OddsLow(5) + OddsHigh(5) + Ninki(3)
    FOOTER_SIZE = 13  # Vote(11) + crlf(2)

    def __init__(self):
        self.logger = get_logger(__name__)

    @staticmethod
    def _odds(raw):
        try:
            if not raw or not raw.strip() or '*' in raw:
                return None
            return str(int(raw) / 10)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def decode_field(data: bytes) -> str:
        try:
            return data.decode("cp932", errors="replace").strip()
        except Exception:
            return ""

    def parse(self, data: bytes) -> Optional[List[Dict[str, str]]]:
        """
        O3レコードをパースして全組合せのリストを返す

        Args:
            data: パース対象のバイトデータ (1レース分の全組合せを含む)

        Returns:
            フィールド辞書のリスト、エラー時はNone
        """
        try:
            if len(data) < self.HEADER_SIZE + self.FOOTER_SIZE:
                self.logger.warning(
                    f"O3レコード長不足: actual={len(data)}"
                )
                return None

            # ヘッダー (40B)
            header = {
                "RecordSpec": self.decode_field(data[0:2]),
                "DataKubun": self.decode_field(data[2:3]),
                "MakeDate": self.decode_field(data[3:11]),
                "Year": self.decode_field(data[11:15]),
                "MonthDay": self.decode_field(data[15:19]),
                "JyoCD": self.decode_field(data[19:21]),
                "Kaiji": self.decode_field(data[21:23]),
                "Nichiji": self.decode_field(data[23:25]),
                "RaceNum": self.decode_field(data[25:27]),
                "HassoTime": self.decode_field(data[27:35]),
                "TorokuTosu": self.decode_field(data[35:37]),
                "SyussoTosu": self.decode_field(data[37:39]),
                "WideFlag": self.decode_field(data[39:40]),
            }

            # エントリ数算出
            num_entries = (len(data) - self.HEADER_SIZE - self.FOOTER_SIZE) // self.ENTRY_SIZE

            # フッター (Vote)
            vote_offset = self.HEADER_SIZE + num_entries * self.ENTRY_SIZE
            vote = self.decode_field(data[vote_offset:vote_offset + 11]) or None

            # 各エントリをパース
            results = []
            for i in range(num_entries):
                pos = self.HEADER_SIZE + i * self.ENTRY_SIZE
                kumi = self.decode_field(data[pos:pos + 4])

                if not kumi or kumi == "0" * len(kumi):
                    continue

                row = dict(header)
                row["Kumi"] = kumi
                row["OddsLow"] = self._odds(self.decode_field(data[pos + 4:pos + 9]))
                row["OddsHigh"] = self._odds(self.decode_field(data[pos + 9:pos + 14]))
                row["Ninki"] = self.decode_field(data[pos + 14:pos + 17])
                row["Vote"] = vote
                results.append(row)

            return results if results else None

        except Exception as e:
            self.logger.error(f"O3レコードパース中にエラー: {e}")
            return None
