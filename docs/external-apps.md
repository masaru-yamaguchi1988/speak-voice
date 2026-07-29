# ブラウザ・クリップボード・外部アプリ連携

外部アプリから送信する前にWebコンソールを起動してください。

```bash
speak-voice-web
```

## ブラウザの選択テキスト

Webコンソールで音声エンジンと話者を選び、「選択テキストを読み上げ」をブラウザのブックマークバーへドラッグします。

Webページで文章を選択してブックマークを押すと、ローカルの`speak-voice`へ送信されます。文章を選択していない場合は入力ダイアログが表示されます。

Webコンソールは`127.0.0.1`だけで待ち受けますが、ブックマークレット利用のため外部ページからローカルのフックAPIへのPOSTを許可しています。

## クリップボード

文章をコピーしてから実行します。

```bash
speak-voice-clip --wait
```

エンジンや話者も指定できます。

```bash
speak-voice-clip \
  --engine voicevox \
  --speaker 2 \
  --speed 1.1 \
  --wait
```

クリップボード取得には次のOS機能を使用します。

- macOS: `pbpaste`
- Windows: PowerShell `Get-Clipboard`
- Linux: `wl-paste`、`xclip`、`xsel`のいずれか

## Raycast・Alfred・macOSショートカット

各アプリのシェルコマンド実行機能に、次のようなコマンドを登録します。

```bash
/usr/local/bin/speak-voice-clip \
  --engine voicevox \
  --speaker 2 \
  --wait
```

仮想環境へインストールしている場合は、`which speak-voice-clip`で表示された絶対パスを指定してください。

## テキストを直接送る

```bash
speak-voice hook "読み上げたい文章" \
  --engine voicevox \
  --speaker 2
```

通常はWebサーバーの`POST /api/hook/speak`へ送信します。Webサーバーへ接続できない場合は、指定した音声エンジンをCLIから直接呼び出して再生を試みます。
