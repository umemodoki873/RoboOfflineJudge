Robo Offline Judge (v0.1)

使い方:
1) app.py を Python 3 で起動（将来は JudgeApp.exe で起動）
2) ブラウザで http://127.0.0.1:8000/ を開く
3) 問題を選び、コードを貼り付けて「提出して実行」

問題追加:
- problems/ に [A-Za-z0-9_-]+ のディレクトリを作成
- 必須: meta.json / statement.md / tests/
- tests は inXX.txt と outXX.txt のペアを置く

備考:
- 実行は1ケースごとに別プロセス
- ステータス: AC / WA / RE / TLE
- 既定バインド先は 127.0.0.1 のみ
