# トラブルシューティング

## Ollamaで404になる

指定したモデルが取得済みか確認します。

```bash
ollama list
ollama pull gemma3
```

Base URLは通常`http://localhost:11434/v1`です。Web画面の「再取得」でモデルが表示されることを確認してください。

## 音声エンジンが「無効」と表示される

- VOICEVOXまたはCOEIROINKが起動しているか確認
- 使用ポートが既定値と異なっていないか確認
- VOICEPEAKの実行ファイルが存在するか確認
- 場所が異なる場合は`VOICEPEAK_PATH`を設定
- VoiSona Talkが起動・ログイン済みで、REST APIが有効か確認
- VoiSona Talkのユーザー名、パスワード、ポートが一致しているか確認

## VOICEPEAKが頻繁に失敗する

VOICEPEAKのCLI呼び出しは直列化され、既定では各起動の間を1秒空けます。一時的な終了や不正なWAV出力は最大4回まで、1秒、2秒、4秒と間隔を広げて再試行します。

コロン、Markdown装飾、絵文字など、記号だけの断片はVOICEPEAKを不安定にすることがあるため、読み上げキューから自動的に除外します。

WebコンソールでVOICEPEAKを選ぶと、直近の診断イベントとログファイルの場所を確認できます。既定のログ保存先は次のとおりです。

- macOS: `~/Library/Logs/speak-voice/voicepeak.log`
- Windows: `%LOCALAPPDATA%\speak-voice\logs\voicepeak.log`
- Linux: `~/.local/state/speak-voice/voicepeak.log`

ログには読み上げ本文を保存せず、文字数、所要時間、終了コード、標準エラーなどを記録します。画面に表示された診断IDで、同じ音声生成の再試行を追跡できます。

調整用の環境変数：

```bash
export VOICEPEAK_COOLDOWN_SECONDS=1.5
export VOICEPEAK_RETRY_ATTEMPTS=4
export VOICEPEAK_LOG_FILE=/任意の場所/voicepeak.log
```

`error_kind`が`timeout`の場合は入力を短く区切ります。同じ`exit_code`が続く場合は、VOICEPEAK本体とボイスライブラリの更新状況も確認してください。

## Linuxで音声が再生されない

`aplay`、`paplay`、`play`のいずれかをインストールしてください。

## クリップボードを取得できない

Linuxでは`wl-paste`、`xclip`、`xsel`のいずれかをインストールしてください。

## Python APIの読み上げが途中で切れる

`bridge.stop()`の前に再生完了を待ちます。

```python
bridge.wait_until_done()
bridge.stop()
```

途中で止める場合は`bridge.cancel()`を呼び出してください。
