"""jltsql today サブコマンド — 当日のDM・TM・オッズをリアルタイムAPIで取得

JRA: JVRTOpen で以下を取得し PostgreSQL に upsert:
- 速報系: DM(0B13), TM(0B17)  key=YYYYMMDD
- 時系列: O1-O6(0B30-0B36)    key=YYYYMMDDJJKKNNRR (レース単位)

NAR: NVRTOpen で以下を取得し PostgreSQL に upsert:
- 0B12: RA/SE/HR (結果・払戻)  key=YYYYMMDD
- 0B30: O1-O6 (全オッズ一括)   key=YYYYMMDDJJRR (レース単位)
"""

import datetime
import time
from typing import List, Tuple

from src.jvlink.constants import generate_time_series_full_key
from src.parser.dm_parser import DMParser
from src.parser.tm_parser import TMParser
from src.parser.o1_parser import O1Parser
from src.parser.o2_parser import O2Parser
from src.parser.o3_parser import O3Parser
from src.parser.o4_parser import O4Parser
from src.parser.o5_parser import O5Parser
from src.parser.o6_parser import O6Parser

JYO_NAMES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}


def _strip(v):
    if v is None:
        return None
    return str(v).strip() or None


def _int(v):
    if v is None:
        return None
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return None


def _float(v):
    if v is None:
        return None
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


# ── upsert functions ──

def upsert_dm(conn, rows):
    count = 0
    for r in rows:
        try:
            conn.run("""
                INSERT INTO nl_dm (year, monthday, jyocd, kaiji, nichiji, racenum,
                    umaban, dmtime, dmgosap, dmgosam, makehm, makedate, datakubun)
                VALUES (:y, :md, :j, :k, :n, :rn, :u, :dt, :gp, :gm, :hm, :mkd, :dk)
                ON CONFLICT (year, monthday, jyocd, kaiji, nichiji, racenum, umaban)
                DO UPDATE SET dmtime=EXCLUDED.dmtime, dmgosap=EXCLUDED.dmgosap,
                    dmgosam=EXCLUDED.dmgosam, makehm=EXCLUDED.makehm
            """,
                y=_int(r.get("Year")), md=_strip(r.get("MonthDay")),
                j=_strip(r.get("JyoCD")), k=_strip(r.get("Kaiji")),
                n=_strip(r.get("Nichiji")), rn=_strip(r.get("RaceNum")),
                u=_int(r.get("Umaban")), dt=_strip(r.get("DMTime")),
                gp=_strip(r.get("DMGosaP")), gm=_strip(r.get("DMGosaM")),
                hm=_strip(r.get("MakeHM")), mkd=_strip(r.get("MakeDate")),
                dk=_strip(r.get("DataKubun")),
            )
            count += 1
        except Exception as e:
            if count < 3:
                print(f"  DM upsert error: {e}", flush=True)
    return count


def upsert_tm(conn, rows):
    count = 0
    for r in rows:
        try:
            conn.run("""
                INSERT INTO nl_tm (year, monthday, jyocd, kaiji, nichiji, racenum,
                    umaban, tmscore, makehm, makedate, datakubun)
                VALUES (:y, :md, :j, :k, :n, :rn, :u, :ts, :hm, :mkd, :dk)
                ON CONFLICT (year, monthday, jyocd, kaiji, nichiji, racenum, umaban)
                DO UPDATE SET tmscore=EXCLUDED.tmscore, makehm=EXCLUDED.makehm
            """,
                y=_int(r.get("Year")), md=_strip(r.get("MonthDay")),
                j=_strip(r.get("JyoCD")), k=_strip(r.get("Kaiji")),
                n=_strip(r.get("Nichiji")), rn=_strip(r.get("RaceNum")),
                u=_int(r.get("Umaban")), ts=_int(r.get("TMScore")),
                hm=_strip(r.get("MakeHM")), mkd=_strip(r.get("MakeDate")),
                dk=_strip(r.get("DataKubun")),
            )
            count += 1
        except Exception as e:
            if count < 3:
                print(f"  TM upsert error: {e}", flush=True)
    return count


