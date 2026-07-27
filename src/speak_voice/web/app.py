import asyncio
import json
import os
import queue
import threading
from dataclasses import dataclass, field
from typing import Optional

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from speak_voice.base import BaseEngine
from speak_voice.bridge import VoiceAgentBridge
from speak_voice.cli import ENGINES
from speak_voice.engines import VoicepeakEngine

app = FastAPI(title="speak-voice Web Console")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["content-type"],
)

# 静的ファイルの提供設定 (HTML, CSS, JS)
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# バックグラウンド発声キュー＆ワーカー
speak_queue: queue.Queue = queue.Queue()


@dataclass
class SpeakResult:
    done: threading.Event = field(default_factory=threading.Event)
    error: Optional[Exception] = None


def speak_worker():
    while True:
        item = speak_queue.get()
        if item is None:
            break
        engine_key, speaker_id, text, options, result = item
        try:
            inst = ENGINES[engine_key]()
            wav_bytes = inst.synthesize_wav(
                text=text,
                speaker_id=speaker_id,
                speed=options.get("speed"),
                pitch=options.get("pitch"),
                intonation=options.get("intonation"),
                volume=options.get("volume"),
                style=options.get("style"),
            )
            from speak_voice.player import play_wav

            if not play_wav(wav_bytes):
                raise RuntimeError("音声プレイヤーが再生に失敗しました。")
        except Exception as e:
            if result:
                result.error = e
            print(f"[Speak Worker Error]: {e}")
        finally:
            if result:
                result.done.set()
            speak_queue.task_done()


worker_thread = threading.Thread(target=speak_worker, daemon=True)
worker_thread.start()

ENGINE_PARAMETERS = {
    "voicevox": [
        {"id": "speed", "label": "話速", "min": 0.5, "max": 2.0, "step": 0.05, "default": 1.0},
        {"id": "pitch", "label": "音高", "min": -0.15, "max": 0.15, "step": 0.01, "default": 0.0},
        {
            "id": "intonation",
            "label": "抑揚",
            "min": 0.0,
            "max": 2.0,
            "step": 0.05,
            "default": 1.0,
        },
        {"id": "volume", "label": "音量", "min": 0.0, "max": 2.0, "step": 0.05, "default": 1.0},
    ],
    "coeiroink": [
        {"id": "speed", "label": "話速", "min": 0.5, "max": 2.0, "step": 0.05, "default": 1.0},
        {"id": "pitch", "label": "音高", "min": -0.5, "max": 0.5, "step": 0.01, "default": 0.0},
        {
            "id": "intonation",
            "label": "抑揚",
            "min": 0.0,
            "max": 2.0,
            "step": 0.05,
            "default": 1.0,
        },
        {"id": "volume", "label": "音量", "min": 0.0, "max": 2.0, "step": 0.05, "default": 1.0},
    ],
    "voicepeak": [
        {"id": "speed", "label": "話速", "min": 0.5, "max": 2.0, "step": 0.05, "default": 1.0},
        {"id": "pitch", "label": "音高", "min": -1.5, "max": 1.5, "step": 0.05, "default": 0.0},
        {"id": "volume", "label": "音量", "min": 0.0, "max": 2.0, "step": 0.05, "default": 1.0},
    ],
    "aivoice": [
        {"id": "speed", "label": "話速", "min": 0.5, "max": 4.0, "step": 0.05, "default": 1.0},
        {"id": "pitch", "label": "音高", "min": 0.5, "max": 2.0, "step": 0.05, "default": 1.0},
        {
            "id": "intonation",
            "label": "抑揚",
            "min": 0.0,
            "max": 2.0,
            "step": 0.05,
            "default": 1.0,
        },
        {"id": "volume", "label": "音量", "min": 0.0, "max": 2.0, "step": 0.05, "default": 1.0},
    ],
    "voisona": [],
}


def ollama_root_url(base_url: str) -> str:
    """OpenAI互換URLからOllamaネイティブAPIのルートURLを得ます。"""
    return base_url.rstrip("/").removesuffix("/v1")


def get_ollama_models(base_url: str) -> list[str]:
    """Ollamaにインストール済みのモデル名を取得します。"""
    response = requests.get(f"{ollama_root_url(base_url)}/api/tags", timeout=5)
    response.raise_for_status()
    return [
        item["name"]
        for item in response.json().get("models", [])
        if isinstance(item, dict) and item.get("name")
    ]


