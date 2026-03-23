"""jltsql odds コマンド — 発走時刻ベースのオッズ自動取得

発走5分以内のレースがあれば:
  → そのレースのオッズを取得 → 1分サイクル
なければ:
  → 発走前の全レースのオッズを取得
  → 直近の発走5分前 or 5分後までスリープ

全レース確定で自動終了。
NARではrtdキャッシュファイルからも時系列オッズを読み取る。
"""

import glob
import os
import struct
import time
import zlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from src.parser.factory import ParserFactory
from src.cli.fetch_today import (
    _sanitize, _generic_upsert, p,
    NAR_JYOCD_NAMES, JYO_NAMES,
)


# ── odds table mapping ──

ODDS_TABLE_MAP = {
    'O1': ('nl_o1', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'umaban']),
    'O1W': ('nl_o1_waku', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi']),
    'O2': ('nl_o2', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi']),
    'O3': ('nl_o3', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi']),
    'O4': ('nl_o4', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi']),
    'O5': ('nl_o5', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi']),
    'O6': ('nl_o6', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi']),
}

# 時系列テーブル (HassoTime + FetchedAt をPKに含む → 複数時点のスナップショット蓄積)
TS_TABLE_MAP = {
    'O1': ('ts_o1', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'umaban', 'hassotime', 'fetchedat']),
    'O1W': ('ts_o1_waku', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi', 'hassotime', 'fetchedat']),
    'O2': ('ts_o2', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi', 'hassotime', 'fetchedat']),
    'O3': ('ts_o3', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi', 'hassotime', 'fetchedat']),
    'O4': ('ts_o4', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi', 'hassotime', 'fetchedat']),
    'O5': ('ts_o5', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi', 'hassotime', 'fetchedat']),
    'O6': ('ts_o6', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi', 'hassotime', 'fetchedat']),
}

ODDS_TABLE_MAP_NAR = {
    k: (v[0] + '_nar', v[1]) for k, v in ODDS_TABLE_MAP.items()
}

TS_TABLE_MAP_NAR = {
    k: (v[0] + '_nar', v[1]) for k, v in TS_TABLE_MAP.items()
}

# NAR結果テーブル (0B12 rtdから取得)
NAR_RESULT_TABLE_MAP = {
    'RA': ('nl_ra_nar', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum']),
    'SE': ('nl_se_nar', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'umaban']),
    'HR': ('nl_hr_nar', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum']),
}

NAR_CACHE_DIR = r"C:\UmaConn\chiho.k-ba\data\cache"

# NARのrtdキャッシュ更新に使うspec一覧
# NVRTOpen→NVCloseすることで.rtdファイルが更新される
NAR_RTD_TRIGGER_SPECS = ["0B41", "0B42", "0B33", "0B34", "0B35", "0B36"]


# ── rtd file reading ──

def read_zip_entries(data: bytes):
    """ZIP(rtd)ファイルからエントリを読み取る"""
    entries = []
    pos = 0
    PK_SIG = b'PK\x03\x04'
    while True:
        idx = data.find(PK_SIG, pos)
        if idx == -1:
            break
        ver, flags, method, mtime, mdate, crc32_val, comp_size, uncomp_size, name_len, extra_len = \
            struct.unpack_from('<HHHHHIIIHH', data, idx + 4)
        name_start = idx + 30
        name = data[name_start:name_start + name_len].decode('cp932', errors='replace')
        data_start = name_start + name_len + extra_len
        if method == 8:
            content = zlib.decompress(data[data_start:data_start + comp_size], -15)
        elif method == 0:
            content = data[data_start:data_start + uncomp_size]
        else:
            content = b''
        entries.append((name, content))
        pos = data_start + comp_size
    return entries


def find_rtd_files(date_str: str, dataspec: str, jyocd: str = None, racenum: int = None):
    """rtdファイルのパスを検索。

    速報系(0B1x): {dataspec}{date}.rtd (日付単位)
    時系列(0B3x): {dataspec}{date}{jyocd}{rr}.rtd (レース単位)
    """
    year = date_str[:4]
    cache_dir = os.path.join(NAR_CACHE_DIR, year)
    if not os.path.isdir(cache_dir):
        return []

    if jyocd and racenum is not None:
        rr = f"{racenum:02d}"
        pattern = os.path.join(cache_dir, f"{dataspec}{date_str}{jyocd}*{rr}.rtd")
    else:
        pattern = os.path.join(cache_dir, f"{dataspec}{date_str}*.rtd")

    return sorted(glob.glob(pattern))


def trigger_rtd_cache(wrapper, date_str: str, jyocd: str, racenum: int):
    """各式別specでNVRTOpen→NVCloseしてrtdキャッシュを更新させる"""
    rr = f"{racenum:02d}"
    key = f"{date_str}{jyocd}{rr}"
    for spec in NAR_RTD_TRIGGER_SPECS:
        try:
            t0 = time.time()
            wrapper.jv_rt_open(spec, key=key)
            wrapper.jv_close()
            elapsed = time.time() - t0
            if elapsed > 5:
                p(f"  WARNING: {spec} key={key} took {elapsed:.1f}s")
        except Exception:
            try:
                wrapper.jv_close()
            except Exception:
                pass


def import_rtd_odds(conn, date_str: str, jyocd: str, racenum: int,
                    ts_table_map: dict, factory):
    """0B30 rtdファイルから全スナップショットのオッズを ts_o* にupsert"""
    fetched_at = datetime.now().strftime("%Y%m%d%H%M%S")
    paths = find_rtd_files(date_str, "0B30", jyocd, racenum)
    if not paths:
        return 0

    total = 0
    for rtd_path in paths:
        try:
            with open(rtd_path, 'rb') as f:
                data = f.read()
            entries = read_zip_entries(data)
        except Exception:
            continue

        for _, content in entries:
            if len(content) < 2:
                continue
            rt = content[:2].decode('cp932', errors='replace')
            try:
                parser = factory.get_parser(rt)
                if parser is None:
                    continue
                parsed = parser.parse(content)
                if parsed is None:
                    continue
                records = parsed if isinstance(parsed, list) else [parsed]
                for rec in records:
                    rs = rec.get("RecordSpec", rt)
                    ts_mapping = ts_table_map.get(rs)
                    if ts_mapping:
                        ts_tbl, ts_pk = ts_mapping
                        ts_rec = dict(rec)
                        ts_rec["FetchedAt"] = fetched_at
                        _generic_upsert(conn, ts_tbl, ts_rec, ts_pk)
                        total += 1
            except Exception:
                pass

    return total


def import_rtd_results(conn, date_str: str, factory):
    """0B12 rtdファイルからRA/SE/HRを読み取ってupsert (ネストzip)"""
    paths = find_rtd_files(date_str, "0B12")
    if not paths:
        return {}

    counts = {"RA": 0, "SE": 0, "HR": 0}
    for rtd_path in paths:
        try:
            with open(rtd_path, 'rb') as f:
                data = f.read()
            outer_entries = read_zip_entries(data)
        except Exception:
            continue

        for _, outer_content in outer_entries:
            # 内側のzipを展開
            inner_entries = read_zip_entries(outer_content)
            for _, content in inner_entries:
                if len(content) < 2:
                    continue
                rt = content[:2].decode('cp932', errors='replace')
                mapping = NAR_RESULT_TABLE_MAP.get(rt)
                if not mapping:
                    continue
                try:
                    parser = factory.get_parser(rt)
                    if parser is None:
                        continue
                    parsed = parser.parse(content)
                    if parsed is None:
                        continue
                    records = parsed if isinstance(parsed, list) else [parsed]
                    for rec in records:
                        tbl, pk = mapping
                        _generic_upsert(conn, tbl, rec, pk)
                        counts[rt] = counts.get(rt, 0) + 1
                except Exception:
                    pass

    return counts


def _get_table_map(is_nar: bool) -> dict:
    return ODDS_TABLE_MAP_NAR if is_nar else ODDS_TABLE_MAP


def _get_ts_table_map(is_nar: bool) -> dict:
    return TS_TABLE_MAP_NAR if is_nar else TS_TABLE_MAP


# ── race/hassotime queries ──

def get_races_with_hasso(conn, date_str: str, is_nar: bool):
    """レース一覧 + 発走時刻を取得

    Returns:
        List of (jyocd, kaiji, nichiji, racenum, hasso_datetime_or_None)
    """
    table = "nl_ra_nar" if is_nar else "nl_ra"
    year = int(date_str[:4])
    monthday = int(date_str[4:])
    rows = conn.run(f"""
        SELECT jyocd, kaiji, nichiji, racenum, hassotime
        FROM {table}
        WHERE year = :y AND monthday = :md
        ORDER BY jyocd, racenum
    """, y=year, md=monthday)

    today_date = datetime.strptime(date_str, "%Y%m%d").date()
    result = []
    for jyocd, kaiji, nichiji, racenum, hasso in rows:
        jyocd_s = str(jyocd).zfill(2) if isinstance(jyocd, int) else jyocd
        hasso_dt = None
        if hasso:
            hasso_s = str(hasso).strip().zfill(4)
            try:
                h, m = int(hasso_s[:2]), int(hasso_s[2:4])
                hasso_dt = datetime(today_date.year, today_date.month, today_date.day, h, m)
            except (ValueError, IndexError):
                pass
        result.append((jyocd_s, int(kaiji), int(nichiji), int(racenum), hasso_dt))
    return result


def get_confirmed_races(conn, date_str: str, is_nar: bool) -> Set[Tuple[str, int]]:
    """払戻確定済みレースのセット → {(jyocd, racenum)}"""
    table = "nl_hr_nar" if is_nar else "nl_hr"
    year = int(date_str[:4])
    monthday = int(date_str[4:])
    try:
        rows = conn.run(f"""
            SELECT DISTINCT jyocd, racenum FROM {table}
            WHERE year = :y AND monthday = :md
        """, y=year, md=monthday)
        return set(
            (str(r[0]).zfill(2) if isinstance(r[0], int) else r[0], int(r[1]))
            for r in rows
        )
    except Exception:
        return set()


# ── odds fetch ──

def fetch_race_odds(wrapper, conn, key: str, table_map: dict, factory: ParserFactory,
                    ts_table_map: Optional[dict] = None):
    """1レース分のオッズを 0B30 で取得して upsert。件数を返す。
    ts_table_map が指定されていれば TS_O* テーブルにも同時書き込み。"""
    fetched_at = datetime.now().strftime("%Y%m%d%H%M%S")
    try:
        result, _ = wrapper.jv_rt_open("0B30", key=key)
    except Exception:
        return 0, None

    if result < 0:
        try:
            wrapper.jv_close()
        except Exception:
            pass
        return 0, None

    total = 0
    datakubun = None

    for _ in range(200000):
        try:
            ret, buff, _ = wrapper.jv_read()
        except Exception:
            break
        if ret == 0:
            break
        if ret < 0 or not buff or len(buff) < 2:
            continue

        rt = buff[:2].decode('cp932', errors='replace')
        try:
            parser = factory.get_parser(rt)
            if parser is None:
                continue
            parsed = parser.parse(buff)
            if parsed is None:
                continue
            records = parsed if isinstance(parsed, list) else [parsed]
            for rec in records:
                dk = rec.get("DataKubun")
                if dk:
                    datakubun = dk
                rs = rec.get("RecordSpec", rt)
                mapping = table_map.get(rs)
                if mapping is None:
                    continue
                tbl, pk = mapping
                _generic_upsert(conn, tbl, rec, pk)
                # 時系列テーブルにも書き込み (FetchedAt付与)
                if ts_table_map:
                    ts_mapping = ts_table_map.get(rs)
                    if ts_mapping:
                        ts_tbl, ts_pk = ts_mapping
                        ts_rec = dict(rec)
                        ts_rec["FetchedAt"] = fetched_at
                        _generic_upsert(conn, ts_tbl, ts_rec, ts_pk)
                total += 1
        except Exception:
            pass

    try:
        wrapper.jv_close()
    except Exception:
        pass

    return total, datakubun


# ── scheduling ──

def categorize_races(races, confirmed: Set, now_dt: datetime):
    """レースを分類:
    - urgent: 発走5分以内（-120秒 ～ +300秒）
    - pending: 発走前だがurgentではない
    - next_hasso: 未確定レースの直近発走時刻
    """
    urgent = []
    pending = []
    next_hasso = None

    for jyocd, kaiji, nichiji, racenum, hasso_dt in races:
        if (jyocd, racenum) in confirmed:
            continue
        if hasso_dt is None:
            pending.append((jyocd, kaiji, nichiji, racenum, hasso_dt))
            continue

        diff = (hasso_dt - now_dt).total_seconds()
        if -120 <= diff <= 300:
            urgent.append((jyocd, kaiji, nichiji, racenum, hasso_dt))
        elif diff > -120:
            pending.append((jyocd, kaiji, nichiji, racenum, hasso_dt))
            if next_hasso is None or hasso_dt < next_hasso:
                next_hasso = hasso_dt

    return urgent, pending, next_hasso


def calc_sleep(cycle_start: datetime, urgent: bool, next_hasso: Optional[datetime]) -> float:
    """スリープ時間を計算"""
    now_dt = datetime.now()

    if urgent:
        # 発走間近: サイクル開始から1分
        target = cycle_start + timedelta(seconds=60)
        sleep_sec = (target - now_dt).total_seconds()
        return max(sleep_sec, 1)

    # 発走が遠い: 直近発走5分前 or サイクル開始から5分
    fallback = cycle_start + timedelta(seconds=300)

    if next_hasso:
        target = next_hasso - timedelta(seconds=300)
        target = min(target, fallback)
    else:
        target = fallback

    sleep_sec = (target - now_dt).total_seconds()
    return max(sleep_sec, 5)


# ── prefetch race entries via historical API ──

def prefetch_races(wrapper, conn, date_str: str, is_nar: bool):
    """NVOpen/JVOpen差分で当日の出馬表(RA/SE)をDBにupsert。

    0B12(リアルタイム)は確定レースしか返さないため、
    未発走レースの出馬表は履歴APIで事前取得する必要がある。
    """
    import time as _time

    ra_table = "nl_ra_nar" if is_nar else "nl_ra"
    se_table = "nl_se_nar" if is_nar else "nl_se"
    ra_pk = ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum']
    se_pk = ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'umaban']

    # 3日前からの差分
    from_date = (datetime.strptime(date_str, "%Y%m%d") - timedelta(days=3)).strftime("%Y%m%d")
    fromtime = from_date + "000000"
    target_md = int(date_str[4:])

    p(f"出馬表取得中 (NVOpen from={from_date})...")

    try:
        result, read_count, download_count, _ = wrapper.jv_open("RACE", fromtime, 1)
    except Exception as e:
        p(f"  NVOpen失敗: {e}")
        return 0

    if result == -1 or (read_count == 0 and download_count == 0):
        p("  差分データなし")
        return 0

    # ダウンロード待ち
    if download_count > 0:
        p(f"  ダウンロード中 ({download_count}件)...")
        for _ in range(120):
            st = wrapper.jv_status()
            if st == 0:
                break
            elif st < 0:
                break
            _time.sleep(1)

    factory = ParserFactory()
    ra_count = 0
    se_count = 0

    for _ in range(500000):
        try:
            ret, buff, _ = wrapper.jv_read()
        except Exception:
            break
        if ret == 0:
            break
        if ret < 0 or not buff or len(buff) < 2:
            continue

        rt = buff[:2].decode('cp932', errors='replace')
        if rt not in ('RA', 'SE'):
            continue

        try:
            parser = factory.get_parser(rt)
            if parser is None:
                continue
            parsed = parser.parse(buff)
            if parsed is None:
                continue

            records = parsed if isinstance(parsed, list) else [parsed]
            for rec in records:
                md = rec.get('MonthDay')
                try:
                    md_int = int(str(md).strip())
                except (ValueError, TypeError):
                    continue
                if md_int != target_md:
                    continue

                if rt == 'RA':
                    _generic_upsert(conn, ra_table, rec, ra_pk)
                    ra_count += 1
                elif rt == 'SE':
                    _generic_upsert(conn, se_table, rec, se_pk)
                    se_count += 1
        except Exception:
            pass

    try:
        wrapper.jv_close()
    except Exception:
        pass

    p(f"  RA: {ra_count}件, SE: {se_count}件")
    return ra_count


# ── main loop ──

def run_poll_odds(wrapper, conn, date_str: str, is_nar: bool, pg_config: dict = None):
    """オッズポーリングメインループ"""
    jyo_names = NAR_JYOCD_NAMES if is_nar else JYO_NAMES
    table_map = _get_table_map(is_nar)
    ts_table_map = _get_ts_table_map(is_nar)
    factory = ParserFactory()

    # 出馬表を事前取得（NVOpen差分）
    prefetch_races(wrapper, conn, date_str, is_nar)

    races = get_races_with_hasso(conn, date_str, is_nar)
    if not races:
        p("レースが見つかりません")
        return

    jyo_set = sorted(set(r[0] for r in races))
    p(f"対象: {len(races)}R [{', '.join(jyo_names.get(j, j) for j in jyo_set)}]")

    confirmed = get_confirmed_races(conn, date_str, is_nar)
    total_odds = 0
    cycle = 0
    last_full = datetime.min

    while True:
        cycle += 1
        cycle_start = datetime.now()
        now_dt = cycle_start

        confirmed = get_confirmed_races(conn, date_str, is_nar)
        active = [(j, k, n, r, h) for j, k, n, r, h in races if (j, r) not in confirmed]

        if not active:
            p(f"全{len(races)}レース確定。終了します。")
            break

        urgent, pending, next_hasso = categorize_races(races, confirmed, now_dt)
        need_full = (now_dt - last_full).total_seconds() >= 300

        # 1) urgent: 発走5分以内のレース (毎サイクル)
        urgent_count = 0
        if urgent:
            for jyocd, kaiji, nichiji, racenum, hasso_dt in urgent:
                key = f"{date_str}{jyocd}{racenum:02d}"
                cnt, dk = fetch_race_odds(wrapper, conn, key, table_map, factory, ts_table_map)
                urgent_count += cnt

        # 2) full: 全未確定レース (5分間隔)
        full_count = 0
        rtd_total = 0
        if need_full:
            urgent_set = set((j, r) for j, _, _, r, _ in urgent) if urgent else set()
            for jyocd, kaiji, nichiji, racenum, hasso_dt in active:
                if (jyocd, racenum) in urgent_set:
                    continue  # urgentで取得済み
                key = f"{date_str}{jyocd}{racenum:02d}"
                cnt, dk = fetch_race_odds(wrapper, conn, key, table_map, factory, ts_table_map)
                full_count += cnt

                if is_nar:
                    trigger_rtd_cache(wrapper, date_str, jyocd, racenum)
                    rtd_cnt = import_rtd_odds(conn, date_str, jyocd, racenum,
                                              ts_table_map, factory)
                    rtd_total += rtd_cnt

            # 0B12 rtd
            if is_nar:
                import_rtd_results(conn, date_str, factory)

            last_full = datetime.now()

        cycle_total = urgent_count + full_count
        total_odds += cycle_total + rtd_total

        # ステータス表示
        ts = now_dt.strftime("%H:%M:%S")
        confirmed_count = len(get_confirmed_races(conn, date_str, is_nar))
        remaining = len(races) - confirmed_count

        parts = []
        if urgent_count > 0:
            urgent_labels = [f"{jyo_names.get(j, j)}R{r}" for j, _, _, r, _ in urgent]
            parts.append(f"urgent+{urgent_count} [{', '.join(urgent_labels)}]")
        if full_count > 0:
            parts.append(f"full+{full_count} ({len(active) - len(urgent_set if need_full else set())}R)")
        if rtd_total > 0:
            parts.append(f"rtd+{rtd_total}")
        if not parts:
            parts.append("waiting")

        p(f"[{ts}] cycle {cycle} {' '.join(parts)} 確定={confirmed_count}/{len(races)}")

        if remaining == 0:
            p(f"全{len(races)}レース確定。終了します。")
            break

        # スリープ: urgentがあれば1分、なければ min(次のfull, 発走5分前)
        if urgent:
            sleep_sec = max((cycle_start + timedelta(seconds=60) - datetime.now()).total_seconds(), 1)
        elif need_full:
            # fullを実行した直後 → 次のfullまで5分、ただし発走5分前には起きる
            sleep_sec = calc_sleep(datetime.now(), False, next_hasso)
        else:
            # fullまだ → 次のurgentか発走5分前
            sleep_sec = calc_sleep(cycle_start, False, next_hasso)

        next_time = (datetime.now() + timedelta(seconds=sleep_sec)).strftime("%H:%M:%S")
        p(f"  累計: {total_odds}件, 残り{remaining}R, 次回: {next_time}")

        for _ in range(int(sleep_sec)):
            time.sleep(1)
