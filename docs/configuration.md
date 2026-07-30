# 音声エンジンとLLMの接続・設定

## 音声エンジン

### VOICEVOX

VOICEVOXエディタまたはエンジンを起動します。既定の接続先は`http://127.0.0.1:50021`です。

Webコンソールではキャラクターごとにスタイルがグループ表示され、話速、音高、抑揚、音量を調整できます。

### COEIROINK v2

COEIROINKを起動します。既定の接続先は`http://127.0.0.1:50032`です。

Webコンソールではキャラクターごとにスタイルがグループ表示され、話速、音高、抑揚、音量を調整できます。

起動確認には`/v1/engine_info`、話者一覧には画像データを含まない`/v1/speakers_path_variant`、音声合成には`/v1/synthesis`を使用します。

### VOICEPEAK

VOICEPEAKをインストールします。既定では次の実行ファイルを使用します。

- macOS: `/Applications/voicepeak.app/Contents/MacOS/voicepeak`
- Windows: `C:\Program Files\Voicepeak\voicepeak.exe`
- Linux: PATH上の`voicepeak`

場所が異なる場合は環境変数を設定します。

```bash
export VOICEPEAK_PATH="/Applications/voicepeak.app/Contents/MacOS/voicepeak"
```

Webコンソールでは話速、音高、音量と、ナレーター固有の感情を調整できます。

### VoiSona Talk

VoiSona Talkを起動してログインし、使用するボイスライブラリをダウンロードします。画面右上の「編集 → 環境設定 → API」で次を設定してください。

1. API用パスワードを設定
2. 「REST APIを有効にする」をON
3. Webコンソールで「VoiSona Talk」を選択
4. API URL、ユーザー名、API用パスワードを入力
5. 「接続テスト」または「接続して使用」を実行

パスワードは標準ではWebサーバーのメモリ内だけに保持され、終了時に消去されます。「この端末の資格情報ストアに保存する」を選択した場合のみ、OSの資格情報ストアへ保存します。ブラウザのLocal Storageには保存しません。

ヘッドレス実行やCLIでは環境変数も使用できます。

```bash
export VOISONA_API_USER="VoiSona Talkに表示されたユーザー名"
export VOISONA_API_PASSWORD="設定したAPI用パスワード"
export VOISONA_API_PORT="32766"
```

接続先全体を変更する場合：

```bash
export VOISONA_API_URL="http://127.0.0.1:32766/api/talk/v1"
```

話者IDは環境ごとに異なるため、一覧から確認します。

```bash
speak-voice list-speakers --engine voisona
speak-voice speak "こんにちは" \
  --engine voisona \
  --speaker "tanaka-san_ja_JP|2.0.0|ja_JP"
```

安全のため、VoiSona API URLには`localhost`またはループバックIPアドレスだけを指定できます。認証設定APIも同一オリジンからのアクセスだけを受け付け、パスワードをレスポンスやログへ出力しません。

接続後に話者を選ぶと、Webコンソールへ年齢感（ALP）、ハスキー（HUS）と、そのボイスライブラリが提供する固有スタイルのスライダーが表示されます。スタイルは複数を混ぜて指定できます。利用できるスタイル名と種類はボイスライブラリによって異なります。

VoiSona TalkのREST APIはベータ版です。詳細は[公式REST APIチュートリアル](https://manual.voisona.com/ja/talk/pc/2b6e9bc7efb180ea86ccc6c7347e9ca6)を参照してください。

## LLM

### Ollama

Ollamaを起動し、少なくとも1つモデルを取得します。

```bash
ollama list
ollama pull gemma3
```

Webコンソールで次を選択します。

- AIプロバイダー: `Ollama`
- Base URL: `http://localhost:11434/v1`
- モデル: 自動取得されたモデル

一覧が更新されない場合は「再取得」を押してください。

### LM Studio・vLLMなど

OpenAI互換サーバーを起動し、Webコンソールで次を選択します。

- AIプロバイダー: `Local OpenAI`
- Base URL: 例 `http://localhost:1234/v1`
- モデル: `/v1/models`から取得されたモデル

### OpenAI・Gemini

Webコンソールでプロバイダーを選び、APIキーを入力します。入力したAPIキーはブラウザを閉じると破棄され、Local Storageには保存しません。
