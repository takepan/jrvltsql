#!/usr/bin/env python
"""
HAレコードパーサー: 地方競馬 枠単票数

NV-Link (UmaConn/地方競馬DATA) の枠単票数レコードをパースする。
枠番1-8の順列組み合わせ（最大8×8=64組）ごとの売れた票数を格納。

構造:
  ヘッダー (31バイト): RecordSpec(2) + DataKubun(1) + MakeDate(8) + KaisaiDate(8)
                       + JyoCD(2) + Kaiji(2) + Nichiji(2) + RaceNum(2)
                       + TorokuTosu(2) + SyussoTosu(2)
  フラグ領域 (32バイト): HatsubaiFlag(1) + Reserved(16) + Padding(15)
  票数データ: 15バイト × N エントリー
    各エントリー: Kumi(2) + Hyosu(13)
    Kumi: 枠番の組 (例: "12"=1枠→2枠, "85"=8枠→5枠)
    Hyosu: 売れた票数
    空白エントリー: セクション区切り → スキップ
  末尾: 合計票数(13バイト) + レコード区切り(\\r\\n)

1レコードから複数行（1組1行）を生成する。
"""


from src.utils.logger import get_logger


# 枠単の有効な組番 (11-88)
VALID_WAKUTAN_KUMI = {
    f"{w1}{w2}" for w1 in range(1, 9) for w2 in range(1, 9)
}


class HAParser:
    """
    HAレコードパーサー

    地方競馬 枠単票数
    VBテーブル名: HARAI_CHIHO (地方競馬用)
    """

    RECORD_TYPE = "HA"
    ENTRY_SIZE = 15  # kumi(2) + hyosu(13)
    HEADER_SIZE = 31  # RecordSpec through SyussoTosu
    FLAG_SIZE = 32  # HatsubaiFlag + reserved + padding

    def __init__(self):
        self.logger = get_logger(__name__)

    @staticmethod
    def decode_field(data: bytes) -> str:
        """バイトデータをデコードして文字列に変換"""
        try:
            return data.decode("cp932", errors="replace").strip()
        except Exception:
            return ""

    def parse(self, data: bytes) -> "list[dict] | None":
        """
        HAレコードをパースして1組1行の辞書リストを返す。

        Returns:
            辞書のリスト。各辞書はヘッダー共通項目 + Kumi + Hyosu を持つ。
            エラー時はNone。
        """
        try:
            # Strip trailing CRLF if present
            if data.endswith(b"\r\n"):
                data = data[:-2]
            elif data.endswith(b"\n"):
                data = data[:-1]

            if len(data) < self.HEADER_SIZE + self.FLAG_SIZE:
                self.logger.warning(
                    f"HAレコード長不足: expected>={self.HEADER_SIZE + self.FLAG_SIZE}, actual={len(data)}"
                )
                return None

            pos = 0

            # ヘッダー
            header = {}
            header["RecordSpec"] = self.decode_field(data[pos:pos + 2]); pos += 2
            header["DataKubun"] = self.decode_field(data[pos:pos + 1]); pos += 1
            header["MakeDate"] = self.decode_field(data[pos:pos + 8]); pos += 8
            header["KaisaiDate"] = self.decode_field(data[pos:pos + 8]); pos += 8
            header["JyoCD"] = self.decode_field(data[pos:pos + 2]); pos += 2
            header["Kaiji"] = self.decode_field(data[pos:pos + 2]); pos += 2
            header["Nichiji"] = self.decode_field(data[pos:pos + 2]); pos += 2
            header["RaceNum"] = self.decode_field(data[pos:pos + 2]); pos += 2
            header["TorokuTosu"] = self.decode_field(data[pos:pos + 2]); pos += 2
            header["SyussoTosu"] = self.decode_field(data[pos:pos + 2]); pos += 2

            # フラグ領域
            header["HatsubaiFlag"] = self.decode_field(data[pos:pos + 1]); pos += 1
            pos += 31  # Reserved(16) + Padding(15)

            # 票数エントリーをパース → 1組1行
            rows = []
            end = len(data)

            while pos + self.ENTRY_SIZE <= end:
                entry_str = self.decode_field(data[pos:pos + self.ENTRY_SIZE])

                # 空白エントリー → スキップ
                if not entry_str:
                    pos += self.ENTRY_SIZE
                    continue

                kumi = self.decode_field(data[pos:pos + 2])
                hyosu_str = self.decode_field(data[pos + 2:pos + self.ENTRY_SIZE])

                # 組番が枠単の範囲外なら末尾の合計
                if kumi not in VALID_WAKUTAN_KUMI:
                    try:
                        total_vote = int(self.decode_field(data[pos:]))
                    except ValueError:
                        total_vote = 0
                    for row in rows:
                        row["TotalVote"] = total_vote
                    break

                try:
                    hyosu = int(hyosu_str) if hyosu_str else 0
                except ValueError:
                    hyosu = 0

                row = dict(header)
                row["Kumi"] = kumi
                row["WakutanVote"] = hyosu
                rows.append(row)
                pos += self.ENTRY_SIZE

            # 合計行が見つからなかった場合
            for row in rows:
                row.setdefault("TotalVote", 0)

            return rows

        except Exception as e:
            self.logger.exception(f"HAレコードパース中にエラー: {e}")
            return None