def upsert_o1(conn, rows):
    count = 0
    for r in rows:
        try:
            conn.run("""
                INSERT INTO nl_o1 (year, monthday, jyocd, kaiji, nichiji, racenum,
                    umaban, tanodds, tanninki, fukuoddslow, fukuoddshigh, fukuninki,
                    hassotime, torokutosu, syussotosu)
                VALUES (:y, :md, :j, :k, :n, :rn, :u, :to, :tn, :fl, :fh, :fn,
                    :ht, :tt, :st)
                ON CONFLICT (year, monthday, jyocd, kaiji, nichiji, racenum, umaban)
                DO UPDATE SET tanodds=EXCLUDED.tanodds, tanninki=EXCLUDED.tanninki,
                    fukuoddslow=EXCLUDED.fukuoddslow, fukuoddshigh=EXCLUDED.fukuoddshigh,
                    fukuninki=EXCLUDED.fukuninki
            """,
                y=_int(r.get("Year")), md=_strip(r.get("MonthDay")),
                j=_strip(r.get("JyoCD")), k=_strip(r.get("Kaiji")),
                n=_strip(r.get("Nichiji")), rn=_strip(r.get("RaceNum")),
                u=_int(r.get("Umaban")),
                to=_float(r.get("TanOdds")), tn=_int(r.get("TanNinki")),
                fl=_float(r.get("FukuOddsLow")), fh=_float(r.get("FukuOddsHigh")),
                fn=_int(r.get("FukuNinki")),
                ht=_strip(r.get("HassoTime")), tt=_int(r.get("TorokuTosu")),
                st=_int(r.get("SyussoTosu")),
            )
            count += 1
        except Exception as e:
            if count < 3:
                print(f"  O1 upsert error: {e}", flush=True)
    return count


def upsert_odds_kumi(conn, table, rows):
    count = 0
    for r in rows:
        try:
            conn.run(f"""
                INSERT INTO {table} (year, monthday, jyocd, kaiji, nichiji, racenum,
                    kumi, odds, ninki, vote, hassotime, torokutosu, syussotosu)
                VALUES (:y, :md, :j, :k, :n, :rn, :ku, :od, :ni, :vo, :ht, :tt, :st)
                ON CONFLICT (year, monthday, jyocd, kaiji, nichiji, racenum, kumi)
                DO UPDATE SET odds=EXCLUDED.odds, ninki=EXCLUDED.ninki, vote=EXCLUDED.vote
            """,
                y=_int(r.get("Year")), md=_strip(r.get("MonthDay")),
                j=_strip(r.get("JyoCD")), k=_strip(r.get("Kaiji")),
                n=_strip(r.get("Nichiji")), rn=_strip(r.get("RaceNum")),
                ku=_strip(r.get("Kumi")), od=_float(r.get("Odds")),
                ni=_int(r.get("Ninki")), vo=_int(r.get("Vote")),
                ht=_strip(r.get("HassoTime")), tt=_int(r.get("TorokuTosu")),
                st=_int(r.get("SyussoTosu")),
            )
            count += 1
        except Exception as e:
            if count < 3:
                print(f"  {table} upsert error: {e}", flush=True)
    return count


def upsert_o3(conn, rows):
    count = 0
    for r in rows:
        try:
            conn.run("""
                INSERT INTO nl_o3 (year, monthday, jyocd, kaiji, nichiji, racenum,
                    kumi, oddslow, oddshigh, ninki, vote, hassotime, torokutosu, syussotosu)
                VALUES (:y, :md, :j, :k, :n, :rn, :ku, :ol, :oh, :ni, :vo, :ht, :tt, :st)
                ON CONFLICT (year, monthday, jyocd, kaiji, nichiji, racenum, kumi)
                DO UPDATE SET oddslow=EXCLUDED.oddslow, oddshigh=EXCLUDED.oddshigh,
                    ninki=EXCLUDED.ninki, vote=EXCLUDED.vote
            """,
                y=_int(r.get("Year")), md=_strip(r.get("MonthDay")),
                j=_strip(r.get("JyoCD")), k=_strip(r.get("Kaiji")),
                n=_strip(r.get("Nichiji")), rn=_strip(r.get("RaceNum")),
                ku=_strip(r.get("Kumi")), ol=_float(r.get("OddsLow")),
                oh=_float(r.get("OddsHigh")), ni=_int(r.get("Ninki")),
                vo=_int(r.get("Vote")), ht=_strip(r.get("HassoTime")),
                tt=_int(r.get("TorokuTosu")), st=_int(r.get("SyussoTosu")),
            )
            count += 1
        except Exception as e:
            if count < 3:
                print(f"  O3 upsert error: {e}", flush=True)
    return count


# ── fetch helpers ──

def p(*a, **kw):
    kw.setdefault("flush", True)
    print(*a, **kw)


