#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
O1レコードパーサー: ７．オッズ1（単複枠）

Source: 公式JV-Data仕様書 Ver.4.9.0.1

レコード構造 (962B):
  Header(43B):
    RecordSpec(2)+DataKubun(1)+MakeDate(8)+Year(4)+MonthDay(4)+JyoCD(2)
    +Kaiji(2)+Nichiji(2)+RaceNum(2)+HassoTime(8)+TorokuTosu(2)+SyussoTosu(2)
    +TanFlag(1)+FukuFlag(1)+WakurenFlag(1)+FukuChakubaraiKey(1)
  Tan[28]:   [Umaban(2)+Odds(4)+Ninki(2)] × 28 = 224B
  Fuku[28]:  [Umaban(2)+OddsLow(4)+OddsHigh(4)+Ninki(2)] × 28 = 336B
  Wakuren[36]: [Kumi(2)+Odds(5)+Ninki(2)] × 36 = 324B
  Footer:    TanVote(11)+FukuVote(11)+WakurenVote(11)+crlf(2) = 35B
"""

from typing import Dict, List, Optional
from src.utils.logger import get_logger


class O1Parser:
    """
    O1レコードパーサー

    ７．オッズ1（単複枠）
    """

    RECORD_TYPE = "O1"
    WAKU_RECORD_TYPE = "O1W"  # 枠連は別テーブル(NL_O1_WAKU)へルーティング
    HEADER_SIZE = 43
    TAN_ENTRY_SIZE = 8    # Umaban(2) + Odds(4) + Ninki(2)
    TAN_COUNT = 28
    FUKU_ENTRY_SIZE = 12  # Umaban(2) + OddsLow(4) + OddsHigh(4) + Ninki(2)
    FUKU_COUNT = 28
    WAKU_ENTRY_SIZE = 9   # Kumi(2) + Odds(5) + Ninki(2)
    WAKU_COUNT = 36

    # 有効な枠連組番号 (枠番1-8の組み合わせ: 11,12,...,18,22,...,28,...,88)
    VALID_KUMI = frozenset(
        f"{a}{b}" for a in range(1, 9) for b in range(a, 9)
    )

    def __init__(self):
        self.logger = get_logger(__name__)

    @staticmethod
    def _odds(raw):
        """0.1倍単位のオッズを実倍率に変換 (**** は確定後なので None)"""
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
        O1レコードをパースして全エントリのリストを返す

        単勝・複勝は同じUmaban行にマージ (RecordSpec="O1" → NL_O1)。
        枠連は別テーブル行として追加 (RecordSpec="O1W" → NL_O1_WAKU)。

        Args:
            data: パース対象のバイトデータ (962B)

        Returns:
            フィールド辞書のリスト、エラー時はNone
        """
        try:
            if len(data) < self.HEADER_SIZE:
                self.logger.warning(
                    f"O1レコード長不足: actual={len(data)}"
                )
                return None

            # ヘッダー (43B)
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
                "TanFlag": self.decode_field(data[39:40]),
                "FukuFlag": self.decode_field(data[40:41]),
                "WakurenFlag": self.decode_field(data[41:42]),
                "FukuChakubaraiKey": self.decode_field(data[42:43]),
            }

            # 各配列のオフセット
            tan_offset = self.HEADER_SIZE  # 43
            fuku_offset = tan_offset + self.TAN_COUNT * self.TAN_ENTRY_SIZE  # 43+224=267
            waku_offset = fuku_offset + self.FUKU_COUNT * self.FUKU_ENTRY_SIZE  # 267+336=603
            footer_offset = waku_offset + self.WAKU_COUNT * self.WAKU_ENTRY_SIZE  # 603+324=927

            # フッター (Vote) — 空文字は None に変換
            tan_vote = self.decode_field(data[footer_offset:footer_offset + 11]) or None
            fuku_vote = self.decode_field(data[footer_offset + 11:footer_offset + 22]) or None
            wakuren_vote = self.decode_field(data[footer_offset + 22:footer_offset + 33]) or None

            # 単勝配列 → Umaban をキーに行を構築
            rows = {}  # Umaban -> dict
            for i in range(self.TAN_COUNT):
                pos = tan_offset + i * self.TAN_ENTRY_SIZE
                umaban = self.decode_field(data[pos:pos + 2])

                if not umaban or umaban == "00" or umaban == "0":
                    continue

                row = dict(header)
                row["Umaban"] = umaban
                row["TanOdds"] = self._odds(self.decode_field(data[pos + 2:pos + 6]))
                row["TanNinki"] = self.decode_field(data[pos + 6:pos + 8])
                row["TanVote"] = tan_vote
                row["FukuVote"] = fuku_vote
                row["WakurenVote"] = wakuren_vote
                rows[umaban] = row

            # 複勝配列 → 同じUmaban行にマージ
            for i in range(self.FUKU_COUNT):
                pos = fuku_offset + i * self.FUKU_ENTRY_SIZE
                umaban = self.decode_field(data[pos:pos + 2])

                if not umaban or umaban == "00" or umaban == "0":
                    continue

                if umaban in rows:
                    rows[umaban]["FukuUmaban"] = umaban
                    rows[umaban]["FukuOddsLow"] = self._odds(self.decode_field(data[pos + 2:pos + 6]))
                    rows[umaban]["FukuOddsHigh"] = self._odds(self.decode_field(data[pos + 6:pos + 10]))
                    rows[umaban]["FukuNinki"] = self.decode_field(data[pos + 10:pos + 12])
                else:
                    # 複勝のみ存在するケース
                    row = dict(header)
                    row["Umaban"] = umaban
                    row["FukuUmaban"] = umaban
                    row["FukuOddsLow"] = self._odds(self.decode_field(data[pos + 2:pos + 6]))
                    row["FukuOddsHigh"] = self._odds(self.decode_field(data[pos + 6:pos + 10]))
                    row["FukuNinki"] = self.decode_field(data[pos + 10:pos + 12])
                    row["TanVote"] = tan_vote
                    row["FukuVote"] = fuku_vote
                    row["WakurenVote"] = wakuren_vote
                    rows[umaban] = row

            results = list(rows.values())

            # 枠連配列 → NL_O1_WAKU テーブルへ (RecordSpec="O1W")
            waku_header = {
                "RecordSpec": self.WAKU_RECORD_TYPE,
                "DataKubun": header["DataKubun"],
                "MakeDate": header["MakeDate"],
                "Year": header["Year"],
                "MonthDay": header["MonthDay"],
                "JyoCD": header["JyoCD"],
                "Kaiji": header["Kaiji"],
                "Nichiji": header["Nichiji"],
                "RaceNum": header["RaceNum"],
                "HassoTime": header["HassoTime"],
                "WakurenFlag": header["WakurenFlag"],
            }
            for i in range(self.WAKU_COUNT):
                pos = waku_offset + i * self.WAKU_ENTRY_SIZE
                kumi = self.decode_field(data[pos:pos + 2])

                if not kumi or kumi not in self.VALID_KUMI:
                    continue

                row = dict(waku_header)
                row["Kumi"] = kumi
                row["WakurenOdds"] = self._odds(self.decode_field(data[pos + 2:pos + 7]))
                row["WakurenNinki"] = self.decode_field(data[pos + 7:pos + 9])
                row["WakurenVote"] = wakuren_vote
                results.append(row)

            return results if results else None

        except Exception as e:
            self.logger.error(f"O1レコードパース中にエラー: {e}")
            return None
