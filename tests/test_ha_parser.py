"""Unit tests for HA (地方競馬 枠単票数) parser."""

import pytest
from src.parser.ha_parser import HAParser


class TestHAParser:
    """HAParser tests."""

    def setup_method(self):
        self.parser = HAParser()

    def _build_record(
        self,
        record_spec=b"HA",
        data_kubun=b"1",
        make_date=b"20240101",
        kaisai_date=b"20240115",
        jyo_cd=b"10",
        kaiji=b"01",
        nichiji=b"02",
        race_num=b"05",
        toroku_tosu=b"12",
        syusso_tosu=b"11",
        hatsubai_flag=b"1",
        reserved=b"\x00" * 16 + b" " * 15,
        entries=None,
    ):
        """Build a test HA record."""
        header = (
            record_spec
            + data_kubun
            + make_date
            + kaisai_date
            + jyo_cd
            + kaiji
            + nichiji
            + race_num
            + toroku_tosu
            + syusso_tosu
        )
        assert len(header) == 31

        flags = hatsubai_flag + reserved
        assert len(flags) == 32

        if entries is None:
            # Default: 3 枠単エントリー
            entries = (
                b"12" + b"         1000"   # 1枠→2枠, 1000票
                + b"13" + b"         2500"  # 1枠→3枠, 2500票
                + b"21" + b"          500"  # 2枠→1枠, 500票
            )

        body = header + flags + entries + b"\r\n"
        return body

    def test_basic_parse(self):
        """Test basic HA record parsing - returns list of rows."""
        record = self._build_record()
        rows = self.parser.parse(record)

        assert rows is not None
        assert isinstance(rows, list)
        assert len(rows) == 3

        # 全行にヘッダー情報が含まれる
        for row in rows:
            assert row["RecordSpec"] == "HA"
            assert row["DataKubun"] == "1"
            assert row["MakeDate"] == "20240101"
            assert row["KaisaiDate"] == "20240115"
            assert row["JyoCD"] == "10"
            assert row["Kaiji"] == "01"
            assert row["Nichiji"] == "02"
            assert row["RaceNum"] == "05"
            assert row["TorokuTosu"] == "12"
            assert row["SyussoTosu"] == "11"
            assert row["HatsubaiFlag"] == "1"

    def test_kumi_and_vote(self):
        """Test Kumi and WakutanVote extraction."""
        record = self._build_record()
        rows = self.parser.parse(record)

        assert rows[0]["Kumi"] == "12"
        assert rows[0]["WakutanVote"] == 1000
        assert rows[1]["Kumi"] == "13"
        assert rows[1]["WakutanVote"] == 2500
        assert rows[2]["Kumi"] == "21"
        assert rows[2]["WakutanVote"] == 500
        # TotalVote defaults to 0 when no total row
        for row in rows:
            assert row["TotalVote"] == 0

    def test_all_8x8_combinations(self):
        """Test with full 64 combinations (8枠 × 8枠)."""
        entries = b""
        for w1 in range(1, 9):
            for w2 in range(1, 9):
                kumi = f"{w1}{w2}".encode()
                hyosu = f"{w1 * 100 + w2:13d}".encode()
                entries += kumi + hyosu

        record = self._build_record(entries=entries)
        rows = self.parser.parse(record)

        assert len(rows) == 64
        assert rows[0]["Kumi"] == "11"
        assert rows[0]["WakutanVote"] == 101
        assert rows[63]["Kumi"] == "88"
        assert rows[63]["WakutanVote"] == 808

    def test_skip_blank_entries(self):
        """Test that blank entries are skipped."""
        entries = (
            b"12" + b"          100"
            + b" " * 15               # blank → skip
            + b"34" + b"          200"
        )
        record = self._build_record(entries=entries)
        rows = self.parser.parse(record)

        assert len(rows) == 2
        assert rows[0]["Kumi"] == "12"
        assert rows[1]["Kumi"] == "34"

    def test_empty_record(self):
        """Test with no entries (all spaces)."""
        entries = b" " * 60
        record = self._build_record(entries=entries)
        rows = self.parser.parse(record)

        assert rows is not None
        assert len(rows) == 0

    def test_record_too_short(self):
        """Test with record shorter than minimum."""
        result = self.parser.parse(b"HA" + b"\x00" * 10)
        assert result is None

    def test_record_with_lf_ending(self):
        """Test record ending with just \\n."""
        entries = b"12" + b"          100"
        body = (
            b"HA" + b"1" + b"20240101" + b"20240115"
            + b"10" + b"01" + b"02" + b"05" + b"12" + b"11"
            + b"1" + b"\x00" * 16 + b" " * 15
            + entries + b"\n"
        )
        rows = self.parser.parse(body)
        assert rows is not None
        assert len(rows) == 1

    def test_decode_field_cp932(self):
        """Test decode_field with cp932 encoding."""
        assert HAParser.decode_field(b"  test  ") == "test"
        assert HAParser.decode_field(b"") == ""
        assert HAParser.decode_field(b"   ") == ""

    def test_parser_attributes(self):
        """Test parser class attributes."""
        assert self.parser.RECORD_TYPE == "HA"
        assert self.parser.ENTRY_SIZE == 15
        assert self.parser.HEADER_SIZE == 31