def fetch_speed_report(wrapper, data_spec, key, label, parser, upsert_fn, conn):
    """速報系(0B1x)データを取得。key=YYYYMMDD"""
    p(f"\n--- {label} (spec={data_spec}, key={key}) ---")
    try:
        result, read_count = wrapper.jv_rt_open(data_spec, key=key)
    except Exception as e:
        p(f"  JVRTOpen失敗: {e}")
        return 0

    if result < 0:
        p(f"  データなし (result={result})")
        return 0

    p(f"  JVRTOpen成功: read_count={read_count}")

    total = 0
    errors = 0
    rec_count = 0

    while True:
        ret, buff, _fname = wrapper.jv_read()
        if ret == 0:
            break
        elif ret == -1:
            continue
        elif ret < -1:
            errors += 1
            continue

        if buff is None or len(buff) < 2:
            continue

        try:
            parsed = parser.parse(buff)
        except Exception:
            errors += 1
            continue

        if parsed is None:
            continue

        rows = parsed if isinstance(parsed, list) else [parsed]
        rec_count += 1
        cnt = upsert_fn(conn, rows)
        total += cnt

    wrapper.jv_close()
    p(f"  レコード: {rec_count}, DB登録: {total}, エラー: {errors}")
    return total


def fetch_time_series(wrapper, data_spec, label, parser, upsert_fn, conn,
                      races: List[Tuple], date_str: str):
    """時系列(0B2x-0B3x)データをレース単位で取得。"""
    p(f"\n--- {label} (spec={data_spec}) ---")

    total = 0
    race_ok = 0
    race_skip = 0

    for jyocd, kaiji, nichiji, racenum in races:
        key = generate_time_series_full_key(
            date_str, str(jyocd).zfill(2), int(kaiji), int(nichiji), int(racenum)
        )

        result, read_count = None, 0
        for retry in range(3):
            try:
                result, read_count = wrapper.jv_rt_open(data_spec, key=key)
                break
            except Exception as e:
                err_code = getattr(e, 'error_code', None)
                if err_code in (-301, -302):
                    time.sleep(5)
                else:
                    p(f"  {jyocd}R{racenum} key={key} JVRTOpen失敗: {e} (code={err_code})")
                    break

        if result is None or result < 0:
            race_skip += 1
            continue

        rec_count = 0
        while True:
            ret, buff, _fname = wrapper.jv_read()
            if ret == 0:
                break
            elif ret <= -1:
                continue

            if buff is None or len(buff) < 2:
                continue

            try:
                parsed = parser.parse(buff)
            except Exception:
                continue

            if parsed is None:
                continue

            rows = parsed if isinstance(parsed, list) else [parsed]
            rec_count += 1
            total += upsert_fn(conn, rows)

        wrapper.jv_close()
        if rec_count > 0:
            race_ok += 1

    p(f"  レース: {race_ok}件取得, {race_skip}件スキップ, DB登録: {total}")
    return total


def get_today_races(conn, date_str):
    """DBから当日のレース一覧を取得 (jyocd, kaiji, nichiji, racenum)"""
    year = int(date_str[:4])
    monthday = date_str[4:]
    rows = conn.run("""
        SELECT DISTINCT jyocd, kaiji, nichiji, racenum
        FROM nl_ra
        WHERE year = :y AND monthday = :md
        ORDER BY jyocd, racenum
    """, y=year, md=monthday)
    return rows


