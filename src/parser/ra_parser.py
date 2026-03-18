#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RAレコードパーサー: ２．レース詳細

Source: 公式JV-Data仕様書 Ver.4.9.0.1

レコード長: 1272 bytes

項番  項目名                    位置   繰返  バイト  合計
 1    レコード種別ID              1           2
 2    データ区分                  3           1
 3    データ作成年月日            4           8
 4    開催年                     12           4       PK
 5    開催月日                   16           4       PK
 6    競馬場コード               20           2       PK
 7    開催回[第N回]              22           2       PK
 8    開催日目[N日目]            24           2       PK
 9    レース番号                 26           2       PK
10    曜日コード                 28           1
11    特別競走番号               29           4
12    競走名本題                 33          60
13    競走名副題                 93          60
14    競走名カッコ内            153          60
15    競走名本題欧字            213         120
16    競走名副題欧字            333         120
17    競走名カッコ内欧字        453         120
18    競走名略称10文字          573          20
19    競走名略称6文字           593          12
20    競走名略称3文字           605           6
21    競走名区分                611           1
22    重賞回次[第N回]           612           3
23    グレードコード            615           1
24    変更前グレードコード      616           1
25    競走種別コード            617           2
26    競走記号コード            619           3
27    重量種別コード            622           1
28    競走条件コード 2歳        623           3
29    競走条件コード 3歳        626           3
30    競走条件コード 4歳        629           3
31    競走条件コード 5歳以上    632           3
32    競走条件コード 最若年     635           3
33    競走条件名称              638          60
34    距離                      698           4
35    変更前距離                702           4
36    トラックコード            706           2
37    変更前トラックコード      708           2
38    コース区分                710           2
39    変更前コース区分          712           2
40    本賞金                    714     7     8      56
41    変更前本賞金              770     5     8      40
42    付加賞金                  810     5     8      40
43    変更前付加賞金            850     3     8      24
44    発走時刻                  874           4
45    変更前発走時刻            878           4
46    登録頭数                  882           2
47    出走頭数                  884           2
48    入線頭数                  886           2
49    天候コード                888           1
50    芝馬場状態コード          889           1
51    ダート馬場状態コード      890           1
52    ラップタイム              891    25     3      75
53    障害マイルタイム          966           4
54    前3ハロン                 970           3
55    前4ハロン                 973           3
56    後3ハロン                 976           3
57    後4ハロン                 979           3
58    コーナー通過順位          982     4    72     288
59    レコード更新区分         1270           1
60    レコード区切             1271           2
"""

from typing import Dict, Optional
from src.utils.logger import get_logger


class RAParser:
    """
    RAレコードパーサー

    ２．レース詳細
    レコード長: 1272 bytes
    VBテーブル名: RACE
    """

    RECORD_TYPE = "RA"
    RECORD_LENGTH = 1272

    def __init__(self):
        self.logger = get_logger(__name__)

    @staticmethod
    def decode_field(data: bytes) -> str:
        """バイトデータをデコードして文字列に変換"""
        try:
            return data.decode("cp932", errors="replace").strip()
        except Exception:
            return ""

    def parse(self, data: bytes) -> Optional[Dict[str, str]]:
        """
        RAレコードをパースしてフィールド辞書を返す

        Args:
            data: パース対象のバイトデータ (1272B)

        Returns:
            フィールド名をキーとした辞書、エラー時はNone
        """
        try:
            if len(data) < self.RECORD_LENGTH:
                self.logger.warning(
                    f"RAレコード長不足: expected={self.RECORD_LENGTH}, actual={len(data)}"
                )

            result = {}

            # 1. レコード種別ID (位置:1, 長さ:2)
            result["RecordSpec"] = self.decode_field(data[0:2])

            # 2. データ区分 (位置:3, 長さ:1)
            result["DataKubun"] = self.decode_field(data[2:3])

            # 3. データ作成年月日 (位置:4, 長さ:8)
            result["MakeDate"] = self.decode_field(data[3:11])

            # 4. 開催年 (位置:12, 長さ:4)
            result["Year"] = self.decode_field(data[11:15])

            # 5. 開催月日 (位置:16, 長さ:4)
            result["MonthDay"] = self.decode_field(data[15:19])

            # 6. 競馬場コード (位置:20, 長さ:2)
            result["JyoCD"] = self.decode_field(data[19:21])

            # 7. 開催回[第N回] (位置:22, 長さ:2)
            result["Kaiji"] = self.decode_field(data[21:23])

            # 8. 開催日目[N日目] (位置:24, 長さ:2)
            result["Nichiji"] = self.decode_field(data[23:25])

            # 9. レース番号 (位置:26, 長さ:2)
            result["RaceNum"] = self.decode_field(data[25:27])

            # 10. 曜日コード (位置:28, 長さ:1)
            result["YoubiCD"] = self.decode_field(data[27:28])

            # 11. 特別競走番号 (位置:29, 長さ:4)
            result["TokuNum"] = self.decode_field(data[28:32])

            # 12. 競走名本題 (位置:33, 長さ:60)
            result["Hondai"] = self.decode_field(data[32:92])

            # 13. 競走名副題 (位置:93, 長さ:60)
            result["Fukudai"] = self.decode_field(data[92:152])

            # 14. 競走名カッコ内 (位置:153, 長さ:60)
            result["Kakko"] = self.decode_field(data[152:212])

            # 15. 競走名本題欧字 (位置:213, 長さ:120)
            result["HondaiEng"] = self.decode_field(data[212:332])

            # 16. 競走名副題欧字 (位置:333, 長さ:120)
            result["FukudaiEng"] = self.decode_field(data[332:452])

            # 17. 競走名カッコ内欧字 (位置:453, 長さ:120)
            result["KakkoEng"] = self.decode_field(data[452:572])

            # 18. 競走名略称10文字 (位置:573, 長さ:20)
            result["Ryakusyo10"] = self.decode_field(data[572:592])

            # 19. 競走名略称6文字 (位置:593, 長さ:12)
            result["Ryakusyo6"] = self.decode_field(data[592:604])

            # 20. 競走名略称3文字 (位置:605, 長さ:6)
            result["Ryakusyo3"] = self.decode_field(data[604:610])

            # 21. 競走名区分 (位置:611, 長さ:1)
            result["Kubun"] = self.decode_field(data[610:611])

            # 22. 重賞回次[第N回] (位置:612, 長さ:3)
            result["Nkai"] = self.decode_field(data[611:614])

            # 23. グレードコード (位置:615, 長さ:1)
            result["GradeCD"] = self.decode_field(data[614:615])

            # 24. 変更前グレードコード (位置:616, 長さ:1)
            result["GradeCDBefore"] = self.decode_field(data[615:616])

            # 25. 競走種別コード (位置:617, 長さ:2)
            result["SyubetuCD"] = self.decode_field(data[616:618])

            # 26. 競走記号コード (位置:619, 長さ:3)
            result["KigoCD"] = self.decode_field(data[618:621])

            # 27. 重量種別コード (位置:622, 長さ:1)
            result["JyuryoCD"] = self.decode_field(data[621:622])

            # 28-32. 競走条件コード (位置:623-637, 各3B)
            result["JyokenCD1"] = self.decode_field(data[622:625])
            result["JyokenCD2"] = self.decode_field(data[625:628])
            result["JyokenCD3"] = self.decode_field(data[628:631])
            result["JyokenCD4"] = self.decode_field(data[631:634])
            result["JyokenCD5"] = self.decode_field(data[634:637])

            # 33. 競走条件名称 (位置:638, 長さ:60)
            result["JyokenName"] = self.decode_field(data[637:697])

            # 34. 距離 (位置:698, 長さ:4)
            result["Kyori"] = self.decode_field(data[697:701])

            # 35. 変更前距離 (位置:702, 長さ:4)
            result["KyoriBefore"] = self.decode_field(data[701:705])

            # 36. トラックコード (位置:706, 長さ:2)
            result["TrackCD"] = self.decode_field(data[705:707])

            # 37. 変更前トラックコード (位置:708, 長さ:2)
            result["TrackCDBefore"] = self.decode_field(data[707:709])

            # 38. コース区分 (位置:710, 長さ:2)
            result["CourseKubunCD"] = self.decode_field(data[709:711])

            # 39. 変更前コース区分 (位置:712, 長さ:2)
            result["CourseKubunCDBefore"] = self.decode_field(data[711:713])

            # 40. 本賞金 (位置:714, 繰返7回, 各8B = 56B)
            # 1着～5着 + 5着3同着まで考慮し繰返し7回
            pos = 713
            for i in range(1, 8):
                result[f"Honsyokin{i}"] = self.decode_field(data[pos:pos + 8])
                pos += 8
            # pos = 713 + 56 = 769

            # 41. 変更前本賞金 (位置:770, 繰返5回, 各8B = 40B)
            for i in range(1, 6):
                result[f"HonsyokinBefore{i}"] = self.decode_field(data[pos:pos + 8])
                pos += 8
            # pos = 769 + 40 = 809

            # 42. 付加賞金 (位置:810, 繰返5回, 各8B = 40B)
            for i in range(1, 6):
                result[f"Fukasyokin{i}"] = self.decode_field(data[pos:pos + 8])
                pos += 8
            # pos = 809 + 40 = 849

            # 43. 変更前付加賞金 (位置:850, 繰返3回, 各8B = 24B)
            for i in range(1, 4):
                result[f"FukasyokinBefore{i}"] = self.decode_field(data[pos:pos + 8])
                pos += 8
            # pos = 849 + 24 = 873

            # 44. 発走時刻 (位置:874, 長さ:4)
            result["HassoTime"] = self.decode_field(data[873:877])

            # 45. 変更前発走時刻 (位置:878, 長さ:4)
            result["HassoTimeBefore"] = self.decode_field(data[877:881])

            # 46. 登録頭数 (位置:882, 長さ:2)
            result["TorokuTosu"] = self.decode_field(data[881:883])

            # 47. 出走頭数 (位置:884, 長さ:2)
            result["SyussoTosu"] = self.decode_field(data[883:885])

            # 48. 入線頭数 (位置:886, 長さ:2)
            result["NyusenTosu"] = self.decode_field(data[885:887])

            # 49. 天候コード (位置:888, 長さ:1)
            result["TenkoCD"] = self.decode_field(data[887:888])

            # 50. 芝馬場状態コード (位置:889, 長さ:1)
            result["SibaBabaCD"] = self.decode_field(data[888:889])

            # 51. ダート馬場状態コード (位置:890, 長さ:1)
            result["DirtBabaCD"] = self.decode_field(data[889:890])

            # 52. ラップタイム (位置:891, 繰返25回, 各3B = 75B)
            pos = 890
            for i in range(1, 26):
                result[f"LapTime{i}"] = self.decode_field(data[pos:pos + 3])
                pos += 3
            # pos = 890 + 75 = 965

            # 53. 障害マイルタイム (位置:966, 長さ:4)
            result["SyogaiMileTime"] = self.decode_field(data[965:969])

            # 54. 前3ハロン (位置:970, 長さ:3)
            result["Haron3F"] = self.decode_field(data[969:972])

            # 55. 前4ハロン (位置:973, 長さ:3)
            result["Haron4F"] = self.decode_field(data[972:975])

            # 56. 後3ハロン (位置:976, 長さ:3)
            result["Haron3L"] = self.decode_field(data[975:978])

            # 57. 後4ハロン (位置:979, 長さ:3)
            result["Haron4L"] = self.decode_field(data[978:981])

            # 58. コーナー通過順位 (位置:982, 繰返4回, 各72B = 288B)
            pos = 981
            for i in range(1, 5):
                result[f"Corner{i}"] = self.decode_field(data[pos:pos + 1])
                pos += 1
                result[f"Syukaisu{i}"] = self.decode_field(data[pos:pos + 1])
                pos += 1
                result[f"TsukaJyuni{i}"] = self.decode_field(data[pos:pos + 70])
                pos += 70
            # pos = 981 + 288 = 1269

            # 59. レコード更新区分 (位置:1270, 長さ:1)
            result["RecordUpKubun"] = self.decode_field(data[1269:1270])

            return result

        except Exception as e:
            self.logger.error(f"RAレコードパース中にエラー: {e}")
            return None
