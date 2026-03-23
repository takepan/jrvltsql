# NAR リアルタイムデータ仕様

NV-Link (UmaConn) のリアルタイムAPIおよびキャッシュファイルに関する仕様メモ。

## データ取得方法

### NVRTOpen (API)

| spec | 内容 | key形式 | 備考 |
|------|------|---------|------|
| 0B12 | 結果速報 (RA/SE/HR) | YYYYMMDD | 確定レースのみ |
| 0B30 | 全式別オッズ (O1-O6) | YYYYMMDDJJRR | レース単位 |
| 0B33 | ワイドオッズ | YYYYMMDDJJRR | rtdトリガー用 |
| 0B34 | 馬単オッズ | YYYYMMDDJJRR | rtdトリガー用 |
| 0B35 | 三連複オッズ | YYYYMMDDJJRR | rtdトリガー用 |
| 0B36 | 三連単オッズ | YYYYMMDDJJRR | rtdトリガー用 |
| 0B41 | 単複枠オッズ (時系列) | YYYYMMDDJJRR | rtdトリガー用 |
| 0B42 | 馬連オッズ (時系列) | YYYYMMDDJJRR | rtdトリガー用 |

### .rtd キャッシュファイル

場所: `C:\UmaConn\chiho.k-ba\data\cache\{YYYY}\`

| ファイル名パターン | 内容 |
|-------------------|------|
| `0B12{YYYYMMDD}.rtd` | 結果速報 (ネストzip: 内部にRA/SE/HR) |
| `0B30{YYYYMMDD}{JJ}{RR}.rtd` | オッズ (zip: 内部にO1-O6テキスト) |

NVRTOpen→NVCloseすると対応する.rtdファイルが更新される（キャッシュ更新トリガー）。

## データ項目の違い

### NVRTOpen(0B30) vs .rtdファイル

| 項目 | API (0B30) | .rtd |
|------|-----------|------|
| オッズ (Odds) | ○ | ○ |
| 票数 (Vote) | △ dk=4(確定)のみ | **×** |
| 枠単 (O1W) | ○ | **×** |
| 人気 (Ninki) | ○ | ○ |
| HassoTime | ○ | ○ |

**票数はAPIからのみ取得可能。.rtdファイルには含まれない。**

### DataKubun別の票数有無 (NAR)

| DataKubun | 意味 | オッズ | 票数 |
|-----------|------|--------|------|
| 1 | 中間オッズ | ○ | **×** |
| 2 | 前日最終 | ○ | △ |
| 4 | 確定 | ○ | ○ |
| 5 | 速報確定 | ○ | ○ |

※ JRA(JV-Link)ではdk=1でも票数が含まれるが、NAR(NV-Link)では含まれない。

## NVOpen (履歴API)

| 項目 | 備考 |
|------|------|
| fromtime | YYYYMMDD000000形式。差分起点。出馬表は数日前に配信されるため7日前推奨 |
| option=1 | 差分データ。当日分はリアルタイムAPI(NVRTOpen)を使う |
| NVStatus | 0(初期/完了) → >0(ダウンロード進行中%) → 0(完了) の遷移 |
| NVRead -3 | ファイル未ダウンロード。スキップして続行可能 |

### NVStatus遷移の注意点

NVOpen直後のNVStatus=0は「まだ始まっていない」であり「完了」ではない。
ダウンロード待ちでは、一度 >0 を確認した後に 0 になったら完了と判断する。

## テーブル構成

### jltsql odds --nar が書き込むテーブル

| テーブル | Source | 内容 |
|---------|--------|------|
| nl_o*_nar | - | 最新オッズ (上書き) |
| ts_o*_nar | `api` | NVRTOpen(0B30)からの時系列 (FetchedAt別に蓄積) |
| ts_o*_nar | `rtd` | .rtdファイルからの時系列 (FetchedAt別に蓄積) |
| nl_ra_nar / nl_se_nar / nl_hr_nar | - | 0B12 rtdからの結果・払戻 |

ts_o*テーブルのPK: `(Year, MonthDay, JyoCD, Kaiji, Nichiji, RaceNum, Kumi/Umaban, HassoTime, FetchedAt)`

票数が必要な分析では `WHERE source = 'api'` でフィルタする。
