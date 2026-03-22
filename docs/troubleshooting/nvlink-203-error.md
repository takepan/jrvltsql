# NVLink -203 エラー詳細調査レポート

**作成日**: 2025-12-22
**更新日**: 2026-03-22
**対象**: UmaConn/NVLink (地方競馬DATA) の -203 エラー

## 概要

NVLink (UmaConn) API の `NVStatus` が継続的に `-203` エラーを返す問題について調査し、解決策を実装しました。

## 問題の詳細

### 症状

```
NVOpen: result=-301 (ダウンロード中), download_count=1
NVStatus: -203 (継続的に返される)
NVRead: -203 エラー
```

- `NVOpen` は成功（result=-301, download_count=1）
- しかし `NVStatus` が継続的に `-203` を返す
- その結果、`NVRead` も `-203` エラーで失敗

### -203 エラーコードの意味

**定義**: `JV_RT_OTHER_ERROR = -203` (その他エラー)

**JV-Link (JRA) の場合**: ネットワーク接続エラー
**NV-Link (NAR) の場合**: 主に以下の原因:

1. **option=1 (差分データモード) での既知の問題** (最も多い原因)
2. **データキャッシュの破損**

## 根本原因

### 1. option=1 の互換性問題

NAR (NV-Link) では `option=1` (差分データ取得) が正常動作しないことがある。
特に初回利用時や、11ヶ月以内のデータを取得する場合に発生しやすい。

**理由**: NV-Link API は JV-Link API と同じインターフェースを持つが、内部実装が異なるため、一部の option パラメータで動作が異なる。

### 2. エラーコード定義の不整合

調査時点では `nvlink/constants.py` の `ERROR_MESSAGES` 辞書に `-203` の定義がなかった。これにより、エラーメッセージが `"不明なエラーコード: -203"` となっていた。

## 実装した解決策

### 1. option=4 自動フォールバック (2026-03-22)

NARでoption=1使用時に-203でダウンロードが失敗した場合、自動的にoption=4（セットアップモード）でリトライする。

**ファイル**: `scripts/quickstart.py`

```python
# NAR: -203でダウンロード失敗した場合、option=4（セットアップ）でリトライ
if result.get('download_aborted') and data_source == DataSource.NAR and option != 4:
    result = processor.process_date_range(
        data_spec=spec,
        from_date=from_date,
        to_date=to_date,
        option=4,
    )
```

### 2. ダウンロード失敗時の読み取りスキップ (2026-03-22)

NVGetsで-203が続きダウンロードが完了しない場合、NVReadフェーズを丸ごとスキップする（以前は1000回空読みしていた）。

**ファイル**: `src/fetcher/historical.py`

- `_wait_for_download()` が `True`/`False` を返すように変更
- `download_started == False` で break した場合 → `False`（データなし）
- 呼び出し元で `False` の場合に `_download_aborted = True` をセットして即 return

### 3. -203 ログレベル抑制 (2026-03-22)

NVReadの-203はfetcher側でサイレントスキップするため、wrapper/bridge層のログをwarning→debugに変更。

**ファイル**: `src/nvlink/wrapper.py`, `src/nvlink/bridge.py`

### 4. エラーコード定義の追加

**ファイル**: `src/nvlink/constants.py`

```python
ERROR_MESSAGES = {
    # ...
    -203: "その他のエラー（option=1での互換性問題、またはキャッシュの問題）",
    # ...
}
```

### 5. リトライロジック

`_wait_for_download` では `-203` を含むリトライ可能エラーを2回までリトライし、それでも解決しない場合はダウンロード待ちを打ち切る。

## 対処法（ユーザー向け）

### 自動対処（通常はこれで解決）

quickstart.py が自動的に以下を行う:
1. option=1 で -203 エラー → option=4（セットアップモード）で自動リトライ
2. NVRead -203 連続 → 即スキップ（1000回空読み回避）

### 手動対処（自動対処で解決しない場合）

1. **UmaConn (地方競馬DATA) を再起動**
2. **CLI で明示的に option=4 を使用**:
   ```bash
   jltsql fetch --source nar --spec RACE --from 20240101 --to 20241231 --option 4
   ```
3. **UmaConn の再インストール**（キャッシュ破損が疑われる場合）

## 技術的な詳細

### NVOpen と NVStatus の動作

```
[正常な流れ]
NVOpen("RACE", "20241201000000", option=4)
  -> result=-301 (ダウンロード中), download_count=1

NVStatus() (80msごとにポーリング)
  -> status=1000 (10%)
  -> status=2000 (20%)
  -> ...
  -> status=10000 (100%)
  -> status=0 (完了)

NVRead() (レコード読み取り開始)
  -> データ取得成功

[異常な流れ - option=1 での -203]
NVOpen("RACE", "20241201000000", option=1)
  -> result=-301 (ダウンロード中), download_count=1

NVStatus() (80msごとにポーリング)
  -> status=-203 (その他エラー) ← 継続的に返される
  -> 2回リトライ後、ダウンロード打ち切り

→ option=4 で自動リトライ（quickstart.py）
```

### option パラメータの違い

| option | JV-Link (JRA) | NV-Link (NAR) |
|--------|---------------|---------------|
| 1 | 差分データ取得 (正常動作) | **動作不安定** (-203エラー発生あり) |
| 2 | 今週データ | 一部スペックのみ対応 |
| 3 | セットアップ (ダイアログあり) | 安定動作 |
| 4 | セットアップ (ダイアログなし) | **推奨** (安定動作、全データDL) |

**推奨設定**: NAR データ取得には `option=4` を使用（quickstart.py は -203 時に自動フォールバック）

### -3（ダウンロード中）エラー

`NVRead` / `NVGets` が `-3` を返す場合、該当ファイルがまだサーバーからダウンロードされていないことを意味する。

**対処法**: fetcher 側でサイレントスキップし、連続上限で打ち切り。

### -502 リトライ

`-502`（ダウンロード失敗）は一時的なネットワークエラー。JRVLTSQLでは `-203`, `-402`, `-403`, `-502`, `-503` をリカバラブルエラーとして扱い、ファイルを削除して読み取りを継続する。

## 参考情報

- [UmaConn公式サイト](https://www.keiba-data.com/)
- [jrvltsql エラーコードリファレンス](../reference/error-codes.md)

## 変更履歴

| 日付 | 変更内容 |
|------|---------|
| 2025-12-22 | 初版作成、-203 エラー対策実装 |
| 2026-03-22 | option=4自動フォールバック、ダウンロード失敗時の読み取りスキップ、ログ抑制、NVDTLab設定ツール記述を削除（存在しないため） |
