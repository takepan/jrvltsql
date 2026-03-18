#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
UMレコードパーサー: １３．競走馬マスタ

JVReadが返す実データ (1577バイト) に基づいてパースする。
注: 仕様書(Ver.4.9.0.1)は1609バイトだが、JVReadの実データは1577バイト。
    差分32バイト: HansyokuNum 10→8(×14=28), BreederCode 8→6(2), BreederName 72→70(2)
"""

from typing import Dict, Optional
from src.utils.logger import get_logger


class UMParser:
    """
    UMレコードパーサー

    １３．競走馬マスタ
    レコード長: 1577 bytes (JVRead実データ)
    VBテーブル名: UMA
    """

    RECORD_TYPE = "UM"
    RECORD_LENGTH = 1577  # JVRead実データ

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
        UMレコードをパースしてフィールド辞書を返す

        Args:
            data: パース対象のバイトデータ

        Returns:
            フィールド名をキーとした辞書、エラー時はNone
        """
        try:
            # レコード長チェック (短いレコードも許容)
            if len(data) < 200:
                self.logger.warning(
                    f"UMレコード長不足: expected>={200}, actual={len(data)}"
                )

            # フィールド抽出
            result = {}

            # 1. レコード種別ID (位置:1, 長さ:2)
            result["RecordSpec"] = self.decode_field(data[0:2])

            # 2. データ区分 (位置:3, 長さ:1)
            result["DataKubun"] = self.decode_field(data[2:3])

            # 3. データ作成年月日 (位置:4, 長さ:8)
            result["MakeDate"] = self.decode_field(data[3:11])

            # 4. 血統登録番号 (位置:12, 長さ:10) - PRIMARY KEY
            result["KettoNum"] = self.decode_field(data[11:21])

            # 5. 競走馬抹消区分 (位置:22, 長さ:1)
            result["DelKubun"] = self.decode_field(data[21:22])

            # 6. 競走馬登録年月日 (位置:23, 長さ:8)
            result["RegDate"] = self.decode_field(data[22:30])

            # 7. 競走馬抹消年月日 (位置:31, 長さ:8)
            result["DelDate"] = self.decode_field(data[30:38])

            # 8. 生年月日 (位置:39, 長さ:8)
            result["BirthDate"] = self.decode_field(data[38:46])

            # 9. 馬名 (位置:47, 長さ:36)
            result["Bamei"] = self.decode_field(data[46:82])

            # 10. 馬名半角ｶﾅ (位置:83, 長さ:36)
            result["BameiKana"] = self.decode_field(data[82:118])

            # 11. 馬名欧字 (位置:119, 長さ:60)
            result["BameiEng"] = self.decode_field(data[118:178])

            # 12. JRA施設在きゅうフラグ (位置:179, 長さ:1)
            result["ZaikyuFlag"] = self.decode_field(data[178:179])

            # 13. 予備 (位置:180, 長さ:19)
            result["Reserved"] = self.decode_field(data[179:198])

            # 14. 馬記号コード (位置:199, 長さ:2)
            result["UmaKigoCD"] = self.decode_field(data[198:200])

            # 15. 性別コード (位置:201, 長さ:1)
            result["SexCD"] = self.decode_field(data[200:201])

            # 16. 品種コード (位置:202, 長さ:1)
            result["HinsyuCD"] = self.decode_field(data[201:202])

            # 17. 毛色コード (位置:203, 長さ:2)
            result["KeiroCD"] = self.decode_field(data[202:204])

            # 18-31. <3代血統情報> 繰返14回
            # 各: 繁殖登録番号(8) + 馬名(36) = 44バイト, 合計616バイト
            ketto_pos = 204
            for i in range(1, 15):
                result[f"Ketto3InfoHansyokuNum{i}"] = self.decode_field(data[ketto_pos:ketto_pos+8])
                result[f"Ketto3InfoBamei{i}"] = self.decode_field(data[ketto_pos+8:ketto_pos+44])
                ketto_pos += 44
            # ketto_pos = 820

            # 32. 東西所属コード (長さ:1)
            result["TozaiCD"] = self.decode_field(data[820:821])

            # 33. 調教師コード (長さ:5)
            result["ChokyosiCode"] = self.decode_field(data[821:826])

            # 34. 調教師名略称 (長さ:8)
            result["ChokyosiRyakusyo"] = self.decode_field(data[826:834])

            # 35. 招待地域名 (長さ:20)
            result["Syotai"] = self.decode_field(data[834:854])

            # 36. 生産者コード (長さ:6)
            result["BreederCode"] = self.decode_field(data[854:860])

            # 37. 生産者名(法人格無) (長さ:70) ※spec=72, JVRead=70
            result["BreederName"] = self.decode_field(data[860:930])

            # 38. 産地名 (長さ:20)
            result["SanchiName"] = self.decode_field(data[930:950])

            # 39. 馬主コード (長さ:6)
            result["BanusiCode"] = self.decode_field(data[950:956])

            # 40. 馬主名(法人格無) (長さ:64)
            result["BanusiName"] = self.decode_field(data[956:1020])

            # 41. 平地本賞金累計 (長さ:9)
            result["RuikeiHonsyoHeiti"] = self.decode_field(data[1020:1029])

            # 42. 障害本賞金累計 (長さ:9)
            result["RuikeiHonsyoSyogai"] = self.decode_field(data[1029:1038])

            # 43. 平地付加賞金累計 (長さ:9)
            result["RuikeiFukaHeichi"] = self.decode_field(data[1038:1047])

            # 44. 障害付加賞金累計 (長さ:9)
            result["RuikeiFukaSyogai"] = self.decode_field(data[1047:1056])

            # 45. 平地収得賞金累計 (長さ:9)
            result["RuikeiSyutokuHeichi"] = self.decode_field(data[1056:1065])

            # 46. 障害収得賞金累計 (長さ:9)
            result["RuikeiSyutokuSyogai"] = self.decode_field(data[1065:1074])

            # 47. 総合着回数 (繰返6, 各3バイト, 合計18)
            pos = 1074
            for i in range(1, 7):
                result[f"SogoChakukaisu{i}"] = self.decode_field(data[pos:pos+3])
                pos += 3

            # 48. 中央合計着回数 (繰返6, 各3バイト, 合計18)
            for i in range(1, 7):
                result[f"ChuoChakukaisu{i}"] = self.decode_field(data[pos:pos+3])
                pos += 3

            # 49-55. 馬場別着回数 (各繰返6, 各3バイト, 7グループ)
            for ba_idx in range(1, 8):
                for i in range(1, 7):
                    result[f"Ba{ba_idx}Chakukaisu{i}"] = self.decode_field(data[pos:pos+3])
                    pos += 3

            # 56-67. 馬場状態別着回数 (各繰返6, 各3バイト, 12グループ)
            for j in range(1, 13):
                for i in range(1, 7):
                    result[f"Jyotai{j}Chakukaisu{i}"] = self.decode_field(data[pos:pos+3])
                    pos += 3

            # 68-73. 距離別着回数 (各繰返6, 各3バイト, 6グループ)
            for k in range(1, 7):
                for i in range(1, 7):
                    result[f"Kyori{k}Chakukaisu{i}"] = self.decode_field(data[pos:pos+3])
                    pos += 3

            # 74. 脚質傾向 (繰返4, 各3バイト, 合計12)
            for i in range(1, 5):
                result[f"Kyakusitu{i}"] = self.decode_field(data[pos:pos+3])
                pos += 3

            # 75. 登録レース数 (長さ:3) ※1バイト数値+CRLF2バイト
            result["TorokuRacesu"] = self.decode_field(data[pos:pos+3])

            return result

        except Exception as e:
            self.logger.error(f"UMレコードパース中にエラー: {e}")
            return None