def get_openai_compatible_models(base_url: str) -> list[str]:
    """OpenAI互換APIから利用可能なモデル名を取得します。"""
    response = requests.get(f"{base_url.rstrip('/')}/models", timeout=5)
    response.raise_for_status()
    return [
        item["id"]
        for item in response.json().get("data", [])
        if isinstance(item, dict) and item.get("id")
    ]


def ollama_http_error(response: requests.Response) -> RuntimeError:
    """OllamaのJSONエラー本文を利用者向けメッセージに変換します。"""
    try:
        detail = response.json().get("error")
    except (ValueError, AttributeError):
        detail = None
    message = detail or response.text.strip() or f"HTTP {response.status_code}"
    return RuntimeError(f"Ollama APIエラー: {message}")


class SpeakRequest(BaseModel):
    engine: str
    speaker: str
    text: str
    speed: Optional[float] = None
    pitch: Optional[float] = None
    intonation: Optional[float] = None
    volume: Optional[float] = None
    style: Optional[str] = None
    wait: Optional[bool] = False  # 再生完了まで待機するかどうか


class ChatRequest(BaseModel):
    engine: str
    speaker: str
    prompt: str
    api_provider: str  # "openai", "gemini", "ollama", "local", "mock"
    api_key: Optional[str] = None
    base_url: Optional[str] = (
        None  # ローカルLLM/Ollama用のベースURL (例: http://localhost:11434/v1)
    )
    model_name: Optional[str] = None  # カスタムモデル名 (例: qwen2.5, gpt-4o-mini)
    speed: Optional[float] = None
    pitch: Optional[float] = None
    intonation: Optional[float] = None
    volume: Optional[float] = None
    style: Optional[str] = None


@app.get("/")
def read_root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>speak-voice Web Console</h1><p>Static files not found yet.</p>")


@app.get("/api/engines")
def list_engines():
    """サポートされている音声合成エンジンと動作ステータスの一覧を返します。"""
    result = []
    for key, engine_cls in ENGINES.items():
        try:
            inst = engine_cls()
            available = inst.is_available()
            name = inst.engine_name
        except Exception:
            available = False
            name = key.upper()
        result.append({"key": key, "name": name, "available": available})
    return result


@app.get("/api/models")
def list_models(provider: str, base_url: Optional[str] = None):
    """ローカルLLMで利用可能なモデル一覧を返します。"""
    try:
        if provider == "ollama":
            url = base_url or "http://localhost:11434/v1"
            models = get_ollama_models(url)
        elif provider == "local":
            url = base_url or "http://localhost:1234/v1"
            models = get_openai_compatible_models(url)
        else:
            return {"models": []}
        return {"models": models}
    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"モデル一覧を取得できませんでした: {error}",
        ) from error


@app.get("/api/engine-settings")
def engine_settings(engine: str, speaker: Optional[str] = None):
    """選択エンジンで利用できる調声項目と範囲を返します。"""
    engine_key = engine.lower()
    if engine_key not in ENGINES:
        raise HTTPException(status_code=400, detail=f"Unknown engine: {engine}")

    emotions = []
    if engine_key == "voicepeak" and speaker:
        instance = ENGINES[engine_key]()
        if isinstance(instance, VoicepeakEngine):
            emotions = instance.get_emotions(speaker)

    return {
        "parameters": ENGINE_PARAMETERS[engine_key],
        "emotions": emotions,
    }


