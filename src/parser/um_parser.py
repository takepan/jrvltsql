#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UMレコードパーサー: １３．競走馬マスタ

JV-Data仕様書(Ver.4.9.0.1): レコード長1609バイト

注: pywin32のCOM BSTR変換でNULLパディングバイトが消失するため、
    実際に受け取るcp932バイト列は1577バイト程度になる。
    (HansyokuNum 10桁中の未使用NULLパディング × 14エントリ = ~28バイト消失、
     BreederCode/BreederName のNULLパディングで ~4バイト消失)
    このため、ketto3info内ではバイトオフセットではなく
    数字/非数字の境界で動的にフィールドを区切る。
"""

from typing import Dict, Optional
from src.utils.logger import get_logger


class UMParser:
    """
    UMレコードパーサー

    １３．競走馬マスタ
    レコード長: 1609 bytes (仕様)
    VBテーブル名: UMA
    """

    RECORD_TYPE = "UM"
    RECORD_LENGTH = 1609

    def __init__(self):
        self.logger = get_logger(__name__)

    @staticmethod
    def decode_field(data: bytes) -> str:
        """バイトデータをデコードして文字列に変換"""
        try:
            return data.decode("cp932", errors="replace").strip()
        except Exception:
            return ""

    @staticmethod
    def _find_next_digit_run(data: bytes, start: int, min_digits: int = 8) -> int:
        """data[start:]から連続数字列(min_digits桁以上)の開始位置を返す。見つからなければlen(data)。"""
        i = start
        while i < len(data):
            if 0x30 <= data[i] <= 0x39:
                # 数字の連続長を数える
                j = i
                while j < len(data) and 0x30 <= data[j] <= 0x39:
                    j += 1
                if j - i >= min_digits:
                    return i
                i = j
            else:
                # cp932 2バイト文字のリードバイトならスキップ
                b = data[i]
                if (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC) and i + 1 < len(data):
                    i += 2
                else:
                    i += 1
        return len(data)

    @classmethod
    def _parse_ketto_entries(cls, data: bytes, count: int = 14):
        """ketto3info (HansyokuNum + Bamei) × count をパースする。

        NULLパディング消失により固定オフセットが使えないため、
        「次の長い数字列(>=8桁)の手前までがBamei」という方法で区切る。
        """
        entries = []
        pos = 0
        for i in range(count):
            # HansyokuNum: 先頭から数字を読む
            num_end = pos
            while num_end < len(data) and 0x30 <= data[num_end] <= 0x39:
                num_end += 1
            num_val = data[pos:num_end].decode("ascii", errors="replace").strip()

            # Bamei: 次のHansyokuNum(8桁以上の数字列)の手前まで
            if i < count - 1:
                next_num_start = cls._find_next_digit_run(data, num_end, 8)
            else:
                # 最後のエントリ: 残り全部がBamei (最大36バイト)
                next_num_start = min(num_end + 36, len(data))

            name_val = data[num_end:next_num_start].decode("cp932", errors="replace").strip()
            entries.append((num_val, name_val))
            pos = next_num_start

        return entries, pos

    def parse(self, data: bytes) -> Optional[Dict[str, str]]:
        """UMレコードをパースしてフィールド辞書を返す。"""
        try:
            if len(data) < 200:
                self.logger.warning(
                    f"UMレコード長不足: expected>=200, actual={len(data)}"
                )

            result = {}

            # 1-17: 固定長フィールド (バイトオフセット 0-203, NULLなし)
            result["RecordSpec"] = self.decode_field(data[0:2])
            result["DataKubun"] = self.decode_field(data[2:3])
            result["MakeDate"] = self.decode_field(data[3:11])
            result["KettoNum"] = self.decode_field(data[11:21])
            result["DelKubun"] = self.decode_field(data[21:22])
            result["RegDate"] = self.decode_field(data[22:30])
            result["DelDate"] = self.decode_field(data[30:38])
            result["BirthDate"] = self.decode_field(data[38:46])
            result["Bamei"] = self.decode_field(data[46:82])
            result["BameiKana"] = self.decode_field(data[82:118])
            result["BameiEng"] = self.decode_field(data[118:178])
            result["ZaikyuFlag"] = self.decode_field(data[178:179])
            result["Reserved"] = self.decode_field(data[179:198])
            result["UmaKigoCD"] = self.decode_field(data[198:200])
            result["SexCD"] = self.decode_field(data[200:201])
            result["HinsyuCD"] = self.decode_field(data[201:202])
            result["KeiroCD"] = self.decode_field(data[202:204])

            # 18-31: 3代血統情報 繰返14回
            # HansyokuNum(仕様10バイト) + Bamei(仕様36バイト)
            # NULLパディング消失により固定オフセットが使えないため、
            # 「次の8桁以上数字列の手前までがBamei」で動的分割
            ketto_data = data[204:]
            entries, ketto_consumed = self._parse_ketto_entries(ketto_data, 14)
            for i, (num_val, name_val) in enumerate(entries, 1):
                result[f"Ketto3InfoHansyokuNum{i}"] = num_val
                result[f"Ketto3InfoBamei{i}"] = name_val
            pos = 204 + ketto_consumed

            # 32-40: 後続フィールド（posベースで読み進める）
            # TozaiCD (1)
            result["TozaiCD"] = self.decode_field(data[pos:pos+1])
            pos += 1

            # ChokyosiCode (5)
            result["ChokyosiCode"] = self.decode_field(data[pos:pos+5])
            pos += 5

            # ChokyosiRyakusyo (8) - 日本語を含む
            result["ChokyosiRyakusyo"] = self.decode_field(data[pos:pos+8])
            pos += 8

            # Syotai (20) - 日本語を含む
            result["Syotai"] = self.decode_field(data[pos:pos+20])
            pos += 20

            # BreederCode (仕様8バイト、NULLパディング消失の可能性)
            # 数字のみなので動的に読む
            digit_end = pos
            max_end = min(pos + 8, len(data))
            while digit_end < max_end and 0x30 <= data[digit_end] <= 0x39:
                digit_end += 1
            result["BreederCode"] = data[pos:digit_end].decode("ascii", errors="replace").strip()
            pos = digit_end

            # BreederName (仕様72バイト) - 日本語を含む
            result["BreederName"] = self.decode_field(data[pos:pos+70])
            pos += 70

            # SanchiName (20)
            result["SanchiName"] = self.decode_field(data[pos:pos+20])
            pos += 20

            # BanusiCode (6)
            result["BanusiCode"] = self.decode_field(data[pos:pos+6])
            pos += 6

            # BanusiName (64)
            result["BanusiName"] = self.decode_field(data[pos:pos+64])
            pos += 64

            # 41-46: 賞金累計 (各9バイト、数字のみ)
            result["RuikeiHonsyoHeiti"] = self.decode_field(data[pos:pos+9])
            pos += 9
            result["RuikeiHonsyoSyogai"] = self.decode_field(data[pos:pos+9])
            pos += 9
            result["RuikeiFukaHeichi"] = self.decode_field(data[pos:pos+9])
            pos += 9
            result["RuikeiFukaSyogai"] = self.decode_field(data[pos:pos+9])
            pos += 9
            result["RuikeiSyutokuHeichi"] = self.decode_field(data[pos:pos+9])
            pos += 9
            result["RuikeiSyutokuSyogai"] = self.decode_field(data[pos:pos+9])
            pos += 9

            # 47-73: 着回数グループ (すべて数字3バイト × 繰返)
            for i in range(1, 7):
                result[f"SogoChakukaisu{i}"] = self.decode_field(data[pos:pos+3])
                pos += 3

            for i in range(1, 7):
                result[f"ChuoChakukaisu{i}"] = self.decode_field(data[pos:pos+3])
                pos += 3

            for ba_idx in range(1, 8):
                for i in range(1, 7):
                    result[f"Ba{ba_idx}Chakukaisu{i}"] = self.decode_field(data[pos:pos+3])
                    pos += 3

            for j in range(1, 13):
                for i in range(1, 7):
                    result[f"Jyotai{j}Chakukaisu{i}"] = self.decode_field(data[pos:pos+3])
                    pos += 3

            for k in range(1, 7):
                for i in range(1, 7):
                    result[f"Kyori{k}Chakukaisu{i}"] = self.decode_field(data[pos:pos+3])
                    pos += 3

            # 74. 脚質傾向 (繰返4, 各3バイト)
            for i in range(1, 5):
                result[f"Kyakusitu{i}"] = self.decode_field(data[pos:pos+3])
                pos += 3

            # 75. 登録レース数 (3バイト)
            result["TorokuRacesu"] = self.decode_field(data[pos:pos+3])

            return result

        except Exception as e:
            self.logger.error(f"UMレコードパース中にエラー: {e}")
            return None