def run_fetch_today(wrapper, conn, date_str: str):
    """メインロジック: DM/TM/O1-O6 を取得してDBにupsert

    Args:
        wrapper: JVLinkWrapper (jv_rt_open/jv_read/jv_close を持つ)
        conn: pg8000.native.Connection
        date_str: YYYYMMDD
    """
    p(f"=== fetch today ({date_str}) ===")

    races = get_today_races(conn, date_str)
    p(f"本日のレース: {len(races)}R")
    if races:
        jyo_set = sorted(set(str(r[0]).zfill(2) for r in races))
        p(f"  開催場: {', '.join(JYO_NAMES.get(j, j) for j in jyo_set)}")

    dm_parser = DMParser()
    tm_parser = TMParser()
    o1_parser = O1Parser()
    o2_parser = O2Parser()
    o3_parser = O3Parser()
    o4_parser = O4Parser()
    o5_parser = O5Parser()
    o6_parser = O6Parser()

    t0 = time.time()

    # 速報系 (key=YYYYMMDD)
    dm_total = fetch_speed_report(wrapper, "0B13", date_str, "DM (タイム型予想)",
                                  dm_parser, upsert_dm, conn)
    tm_total = fetch_speed_report(wrapper, "0B17", date_str, "TM (対戦型予想)",
                                  tm_parser, upsert_tm, conn)

    # 時系列オッズ (key=YYYYMMDDJJKKNNRR)
    if not races:
        p("\nレース情報がDBにないため、オッズ取得をスキップ")
        p("先に出馬表を取得してください: jltsql fetch --spec RACE --from YYYYMMDD")
        o1_total = o2_total = o3_total = o4_total = o5_total = o6_total = 0
    else:
        o1_total = fetch_time_series(wrapper, "0B30", "O1 (単勝オッズ)",
                                     o1_parser, upsert_o1, conn, races, date_str)
        o2_total = fetch_time_series(wrapper, "0B32", "O2 (馬連オッズ)", o2_parser,
                                     lambda c, r: upsert_odds_kumi(c, "nl_o2", r),
                                     conn, races, date_str)
        o3_total = fetch_time_series(wrapper, "0B33", "O3 (ワイドオッズ)",
                                     o3_parser, upsert_o3, conn, races, date_str)
        o4_total = fetch_time_series(wrapper, "0B34", "O4 (馬単オッズ)", o4_parser,
                                     lambda c, r: upsert_odds_kumi(c, "nl_o4", r),
                                     conn, races, date_str)
        o5_total = fetch_time_series(wrapper, "0B35", "O5 (3連複オッズ)", o5_parser,
                                     lambda c, r: upsert_odds_kumi(c, "nl_o5", r),
                                     conn, races, date_str)
        o6_total = fetch_time_series(wrapper, "0B36", "O6 (3連単オッズ)", o6_parser,
                                     lambda c, r: upsert_odds_kumi(c, "nl_o6", r),
                                     conn, races, date_str)

    elapsed = time.time() - t0
    p(f"\n完了 ({elapsed:.1f}s)")
    p(f"  DM: {dm_total}件")
    p(f"  TM: {tm_total}件")
    p(f"  O1: {o1_total}件  O2: {o2_total}件  O3: {o3_total}件")
    p(f"  O4: {o4_total}件  O5: {o5_total}件  O6: {o6_total}件")

    return {
        "dm": dm_total, "tm": tm_total,
        "o1": o1_total, "o2": o2_total, "o3": o3_total,
        "o4": o4_total, "o5": o5_total, "o6": o6_total,
        "elapsed": elapsed,
    }


# ── NAR (地方競馬) ──

NAR_JYOCD_NAMES = {
    '30': '門別', '33': '帯広', '35': '盛岡', '36': '水沢',
    '42': '浦和', '43': '船橋', '44': '大井', '45': '川崎',
    '46': '金沢', '47': '笠松', '48': '名古屋',
    '50': '園田', '51': '姫路', '54': '高知', '55': '佐賀',
}

NAR_TABLE_MAP_0B12 = {
    'RA': ('nl_ra_nar', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum']),
    'SE': ('nl_se_nar', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'umaban']),
    'HR': ('nl_hr_nar', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum']),
}


def _sanitize(val):
    if isinstance(val, str) and (val.strip() == "" or val.strip("* ") == ""):
        return None
    return val


def _generic_upsert(conn, table, record, pk_cols):
    """汎用 ON CONFLICT upsert (1件)"""
    record = {k: _sanitize(v) for k, v in record.items()}
    cols = list(record.keys())
    cols_str = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    pk_str = ", ".join(pk_cols)
    up_cols = [c for c in cols if c.lower() not in [pk.lower() for pk in pk_cols]]
    if up_cols:
        up_str = ", ".join(f"{c} = EXCLUDED.{c}" for c in up_cols)
        sql = f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders}) ON CONFLICT ({pk_str}) DO UPDATE SET {up_str}"
    else:
        sql = f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders}) ON CONFLICT ({pk_str}) DO NOTHING"
    conn.run(sql, **record)


