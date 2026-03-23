"""jltsql today サブコマンド — 当日のDM・TM・オッズをリアルタイムAPIで取得

JVRTOpen で以下を取得し PostgreSQL に upsert する:
- 速報系: DM(0B13), TM(0B17)  key=YYYYMMDD
- 時系列: O1-O6(0B30-0B36)    key=YYYYMMDDJJKKNNRR (レース単位)
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