@app.get("/api/speakers")
def list_speakers(engine: str = Query(..., description="Engine key (e.g. voicevox)")):
    """指定された音声合成エンジンの利用可能な話者/キャラクター一覧を返します。"""
    engine_key = engine.lower()
    if engine_key not in ENGINES:
        raise HTTPException(status_code=400, detail=f"Unknown engine: {engine}")

    try:
        inst = ENGINES[engine_key]()
        speakers = inst.get_speakers()
        return [
            {
                "id": s.id,
                "name": s.name,
                "styles": s.styles,
                "speaker_name": s.raw_info.get("speakerName"),
                "style_name": s.raw_info.get("styleName"),
                "version": s.raw_info.get("version"),
            }
            for s in speakers
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch speakers: {str(e)}")


@app.post("/api/speak")
def speak_text(req: SpeakRequest):
    """指定されたパラメータでテキストを合成し、サーバーのスピーカーから再生します。"""
    engine_key = req.engine.lower()
    if engine_key not in ENGINES:
        raise HTTPException(status_code=400, detail=f"Unknown engine: {req.engine}")

    options = {
        "speed": req.speed,
        "pitch": req.pitch,
        "intonation": req.intonation,
        "volume": req.volume,
        "style": req.style,
    }

    result = SpeakResult() if req.wait else None
    speak_queue.put((engine_key, req.speaker, req.text, options, result))

    if result:
        result.done.wait()
        if result.error:
            raise HTTPException(
                status_code=500,
                detail=f"Speech synthesis or playback failed: {result.error}",
            )
        return {"status": "success", "queued": False, "completed": True}

    return {"status": "queued", "queued": True, "completed": False}


@app.post("/api/hook/speak")
def hook_speak(req: SpeakRequest):
    """外部ブラウザ拡張機能、他エージェントアプリ、クリップボード等からのテキストフック用エンドポイント。"""
    return speak_text(req)


@app.post("/api/chat")
def chat_and_speak(req: ChatRequest, request: Request):
    """AI応答をNDJSONで逐次返しながら、文単位で音声再生します。"""
    engine_key = req.engine.lower()
    if engine_key not in ENGINES:
        raise HTTPException(status_code=400, detail=f"Unknown engine: {req.engine}")

    # 音声ブリッジの準備
    try:
        engine_inst = ENGINES[engine_key]()
        bridge = VoiceAgentBridge(
            engine=engine_inst,
            speaker_id=req.speaker,
            speed=req.speed,
            pitch=req.pitch,
            intonation=req.intonation,
            volume=req.volume,
            style=req.style,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize voice bridge: {str(e)}")

    # モックエージェント用の簡単な応答ロジック
    def mock_stream():
        responses = [
            "こんにちは！",
            "私は音声合成コンソールのモックエージェントです。",
            "入力されたプロンプトを受け取りました。",
            f"あなたのプロンプトは「{req.prompt}」ですね。",
            "このように、AIエージェントの会話テキストを自動で読み上げます。",
        ]
        import time

        for phrase in responses:
            yield phrase + " "
            time.sleep(0.8)

    # API連携の実行
    stream_queue: queue.Queue = queue.Queue()
    disconnected = threading.Event()

    def emit_text(text: str):
        if disconnected.is_set():
            bridge.cancel()
            raise RuntimeError("ブラウザとの接続が切断されたため生成を停止しました。")
        stream_queue.put({"type": "text", "text": text})

    def run_bridge():
        bridge.start()
        try:
            provider = req.api_provider.lower()
            if provider in ("ollama", "local"):
                # ローカルLLM (Ollama / LM Studio / Local OpenAI API)
                base_url = req.base_url or "http://localhost:11434/v1"
                model_name = req.model_name
                if provider == "ollama" and not model_name:
                    installed_models = get_ollama_models(base_url)
                    if not installed_models:
                        raise RuntimeError(
                            "Ollamaに利用可能なモデルがありません。"
                            "`ollama pull <モデル名>`でモデルを取得してください。"
                        )
                    model_name = installed_models[0]
                elif not model_name:
                    model_name = "local-model"
                api_key = req.api_key or "ollama"

                # OpenAI SDKを用いたローカルOpenAI互換呼び出し
                try:
                    from openai import OpenAI

                    client = OpenAI(base_url=base_url, api_key=api_key)
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": req.prompt}],
                        stream=True,
                    )

                    def local_stream_gen():
                        for chunk in response:
                            if chunk.choices and chunk.choices[0].delta.content:
                                content = chunk.choices[0].delta.content
                                emit_text(content)
                                yield content

                    bridge.speak_stream(local_stream_gen())

                except Exception as sdk_err:
                    print(f"[Local LLM SDK Error, fallback to REST API]: {sdk_err}")
                    # Ollama REST API (`/api/generate` または `/api/chat`) への直接フォールバック
                    ollama_native_url = f"{ollama_root_url(base_url)}/api/chat"
                    payload = {
                        "model": model_name,
                        "messages": [{"role": "user", "content": req.prompt}],
                        "stream": True,
                    }
                    resp = requests.post(ollama_native_url, json=payload, stream=True, timeout=60)
                    if not resp.ok:
                        raise ollama_http_error(resp)

                    import json

                    def ollama_rest_gen():
                        for line in resp.iter_lines():
                            if line:
                                data = json.loads(line.decode("utf-8"))
                                msg_content = data.get("message", {}).get("content", "")
                                if msg_content:
                                    emit_text(msg_content)
                                    yield msg_content

                    bridge.speak_stream(ollama_rest_gen())

            elif provider == "openai":
                if not req.api_key:
                    raise ValueError("OpenAI APIキーが入力されていません。")
                from openai import OpenAI

                client = OpenAI(api_key=req.api_key)
                model_name = req.model_name or "gpt-4o-mini"
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": req.prompt}],
                    stream=True,
                )

                def openai_gen():
                    for chunk in response:
                        content = chunk.choices[0].delta.content
                        if content:
                            emit_text(content)
                            yield content

                bridge.speak_stream(openai_gen())

            elif provider == "gemini":
                if not req.api_key:
                    raise ValueError("Gemini APIキーが入力されていません。")

                # 新旧Google GenAI SDKの互換処理
                has_new_sdk = False
                try:
                    from google import genai

                    has_new_sdk = True
                except ImportError:
                    has_new_sdk = False

                if has_new_sdk:
                    from google import genai

                    client = genai.Client(api_key=req.api_key)

                    candidates = []
                    # 1. ユーザーが画面で明示的に指定したモデル名
                    if req.model_name:
                        candidates.append(req.model_name)

                    # 2. APIから実際に利用可能なモデル一覧を動的に取得して最優先で追加
                    try:
                        for m in client.models.list():
                            m_clean = getattr(m, "name", "").replace("models/", "")
                            if m_clean and ("flash" in m_clean.lower() or "pro" in m_clean.lower()):
                                if m_clean not in candidates:
                                    candidates.append(m_clean)
                    except Exception:
                        pass

                    if not candidates:
                        raise RuntimeError(
                            "利用可能なGeminiモデルを取得できませんでした。"
                            "モデル名を明示してください。"
                        )

                    response_chunks = []
                    last_err = None
                    used_model = None
                    for m_name in candidates:
                        try:
                            stream = client.models.generate_content_stream(
                                model=m_name, contents=req.prompt
                            )
                            # ストリーミング初期化時の404エラーなどを事前にキャッチするため最初のチャンクを取得
                            stream_iter = iter(stream)
                            first_chunk = next(stream_iter, None)
                            used_model = m_name

                            def make_gen(first, it):
                                if first is not None:
                                    yield first
                                yield from it

                            response_chunks = make_gen(first_chunk, stream_iter)
                            break
                        except Exception as e:
                            last_err = e

                    if used_model is None:
                        raise last_err or RuntimeError("Geminiモデルの呼び出しに失敗しました。")

                    print(f"[Gemini API]: Successfully used model '{used_model}'")

                    def gemini_gen():
                        for chunk in response_chunks:
                            if hasattr(chunk, "text") and chunk.text:
                                emit_text(chunk.text)
                                yield chunk.text

                    bridge.speak_stream(gemini_gen())
                else:
                    import google.generativeai as genai

                    genai.configure(api_key=req.api_key)

                    candidates = []
                    if req.model_name:
                        candidates.append(req.model_name)

                    try:
                        for m in genai.list_models():
                            m_clean = m.name.replace("models/", "")
                            if "generateContent" in getattr(m, "supported_generation_methods", []):
                                if m_clean not in candidates:
                                    candidates.append(m_clean)
                    except Exception:
                        pass
                    if not candidates:
                        raise RuntimeError(
                            "利用可能なGeminiモデルを取得できませんでした。"
                            "モデル名を明示してください。"
                        )

                    response = None
                    last_err = None
                    for m_name in candidates:
                        try:
                            model = genai.GenerativeModel(m_name)
                            response = model.generate_content(req.prompt, stream=True)
                            break
                        except Exception as e:
                            last_err = e

                    if response is None:
                        raise last_err or RuntimeError("Geminiモデルの呼び出しに失敗しました。")

                    def legacy_gemini_gen():
                        for chunk in response:
                            if chunk.text:
                                emit_text(chunk.text)
                                yield chunk.text

                    bridge.speak_stream(legacy_gemini_gen())

            else:  # mock

                def mock_gen():
                    for text in mock_stream():
                        emit_text(text)
                        yield text

                bridge.speak_stream(mock_gen())

            bridge.wait_until_done()
        finally:
            bridge.stop()

    def run_and_report():
        try:
            run_bridge()
            stream_queue.put({"type": "done"})
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            print(f"[Error in chat_and_speak]: {error_msg}")
            stream_queue.put({"type": "error", "detail": error_msg})
        finally:
            stream_queue.put(None)

    async def event_stream():
        thread = threading.Thread(target=run_and_report, daemon=True)
        thread.start()
        try:
            while True:
                if await request.is_disconnected():
                    disconnected.set()
                    bridge.cancel()
                    break
                try:
                    event = stream_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.05)
                    continue
                if event is None:
                    break
                yield json.dumps(event, ensure_ascii=False) + "\n"
        finally:
            disconnected.set()
            bridge.cancel()

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


def start():
    """Webサーバーを起動するためのエントリポイント"""
    uvicorn.run("speak_voice.web.app:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    start()
