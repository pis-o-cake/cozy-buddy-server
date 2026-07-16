"""PC 테스트 클라이언트 — 허브 없이 음성 루프 검증 + SLA 실측 (설계서 §14-2 Phase 1).

사용 예:
    python scripts/test_client.py --text "불 꺼줘"
    python scripts/test_client.py --wav sample.wav          # 16kHz mono 16bit PCM
    python scripts/test_client.py --wav sample.wav --token <device_token>

--token 미지정 시 페어링부터 자동 수행하고 발급된 device token을 출력한다(재사용 권장).
수신한 TTS 오디오는 --out(기본 out.wav)에 저장된다.
"""

import argparse
import asyncio
import json
import time
import uuid
import wave
from pathlib import Path

import httpx
import websockets

FRAME_SAMPLES = 320  # 20ms @ 16kHz


def obtain_device_token(server: str, hub_id: str) -> str:
    with httpx.Client(base_url=server, timeout=10) as client:
        code = client.post("/api/auth/pairing").json()["code"]
        response = client.post(
            "/api/auth/pair", json={"code": code, "hub_id": hub_id, "name": "PC 테스트"}
        )
        response.raise_for_status()
        token = response.json()["device_token"]
        print(f"[pair] hub_id={hub_id} device_token={token}")
        return token


def obtain_jwt(server: str, device_token: str) -> str:
    with httpx.Client(base_url=server, timeout=10) as client:
        response = client.post("/api/auth/token", json={"device_token": device_token})
        response.raise_for_status()
        return response.json()["access_token"]


def load_wav_frames(path: Path) -> list[bytes]:
    with wave.open(str(path), "rb") as wav:
        assert wav.getframerate() == 16000, "16kHz wav가 필요합니다"
        assert wav.getnchannels() == 1, "mono wav가 필요합니다"
        assert wav.getsampwidth() == 2, "16bit PCM wav가 필요합니다"
        pcm = wav.readframes(wav.getnframes())
    step = FRAME_SAMPLES * 2
    return [pcm[i : i + step] for i in range(0, len(pcm), step)]


async def run(args: argparse.Namespace) -> None:
    device_token = args.token or obtain_device_token(args.server, args.hub_id)
    jwt_token = obtain_jwt(args.server, device_token)
    ws_url = args.server.replace("http", "ws", 1) + "/ws/hub"

    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.send(json.dumps({"type": "auth", "token": jwt_token}))
        auth_ok = json.loads(await ws.recv())
        assert auth_ok["type"] == "auth.ok", auth_ok
        print(f"[auth] ok (room={auth_ok.get('room')})")

        session_id = uuid.uuid4().hex[:8]
        if args.wav:
            frames = load_wav_frames(Path(args.wav))
            await ws.send(
                json.dumps(
                    {
                        "type": "utterance.start",
                        "session_id": session_id,
                        "audio": {"codec": "pcm16", "rate": 16000, "ch": 1},
                    }
                )
            )
            for frame in frames:
                await ws.send(b"\x01" + frame)
            await ws.send(json.dumps({"type": "utterance.end", "session_id": session_id}))
            print(f"[send] {len(frames)} frames ({len(frames) * 20}ms)")
        else:
            await ws.send(
                json.dumps({"type": "text.query", "session_id": session_id, "text": args.text})
            )
            print(f"[send] text.query: {args.text}")

        t0 = time.perf_counter()
        marks: dict[str, float] = {}
        audio = bytearray()
        rate = 24000
        idle_seen = False

        while not idle_seen:
            message = await asyncio.wait_for(ws.recv(), timeout=60)
            elapsed = time.perf_counter() - t0
            if isinstance(message, bytes):
                if message[:1] == b"\x02":
                    marks.setdefault("first_audio", elapsed)
                    audio.extend(message[1:])
                continue
            data = json.loads(message)
            match data["type"]:
                case "stt.final":
                    marks.setdefault("stt.final", elapsed)
                    confidence = data.get("confidence")
                    print(f"[{elapsed:6.2f}s] stt.final: {data['text']} (conf={confidence})")
                case "llm.delta":
                    marks.setdefault("first_llm_delta", elapsed)
                case "tts.start":
                    marks.setdefault("tts.start", elapsed)
                    rate = data.get("rate", rate)
                case "tool.status":
                    print(f"[{elapsed:6.2f}s] tool: {data['tool']} → {data['status']}")
                case "response":
                    marks.setdefault("response", elapsed)
                    print(f"[{elapsed:6.2f}s] response: {data['text']}")
                case "error":
                    print(f"[{elapsed:6.2f}s] ERROR {data['code']}: {data.get('message')}")
                case "state":
                    if data["value"] == "idle" and "response" in marks:
                        idle_seen = True

        print("\n── SLA (발화종료/질의 → 각 단계, 설계서 §12-2) ──")
        for name in ("stt.final", "first_llm_delta", "tts.start", "first_audio", "response"):
            if name in marks:
                print(f"  {name:>16}: {marks[name] * 1000:7.0f} ms")

        if audio:
            out = Path(args.out)
            with wave.open(str(out), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(rate)
                wav.writeframes(bytes(audio))
            print(f"\n[audio] {len(audio)} bytes → {out} (rate={rate})")


def main() -> None:
    parser = argparse.ArgumentParser(description="cozy-buddy voice loop test client")
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--hub-id", default=f"pctest-{uuid.uuid4().hex[:6]}")
    parser.add_argument("--token", help="기존 device token 재사용")
    parser.add_argument("--text", help="텍스트 질의 (STT 우회)")
    parser.add_argument("--wav", help="16kHz mono 16bit wav 파일 전송")
    parser.add_argument("--out", default="out.wav", help="수신 TTS 저장 경로")
    args = parser.parse_args()
    if not args.text and not args.wav:
        parser.error("--text 또는 --wav 중 하나가 필요합니다")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
