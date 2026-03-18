#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WFレコードパーサー: ３０．重勝式(WIN5)

JV-Data仕様書 Ver.4.9.0.1に基づく重勝式レコードのパース
払戻データは配列構造(最大243件)になっており、非空エントリのみ抽出する
"""

from typing import Dict, Optional
from src.utils.logger import get_logger


class WFParser:
    """
    WFレコードパーサー

    ３０．重勝式(WIN5)
    レコード長: 7215 bytes (JV-Data仕様書 Ver.4.9.0.1による正確な長さ)
    VBテーブル名: JYUSYOSIKI

    配列構造 (JV-Data仕様書より):
    - 有効票数: 5件 (11バイト × 5 = 55バイト)
    - 払戻情報: 243件 (組番10 + 払戻金9 + 的中票数10 = 29バイト × 243 = 7047バイト)
    """

    RECORD_TYPE = "WF"
    RECORD_LENGTH = 7215

    def __init__(self):
        self.logger = get_logger(__name__)

    @staticmethod
    def decode_field(data: bytes) -> str:
        """バイトデータをデコードして文字列に変換"""
        try:
            # CP932でデコード、空白を除去
            return data.decode("cp932", errors="replace").strip()
        except Exception:
            return ""

    def parse(self, data: bytes) -> Optional[Dict[str, str]]:
        """
        WFレコードをパースしてフィールド辞書を返す

        Args:
            data: パース対象のバイトデータ

        Returns:
            フィールド名をキーとした辞書、エラー時はNone
        """
        try:
            # レコード長チェック
            if len(data) < self.RECORD_LENGTH:
                self.logger.warning(
                    f"WFレコード長不足: expected={self.RECORD_LENGTH}, actual={len(data)}"
                )

            # フィールド抽出
            result = {}
            pos = 0

            # 1. レコード種別ID (長さ:2)
            result["RecordSpec"] = self.decode_field(data[pos:pos+2])
            pos += 2

            # 2. データ区分 (長さ:1)
            result["DataKubun"] = self.decode_field(data[pos:pos+1])
            pos += 1

            # 3. データ作成年月日 (長さ:8)
            result["MakeDate"] = self.decode_field(data[pos:pos+8])
            pos += 8

            # 4. 開催年 (長さ:4)
            result["Year"] = self.decode_field(data[pos:pos+4])
            pos += 4

            # 5. 開催月日 (長さ:4)
            result["MonthDay"] = self.decode_field(data[pos:pos+4])
            pos += 4

            # 6. 予備 (長さ:2)
            result["Yobi1"] = self.decode_field(data[pos:pos+2])
            pos += 2

            # 7-11. 重勝式対象レース情報 × 5 (各8バイト)
            for i in range(5):
                result[f"RaceInfo{i+1}"] = self.decode_field(data[pos:pos+8])
                pos += 8

            # 12. 予備 (長さ:6)
            result["Yobi2"] = self.decode_field(data[pos:pos+6])
            pos += 6

            # 13. 重勝式発売票数 (長さ:11)
            result["HatubaiHyosu"] = self.decode_field(data[pos:pos+11])
            pos += 11

            # 14-18. 有効票数 × 5 (各11バイト)
            for i in range(5):
                suffix = "" if i == 0 else str(i + 1)
                result[f"YukoHyosu{suffix}"] = self.decode_field(data[pos:pos+11])
                pos += 11

            # 19. 返還フラグ (長さ:1)
            result["HenkanFlag"] = self.decode_field(data[pos:pos+1])
            pos += 1

            # 20. 不成立フラグ (長さ:1)
            result["FuseirituFlag"] = self.decode_field(data[pos:pos+1])
            pos += 1

            # 21. 的中無フラグ (長さ:1)
            result["TekichuNasiFlag"] = self.decode_field(data[pos:pos+1])
            pos += 1

            # 22. キャリーオーバー金額初期 (長さ:15)
            result["CarryOverStart"] = self.decode_field(data[pos:pos+15])
            pos += 15

            # 23. キャリーオーバー金額残高 (長さ:15)
            result["CarryOverBalance"] = self.decode_field(data[pos:pos+15])
            pos += 15

            # 24. 払戻情報 × 243 (各29バイト: 組番10 + 払戻金9 + 的中票数10)
            # 非空エントリのみ最大10件を格納
            pay_base = pos
            pay_count = 0
            for i in range(243):
                ep = pay_base + i * 29
                kumi = self.decode_field(data[ep:ep+10])
                pay = self.decode_field(data[ep+10:ep+19])
                tekichu = self.decode_field(data[ep+19:ep+29])

                if kumi or pay or tekichu:
                    pay_count += 1
                    if pay_count <= 10:
                        suffix = "" if pay_count == 1 else str(pay_count)
                        result[f"Kumi{suffix}"] = kumi
                        result[f"PayJyushosiki{suffix}"] = pay
                        result[f"TekichuHyosu{suffix}"] = tekichu
            pos = pay_base + 29 * 243

            # 25. レコード区切 (長さ:2)
            result["RecordDelimiter"] = self.decode_field(data[pos:pos+2])

            return result

        except Exception as e:
            self.logger.error(f"WFレコードパース中にエラー: {e}")
            return None
