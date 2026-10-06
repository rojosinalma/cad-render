"""Zoo text-to-CAD.

Zoo's REST ``POST /ai/text-to-cad/{format}`` is gone (404 on 2026-10-06; only the read side
``GET /user/text-to-cad/{id}`` is left in the OpenAPI spec). The supported path is the ML copilot
websocket, which returns KCL, followed by the pinned ``zoo`` CLI turning the KCL into a file through
Zoo's Engine API. This worker does both and reports the copilot ids so a run can be traced on
zoo.dev. Format ``kcl`` returns the generated source itself.

Env (set by lib/worker.rb): ZOO_API_TOKEN, ZOO_API_URL, ZOO_POLL_S (ping interval), ZOO_TIMEOUT_S.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import EXIT_OK, fail, log, parser, write_meta  # noqa: E402
import exporters  # noqa: E402
import loaders  # noqa: E402

TOKEN = os.environ.get("ZOO_API_TOKEN", "")
API_URL = os.environ.get("ZOO_API_URL", "https://api.zoo.dev")
PING_S = float(os.environ.get("ZOO_POLL_S", "5"))
TIMEOUT_S = float(os.environ.get("ZOO_TIMEOUT_S", "600"))
EXPORT_FORMATS = {"step": "step", "stl": "stl", "3mf": None, "obj": "obj", "ply": "ply", "glb": "glb"}


class ZooError(Exception):
    pass


def ws_url() -> str:
    base = API_URL.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
    return f"{base}/ws/ml/copilot"


async def prompt_copilot(prompt: str) -> dict:
    import websockets

    out = {"files": {}, "conversation_id": None, "api_call_id": None, "text": ""}
    log("zoo", f"WS {ws_url()} user prompt ({len(prompt)} chars)")
    async with websockets.connect(ws_url(), max_size=64 * 1024 * 1024,
                                  additional_headers={"Authorization": f"Bearer {TOKEN}"}) as ws:
        await ws.send(json.dumps({"type": "user", "content": prompt, "forced_tools": ["text_to_cad"],
                                  "project_name": "cad-render"}))

        async def pinger():
            while True:
                await asyncio.sleep(PING_S)
                await ws.send(json.dumps({"type": "ping"}))

        ping = asyncio.create_task(pinger())
        try:
            async for raw in ws:
                msg = json.loads(raw)
                kind = next(iter(msg))
                body = msg[kind]
                if kind == "session_data":
                    out["api_call_id"] = body.get("api_call_id")
                elif kind == "conversation_id":
                    out["conversation_id"] = body.get("conversation_id")
                elif kind == "tool_output":
                    res = body.get("result", {})
                    if res.get("error"):
                        log("zoo", f"tool {res.get('type')} error: {res['error']}")
                    out["files"].update(res.get("outputs") or {})
                elif kind == "project_updated":
                    out["files"].update(body.get("files") or {})
                elif kind == "reasoning":
                    content = body.get("content", "")
                    if body.get("type") == "text":
                        log("zoo", content.strip()[:200])
                elif kind == "error":
                    raise ZooError(body.get("detail", "copilot error"))
                elif kind == "access_denied":
                    raise ZooError(f"access denied ({body.get('code')}): {body.get('detail')}")
                elif kind == "backend_shutdown":
                    raise ZooError(f"copilot backend shut down: {body.get('reason')}")
                elif kind == "end_of_stream":
                    out["text"] = body.get("whole_response", "")
                    break
        finally:
            ping.cancel()
    return out


def export_kcl(kcl_dir: str, fmt: str, out_dir: str) -> str:
    zoo = shutil.which("zoo")
    if not zoo:
        raise ZooError("zoo CLI not installed in the worker image")
    os.makedirs(out_dir, exist_ok=True)
    cmd = [zoo, "kcl", "export", f"--output-format={fmt}", os.path.join(kcl_dir, "main.kcl"), out_dir]
    log("zoo", f"exec {' '.join(cmd[1:])}")
    env = {**os.environ, "ZOO_API_TOKEN": TOKEN, "ZOO_HOST": API_URL.replace("https://", "").replace("http://", "")}
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S, env=env)
    if r.stdout.strip():
        log("zoo", r.stdout.strip()[:500])
    if r.returncode != 0:
        raise ZooError(f"zoo kcl export failed: {(r.stderr or r.stdout).strip()[:500]}")
    files = [f for f in os.listdir(out_dir) if f.lower().endswith(f".{fmt}")]
    if not files:
        raise ZooError(f"zoo kcl export produced no .{fmt} file")
    return os.path.join(out_dir, sorted(files)[0])


def main() -> int:
    p = parser("Zoo text-to-CAD")
    p.add_argument("--prompt", required=True)
    a = p.parse_args()
    if not TOKEN:
        return fail(a.meta, "ZOO_API_TOKEN is not set")
    if a.format not in EXPORT_FORMATS and a.format != "kcl":
        return fail(a.meta, f"unsupported zoo format {a.format!r}")

    t0 = time.monotonic()
    try:
        res = asyncio.run(asyncio.wait_for(prompt_copilot(a.prompt), timeout=TIMEOUT_S))
    except asyncio.TimeoutError:
        return fail(a.meta, f"Zoo copilot did not finish within {TIMEOUT_S:.0f}s")
    except ZooError as e:
        return fail(a.meta, f"Zoo: {e}")
    except Exception as e:  # noqa: BLE001
        return fail(a.meta, f"Zoo websocket failed: {type(e).__name__}: {e}")
    ids = {"zoo_id": res["api_call_id"], "zoo_conversation_id": res["conversation_id"]}
    kcl = res["files"].get("main.kcl") or next((v for k, v in res["files"].items() if k.endswith(".kcl")), None)
    if not kcl:
        return fail(a.meta, f"Zoo returned no KCL: {res['text'][:300] or 'no response text'}", **ids)
    log("zoo", f"copilot done in {time.monotonic() - t0:.1f}s, {len(kcl)} bytes of KCL")

    kcl_dir = os.path.join(os.getcwd(), "zoo-kcl")
    os.makedirs(kcl_dir, exist_ok=True)
    with open(os.path.join(kcl_dir, "main.kcl"), "w") as f:
        f.write(kcl)
    if a.format == "kcl":
        shutil.copy(os.path.join(kcl_dir, "main.kcl"), a.out)
        write_meta(a.meta, ok=True, empty=False, warnings=[], kcl=kcl, **ids)
        return EXIT_OK

    # 3MF is not a Zoo export format: go through STL and re-export.
    native = EXPORT_FORMATS[a.format] or "stl"
    try:
        produced = export_kcl(kcl_dir, native, os.path.join(os.getcwd(), "zoo-out"))
    except ZooError as e:
        return fail(a.meta, str(e), kcl=kcl, **ids)
    except subprocess.TimeoutExpired:
        return fail(a.meta, f"zoo kcl export exceeded {TIMEOUT_S:.0f}s", kcl=kcl, **ids)

    warnings: list[str] = []
    try:
        obj = loaders.load(produced)
        m = exporters.metrics(obj)
    except Exception as e:  # noqa: BLE001 - metrics are best effort; the file itself is the result
        warnings.append(f"could not measure result: {type(e).__name__}: {e}")
        m, obj = {}, None
    if native == a.format:
        shutil.copy(produced, a.out)
    else:
        if obj is None:
            return fail(a.meta, f"cannot re-export to {a.format}: {warnings[-1]}", kcl=kcl, **ids)
        exporters.export(obj, a.format, a.out)
    write_meta(a.meta, ok=True, empty=False, warnings=warnings, kcl=kcl, **ids, **m)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