def _batch_upsert(conn, table, records, pk_cols):
    """汎用 ON CONFLICT upsert (バッチ — VALUES連結で一括実行)"""
    if not records:
        return 0
    records = [{k: _sanitize(v) for k, v in r.items()} for r in records]
    cols = list(records[0].keys())
    cols_str = ", ".join(cols)
    pk_str = ", ".join(pk_cols)
    up_cols = [c for c in cols if c.lower() not in [pk.lower() for pk in pk_cols]]

    # VALUES ($1,$2,...), ($3,$4,...), ...
    params = []
    value_clauses = []
    for i, rec in enumerate(records):
        placeholders = []
        for j, col in enumerate(cols):
            idx = i * len(cols) + j + 1
            placeholders.append(f"${idx}")
            params.append(rec.get(col))
        value_clauses.append(f"({', '.join(placeholders)})")

    values_str = ", ".join(value_clauses)
    if up_cols:
        up_str = ", ".join(f"{c} = EXCLUDED.{c}" for c in up_cols)
        sql = f"INSERT INTO {table} ({cols_str}) VALUES {values_str} ON CONFLICT ({pk_str}) DO UPDATE SET {up_str}"
    else:
        sql = f"INSERT INTO {table} ({cols_str}) VALUES {values_str} ON CONFLICT ({pk_str}) DO NOTHING"

    conn.run(sql, *params)
    return len(records)


def fetch_nar_results(wrapper, conn, date_str):
    """NAR 0B12: RA/SE/HR を NVRTOpen→NVRead で取得"""
    from src.parser.factory import ParserFactory

    p(f"\n--- NAR 結果・払戻 (0B12, key={date_str}) ---")

    try:
        result, read_count = wrapper.jv_rt_open("0B12", key=date_str)
    except Exception as e:
        p(f"  NVRTOpen失敗: {e}")
        return {}

    if result < 0:
        p(f"  データなし (result={result})")
        return {}

    factory = ParserFactory()
    counts = {"RA": 0, "SE": 0, "HR": 0}

    for _ in range(200000):
        try:
            ret_code, buff, _fname = wrapper.jv_read()
        except Exception:
            break
        if ret_code == 0:
            break
        elif ret_code <= 0:
            continue
        if not buff or len(buff) < 2:
            continue

        rt = buff[:2].decode('cp932', errors='replace')
        if rt not in NAR_TABLE_MAP_0B12:
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
                rs = rec.get('RecordSpec', rt)
                mapping = NAR_TABLE_MAP_0B12.get(rs)
                if mapping is None:
                    continue
                table, pk = mapping
                _generic_upsert(conn, table, rec, pk)
                counts[rs] = counts.get(rs, 0) + 1
        except Exception:
            pass

    try:
        wrapper.jv_close()
    except Exception:
        pass

    p(f"  RA: {counts.get('RA', 0)}, SE: {counts.get('SE', 0)}, HR: {counts.get('HR', 0)}")
    return counts


