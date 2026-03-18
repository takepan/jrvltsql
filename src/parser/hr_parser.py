#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HRレコードパーサー: ４．払戻

JV-Data仕様書 Ver.4.9.0.1に基づく払戻レコードのパース
払戻データは配列構造になっており、全件を抽出する
"""

from typing import Dict, Optional
from src.utils.logger import get_logger


class HRParser:
    """
    HRレコードパーサー

    ４．払戻
    レコード長: 719 bytes (JV-Data仕様書 Ver.4.9.0.1による正確な長さ)
    VBテーブル名: HARAI

    配列構造 (JV-Data仕様書より):
    - 単勝払戻: 3件 (馬番2 + 払戻9 + 人気2 = 13バイト × 3 = 39バイト)
    - 複勝払戻: 5件 (馬番2 + 払戻9 + 人気2 = 13バイト × 5 = 65バイト)
    - 枠連払戻: 3件 (組合せ2 + 払戻9 + 人気2 = 13バイト × 3 = 39バイト)
    - 馬連払戻: 3件 (組合せ4 + 払戻9 + 人気3 = 16バイト × 3 = 48バイト)
    - ワイド払戻: 7件 (組合せ4 + 払戻9 + 人気3 = 16バイト × 7 = 112バイト)
    - 予備: 3件 (16バイト × 3 = 48バイト)
    - 馬単払戻: 6件 (組合せ4 + 払戻9 + 人気3 = 16バイト × 6 = 96バイト)
    - 三連複払戻: 3件 (組合せ6 + 払戻9 + 人気3 = 18バイト × 3 = 54バイト)
    - 三連単払戻: 6件 (組合せ6 + 払戻9 + 人気4 = 19バイト × 6 = 114バイト)
    """

    RECORD_TYPE = "HR"
    RECORD_LENGTH = 719  # JV-Data仕様書 Ver.4.9.0.1による正確な長さ

    def __init__(self):
        self.logger = get_logger(__name__)

    @staticmethod
    def decode_field(data: bytes) -> str:
        """バイトデータをデコードして文字列に変換"""
        try:
            # cp932でデコード、空白を除去
            return data.decode("cp932", errors="replace").strip()
        except Exception:
            return ""

    def parse(self, data: bytes) -> Optional[Dict[str, str]]:
        """
        HRレコードをパースしてフィールド辞書を返す

        Args:
            data: パース対象のバイトデータ

        Returns:
            フィールド名をキーとした辞書、エラー時はNone
        """
        try:
            # レコード長チェック（最小限のデータがあるかどうか）
            if len(data) < 100:
                self.logger.warning(
                    f"HRレコード長不足: expected>={self.RECORD_LENGTH}, actual={len(data)}"
                )
                return None

            # フィールド抽出
            result = {}
            pos = 0

            # 1. レコード種別ID (位置:1, 長さ:2)
            result["RecordSpec"] = self.decode_field(data[pos:pos+2])
            pos += 2

            # 2. データ区分 (位置:3, 長さ:1)
            result["DataKubun"] = self.decode_field(data[pos:pos+1])
            pos += 1

            # 3. データ作成年月日 (位置:4, 長さ:8)
            result["MakeDate"] = self.decode_field(data[pos:pos+8])
            pos += 8

            # 4. 開催年 (位置:12, 長さ:4)
            result["Year"] = self.decode_field(data[pos:pos+4])
            pos += 4

            # 5. 開催月日 (位置:16, 長さ:4)
            result["MonthDay"] = self.decode_field(data[pos:pos+4])
            pos += 4

            # 6. 競馬場コード (位置:20, 長さ:2)
            result["JyoCD"] = self.decode_field(data[pos:pos+2])
            pos += 2

            # 7. 開催回[第N回] (位置:22, 長さ:2)
            result["Kaiji"] = self.decode_field(data[pos:pos+2])
            pos += 2

            # 8. 開催日目[N日目] (位置:24, 長さ:2)
            result["Nichiji"] = self.decode_field(data[pos:pos+2])
            pos += 2

            # 9. レース番号 (位置:26, 長さ:2)
            result["RaceNum"] = self.decode_field(data[pos:pos+2])
            pos += 2

            # 10. 登録頭数 (位置:28, 長さ:2)
            result["TorokuTosu"] = self.decode_field(data[pos:pos+2])
            pos += 2

            # 11. 出走頭数 (位置:30, 長さ:2)
            result["SyussoTosu"] = self.decode_field(data[pos:pos+2])
            pos += 2

            # 12-20. 不成立フラグ (各1バイト × 9)
            for i in range(1, 10):
                result[f"FuseirituFlag{i}"] = self.decode_field(data[pos:pos+1])
                pos += 1

            # 21-29. 特払フラグ (各1バイト × 9)
            for i in range(1, 10):
                result[f"TokubaraiFlag{i}"] = self.decode_field(data[pos:pos+1])
                pos += 1

            # 30-38. 返還フラグ (各1バイト × 9)
            for i in range(1, 10):
                result[f"HenkanFlag{i}"] = self.decode_field(data[pos:pos+1])
                pos += 1

            # 39-66. 返還馬番情報 (各1バイト × 28)
            for i in range(1, 29):
                result[f"HenkanUma{i}"] = self.decode_field(data[pos:pos+1])
                pos += 1

            # 67-74. 返還枠番情報 (各1バイト × 8)
            for i in range(1, 9):
                result[f"HenkanWaku{i}"] = self.decode_field(data[pos:pos+1])
                pos += 1

            # 75-82. 返還同枠情報 (各1バイト × 8) - JV-Data仕様書: 位置95, 8バイト
            for i in range(1, 9):
                result[f"HenkanDoWaku{i}"] = self.decode_field(data[pos:pos+1])
                pos += 1

            # ここから配列データ
            # pos = 102 at this point (JV-Data仕様書: 単勝払戻は位置103から、0始まりで102)

            # 単勝払戻 (3件配列: 馬番2 + 払戻9 + 人気2 = 13バイト × 3 = 39バイト)
            tan_base = pos
            for i in range(3):
                suffix = "" if i == 0 else str(i + 1)
                ep = tan_base + i * 13
                result[f"TanUmaban{suffix}"] = self.decode_field(data[ep:ep+2])
                result[f"TanPay{suffix}"] = self.decode_field(data[ep+2:ep+11])
                result[f"TanNinki{suffix}"] = self.decode_field(data[ep+11:ep+13])
            pos += 39  # 3件分

            # 複勝払戻 (5件配列: 馬番2 + 払戻9 + 人気2 = 13バイト × 5 = 65バイト)
            # 全5件を抽出
            fuku_base = pos
            for i in range(5):
                suffix = "" if i == 0 else str(i + 1)
                ep = fuku_base + i * 13
                result[f"FukuUmaban{suffix}"] = self.decode_field(data[ep:ep+2])
                result[f"FukuPay{suffix}"] = self.decode_field(data[ep+2:ep+11])
                result[f"FukuNinki{suffix}"] = self.decode_field(data[ep+11:ep+13])
            pos += 65  # 5件分

            # 枠連払戻 (3件配列: 組合せ2 + 払戻9 + 人気2 = 13バイト × 3 = 39バイト)
            waku_base = pos
            for i in range(3):
                suffix = "" if i == 0 else str(i + 1)
                ep = waku_base + i * 13
                result[f"WakuKumi{suffix}"] = self.decode_field(data[ep:ep+2])
                result[f"WakuPay{suffix}"] = self.decode_field(data[ep+2:ep+11])
                result[f"WakuNinki{suffix}"] = self.decode_field(data[ep+11:ep+13])
            pos += 39  # 3件分

            # 馬連払戻 (3件配列: 組合せ4 + 払戻9 + 人気3 = 16バイト × 3 = 48バイト)
            umaren_base = pos
            for i in range(3):
                suffix = "" if i == 0 else str(i + 1)
                ep = umaren_base + i * 16
                result[f"UmarenKumi{suffix}"] = self.decode_field(data[ep:ep+4])
                result[f"UmarenPay{suffix}"] = self.decode_field(data[ep+4:ep+13])
                result[f"UmarenNinki{suffix}"] = self.decode_field(data[ep+13:ep+16])
            pos += 48  # 3件分

            # ワイド払戻 (7件配列: 組合せ4 + 払戻9 + 人気3 = 16バイト × 7 = 112バイト)
            wide_base = pos
            for i in range(7):
                suffix = "" if i == 0 else str(i + 1)
                ep = wide_base + i * 16
                result[f"WideKumi{suffix}"] = self.decode_field(data[ep:ep+4])
                result[f"WidePay{suffix}"] = self.decode_field(data[ep+4:ep+13])
                result[f"WideNinki{suffix}"] = self.decode_field(data[ep+13:ep+16])
            pos += 112  # 7件分

            # 予備 (3件配列: 16バイト × 3 = 48バイト) - スキップのみ
            pos += 48

            # 馬単払戻 (6件配列: 組合せ4 + 払戻9 + 人気3 = 16バイト × 6 = 96バイト)
            umatan_base = pos
            for i in range(6):
                suffix = "" if i == 0 else str(i + 1)
                ep = umatan_base + i * 16
                result[f"UmatanKumi{suffix}"] = self.decode_field(data[ep:ep+4])
                result[f"UmatanPay{suffix}"] = self.decode_field(data[ep+4:ep+13])
                result[f"UmatanNinki{suffix}"] = self.decode_field(data[ep+13:ep+16])
            pos += 96  # 6件分

            # 三連複払戻 (3件配列: 組合せ6 + 払戻9 + 人気3 = 18バイト × 3 = 54バイト)
            sanrenfuku_base = pos
            for i in range(3):
                suffix = "" if i == 0 else str(i + 1)
                ep = sanrenfuku_base + i * 18
                result[f"SanrenfukuKumi{suffix}"] = self.decode_field(data[ep:ep+6])
                result[f"SanrenfukuPay{suffix}"] = self.decode_field(data[ep+6:ep+15])
                result[f"SanrenfukuNinki{suffix}"] = self.decode_field(data[ep+15:ep+18])
            pos += 54  # 3件分

            # 三連単払戻 (6件配列: 組合せ6 + 払戻9 + 人気4 = 19バイト × 6 = 114バイト)
            sanrentan_base = pos
            for i in range(6):
                suffix = "" if i == 0 else str(i + 1)
                ep = sanrentan_base + i * 19
                result[f"SanrentanKumi{suffix}"] = self.decode_field(data[ep:ep+6])
                result[f"SanrentanPay{suffix}"] = self.decode_field(data[ep+6:ep+15])
                result[f"SanrentanNinki{suffix}"] = self.decode_field(data[ep+15:ep+19])
            pos += 114  # 6件分

            # レコード区切 (2バイト)
            if pos < len(data):
                result["RecordDelimiter"] = self.decode_field(data[pos:pos+2])

            return result

        except Exception as e:
            self.logger.error(f"HRレコードパース中にエラー: {e}")
            return None
