# オフラインPythonジャッジ 仕様 v0.1

## 目的
Windows環境で、ネット不要で動く「教室用 Python ジャッジ」。
生徒は UI にコードを書いて提出し、複数テストケースで AC / WA / RE / TLE を確認できる。
運用者が変わっても「exe起動」「問題フォルダを追加」だけで回ることを目標とする。

## 1. 動作形態
- ローカルPCで動作するローカルWebアプリ
- アクセス先: `http://127.0.0.1:<port>/`
- 既定では外部公開しない（LAN公開なし）

## 2. 配布物・フォルダ構成
- JudgeApp.exe（Python同梱の単体実行）
- problems/（問題パック）
- data/（将来的に履歴DB等）
- logs/（将来的にログ）

```text
JudgeApp/
  JudgeApp.exe
  problems/
    001_add/
      meta.json
      statement.md
      tests/
        in01.txt
        out01.txt
        in02.txt
        out02.txt
  data/
  logs/
  README_先生用.txt
```

## 3. 問題パッケージ仕様
### 3.1 ディレクトリ名
`problem_dir` は `[A-Za-z0-9_-]+` に限定する。

### 3.2 meta.json
必須キー:
- id: string（内部ID）
- title: string（表示名）
- time_limit_sec: number（例 2.0）
- compare: string（出力比較モード）

例:
```json
{
  "id": "001_add",
  "title": "A+B",
  "time_limit_sec": 2.0,
  "compare": "trim"
}
```

### 3.3 statement.md
UTF-8のMarkdown形式。UIで問題文として表示する。

### 3.4 tests ディレクトリ
`inXX.txt` と `outXX.txt` をペアにする。`XX`は任意の番号。
`in` の昇順で実行する。

## 4. 提出仕様（UI）
入力:
- UIのテキストエリアに Python コードを入力

操作:
- 「提出して実行」ボタンを押す

実行環境:
- Python 3.x
- 1テストケースごとに別プロセスで実行
- 入力は stdin
- 出力は stdout
- 文字コードは UTF-8

## 5. 判定仕様
ステータス:
- AC: 全ケース一致
- WA: 出力不一致
- RE: 実行時エラー
- TLE: タイムアウト

### 5.1 出力比較モード
- exact: 完全一致
- trim:
  - 改行コードを `\n` に統一
  - 各行末の空白削除
  - 末尾の空行削除
- tokens: 空白区切りのトークン列が一致

## 6. 結果表示仕様（UI）
画面構成:
- 問題選択
- 問題文表示
- コード入力欄
- 提出ボタン

結果表示:
- 全体 verdict（AC / NG）
- 各テストケース結果

表示内容:
- ケース名
- ステータス
- 実行時間(ms)

WA の場合:
- diff（expected / actual）
- raw stdout

RE / TLE の場合:
- stderr
- raw stdout

## 7. セキュリティ前提
想定用途は教室教材。

最低限の安全対策:
- 提出コードはテンポラリフォルダで実行
- 127.0.0.1 のみバインド
- タイムアウト設定あり

## 8. 運用（先生向け）
起動:
- JudgeApp.exe をダブルクリック

問題追加:
- problems フォルダに問題ディレクトリを追加

バックアップ:
- problems フォルダをコピー

## 9. 将来拡張（v0.2候補）
- サンプル入力での自由実行
- 提出履歴（SQLite）
- 生徒名入力
- テストケース秘匿モード
- 特別採点（SPJ）