def fetch_nar_odds(wrapper, conn, date_str, races):
    """NAR 0B30: 全オッズ一括をレース単位で取得"""
    from src.parser.factory import ParserFactory

    p(f"\n--- NAR オッズ (0B30, {len(races)}レース) ---")

    factory = ParserFactory()
    # NAR O1-O6 テーブル + PKマッピング
    odds_table_map = {
        'O1': ('nl_o1_nar', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'umaban']),
        'O1W': ('nl_o1_waku_nar', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi']),
        'O2': ('nl_o2_nar', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi']),
        'O3': ('nl_o3_nar', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi']),
        'O4': ('nl_o4_nar', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi']),
        'O5': ('nl_o5_nar', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi']),
        'O6': ('nl_o6_nar', ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'kumi']),
    }

    total = 0
    race_ok = 0
    race_skip = 0

    for jyocd, racenum in races:
        jyocd_s = str(jyocd).zfill(2) if isinstance(jyocd, int) else jyocd
        rr = f"{int(racenum):02d}"
        key = f"{date_str}{jyocd_s}{rr}"

        try:
            result, read_count = wrapper.jv_rt_open("0B30", key=key)
        except Exception as e:
            err_code = getattr(e, 'error_code', None)
            if err_code not in (-301, -302):
                pass  # skip silently
            race_skip += 1
            continue

        if result < 0:
            race_skip += 1
            continue

        rec_count = 0
        for _ in range(100000):
            try:
                ret_code, buff, _fname = wrapper.jv_read()
            except Exception:
                break
            if ret_code == 0:
                break
            elif ret_code <= 0:
                continue
            if not buff or len(buff) < 2:
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
                    rs = rec.get('RecordSpec', rt)
                    mapping = odds_table_map.get(rs)
                    if mapping is None:
                        continue
                    table, pk = mapping
                    _generic_upsert(conn, table, rec, pk)
                    rec_count += 1
            except Exception:
                pass

        try:
            wrapper.jv_close()
        except Exception:
            pass

        total += rec_count
        if rec_count > 0:
            race_ok += 1

    p(f"  レース: {race_ok}件取得, {race_skip}件スキップ, DB登録: {total}")
    return total


def get_nar_today_races(conn, date_str):
    """DBからNAR当日レース一覧を取得 (jyocd, racenum)"""
    year = int(date_str[:4])
    monthday = int(date_str[4:])
    rows = conn.run("""
        SELECT DISTINCT jyocd, racenum
        FROM nl_ra_nar
        WHERE year = :y AND monthday = :md
        ORDER BY jyocd, racenum
    """, y=year, md=monthday)
    return rows


def prefetch_nar_races(wrapper, conn, date_str: str):
    """NVOpen差分で当日の出馬表(RA/SE)をDBにupsert。

    0B12は確定レースしか返さないため、未発走レースは履歴APIで取得する。
    """
    import time as _time
    from datetime import datetime as _dt, timedelta as _td
    from src.parser.factory import ParserFactory

    from_date = (_dt.strptime(date_str, "%Y%m%d") - _td(days=7)).strftime("%Y%m%d")
    fromtime = from_date + "000000"
    target_md = int(date_str[4:])

    p(f"\n--- 出馬表取得 (NVOpen from={from_date}) ---")

    try:
        result, read_count, download_count, _ = wrapper.jv_open("RACE", fromtime, 1)
    except Exception as e:
        p(f"  NVOpen失敗: {e}")
        return 0

    if result == -1 or (read_count == 0 and download_count == 0):
        p("  差分データなし")
        return 0

    if download_count > 0:
        p(f"  ダウンロード中 ({download_count}件)...")
        download_started = False
        for i in range(120):
            st = wrapper.jv_status()
            if st > 0:
                download_started = True
            elif st == 0 and download_started:
                break
            _time.sleep(1)

    factory = ParserFactory()
    ra_pk = ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum']
    se_pk = ['year', 'monthday', 'jyocd', 'kaiji', 'nichiji', 'racenum', 'umaban']
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
                    _generic_upsert(conn, "nl_ra_nar", rec, ra_pk)
                    ra_count += 1
                elif rt == 'SE':
                    _generic_upsert(conn, "nl_se_nar", rec, se_pk)
                    se_count += 1
        except Exception:
            pass

    try:
        wrapper.jv_close()
    except Exception:
        pass

    p(f"  RA: {ra_count}件, SE: {se_count}件")
    return ra_count


def run_fetch_today_nar(wrapper, conn, date_str: str):
    """NAR版メインロジック: 出馬表(NVOpen) + 結果(0B12) + オッズ(0B30)

    Args:
        wrapper: NVLinkWrapper (jv_rt_open/jv_read/jv_close を持つ)
        conn: pg8000.native.Connection
        date_str: YYYYMMDD
    """
    p(f"=== fetch today NAR ({date_str}) ===")

    # 出馬表を事前取得（NVOpen差分 — 未発走レース含む全RA/SE）
    prefetch_nar_races(wrapper, conn, date_str)

    races = get_nar_today_races(conn, date_str)
    p(f"\n本日のNARレース: {len(races)}R")
    if races:
        jyo_set = sorted(set(str(r[0]).zfill(2) if isinstance(r[0], int) else r[0]
                              for r in races))
        p(f"  開催場: {', '.join(NAR_JYOCD_NAMES.get(j, j) for j in jyo_set)}")

    t0 = time.time()

    # 結果・払戻 (0B12, key=YYYYMMDD)
    result_counts = fetch_nar_results(wrapper, conn, date_str)

    # オッズ (0B30, key=YYYYMMDDJJrr)
    if not races:
        p("\nNARレース情報がDBにないため、オッズ取得をスキップ")
        odds_total = 0
    else:
        odds_total = fetch_nar_odds(wrapper, conn, date_str, races)

    elapsed = time.time() - t0
    p(f"\n完了 ({elapsed:.1f}s)")
    p(f"  RA: {result_counts.get('RA', 0)}件  SE: {result_counts.get('SE', 0)}件  HR: {result_counts.get('HR', 0)}件")
    p(f"  オッズ: {odds_total}件")

    return {
        "ra": result_counts.get("RA", 0),
        "se": result_counts.get("SE", 0),
        "hr": result_counts.get("HR", 0),
        "odds": odds_total,
        "elapsed": elapsed,
    }
