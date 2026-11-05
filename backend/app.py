"""HTTP JSON-RPC backend for the yt-dlp-webui Electron app.

Spawned by electron-main.py. Listens on 127.0.0.1:<random port>, prints
"PORT:<port>" to stdout once ready, then serves /rpc POST endpoints.
"""
from __future__ import annotations

import http.server
import json
import os
import socket
import sys
import threading
from typing import Any, Callable, Dict, Optional

# Ensure backend package imports work when run as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config, save_config, USER_CONFIG_PATH  # noqa: E402
from extractor import extract_info, search  # noqa: E402
from downloader import (  # noqa: E402
    DownloadManager,
    JOB_COMPLETED, JOB_FAILED, JOB_CANCELLED,
)
from library import init_db, add_item, list_items, get_item, delete_item, set_favorite, increment_play  # noqa: E402


# --------------------------------------------------------------------------- #
# Global state
# --------------------------------------------------------------------------- #
manager: Optional[DownloadManager] = None
EVENT_SUBSCRIBERS: list[Callable[[Dict[str, Any]], None]] = []


def emit_event(event: Dict[str, Any]) -> None:
    for cb in list(EVENT_SUBSCRIBERS):
        try:
            cb(event)
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# RPC method handlers
# --------------------------------------------------------------------------- #
def rpc_config_get(_params: Dict[str, Any]) -> Dict[str, Any]:
    return load_config()


def rpc_config_set(params: Dict[str, Any]) -> Dict[str, Any]:
    key = params.get('key')
    value = params.get('value')
    if not key:
        raise ValueError('key is required')
    cfg = load_config()
    # support dotted keys like "downloads.concurrent_downloads"
    parts = key.split('.')
    d = cfg
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = value
    save_config(cfg)
    global manager
    if manager:
        manager.config = cfg
    return {'ok': True, 'config': cfg}


def rpc_config_reset(_params: Dict[str, Any]) -> Dict[str, Any]:
    defaults_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.default.json')
    import json
    with open(defaults_path, 'r', encoding='utf-8') as f:
        defaults = json.load(f)
    save_config(defaults)
    global manager
    if manager:
        manager.config = defaults
    return {'ok': True, 'config': defaults}


def rpc_search(params: Dict[str, Any]) -> Dict[str, Any]:
    q = params.get('q', '')
    max_results = int(params.get('max_results', 20))
    results = search(q, max_results=max_results)
    return {'results': results}


def rpc_video_info(params: Dict[str, Any]) -> Dict[str, Any]:
    url = params.get('url')
    if not url:
        raise ValueError('url is required')
    info = extract_info(url)
    return {'info': info}


def rpc_download_create(params: Dict[str, Any]) -> Dict[str, Any]:
    url = params.get('url')
    if not url:
        raise ValueError('url is required')
    overrides = params.get('config_overrides') or {}
    priority = params.get('priority', 'normal')
    job_id = manager.create_job(url, overrides, priority=priority)
    return {'job_id': job_id}


def rpc_download_list(_params: Dict[str, Any]) -> Dict[str, Any]:
    return {'jobs': manager.list_jobs()}


def rpc_download_control(params: Dict[str, Any]) -> Dict[str, Any]:
    job_id = params.get('job_id')
    action = params.get('action')
    if not job_id or not action:
        raise ValueError('job_id and action required')
    ok = manager.control(job_id, action)
    return {'ok': ok}


def rpc_download_remove(params: Dict[str, Any]) -> Dict[str, Any]:
    job_id = params.get('job_id')
    delete_file = bool(params.get('delete_file', False))
    if not job_id:
        raise ValueError('job_id required')
    ok = manager.remove_job(job_id, delete_file=delete_file)
    return {'ok': ok}


def rpc_library_list(params: Dict[str, Any]) -> Dict[str, Any]:
    query = params.get('query')
    favorite_only = bool(params.get('favorite_only', False))
    return {'items': list_items(query=query, favorite_only=favorite_only)}


def rpc_library_action(params: Dict[str, Any]) -> Dict[str, Any]:
    item_id = params.get('item_id')
    action = params.get('action')
    if item_id is None or not action:
        raise ValueError('item_id and action required')

    if action == 'delete':
        delete_file = bool(params.get('delete_file', False))
        ok = delete_item(int(item_id), delete_file=delete_file)
        return {'ok': ok}

    if action == 'favorite':
        fav = bool(params.get('favorite', True))
        ok = set_favorite(int(item_id), fav)
        return {'ok': ok}

    if action == 'play':
        increment_play(int(item_id))
        item = get_item(int(item_id))
        return {'ok': True, 'item': item}

    if action == 'get':
        item = get_item(int(item_id))
        if not item:
            raise ValueError('item not found')
        return {'ok': True, 'item': item}

    raise ValueError(f'unknown action: {action}')


METHODS: Dict[str, Callable[[Dict[str, Any]], Any]] = {
    'config.get': rpc_config_get,
    'config.set': rpc_config_set,
    'config.reset': rpc_config_reset,
    'search.query': rpc_search,
    'video.info': rpc_video_info,
    'download.create': rpc_download_create,
    'download.list': rpc_download_list,
    'download.control': rpc_download_control,
    'download.remove': rpc_download_remove,
    'library.list': rpc_library_list,
    'library.action': rpc_library_action,
}


# --------------------------------------------------------------------------- #
# HTTP server
# --------------------------------------------------------------------------- #
class RPCHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: ARG002
        return  # silence default logging

    def _send(self, code: int, body: Dict[str, Any]) -> None:
        data = json.dumps(body).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != '/rpc':
            self._send(404, {'jsonrpc': '2.0', 'error': {'message': 'not found'}, 'id': None})
            return
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length) if length else b'{}'
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            self._send(400, {'jsonrpc': '2.0', 'error': {'message': 'invalid json'}, 'id': None})
            return

        method = req.get('method')
        params = req.get('params') or {}
        req_id = req.get('id')

        handler = METHODS.get(method)
        if not handler:
            self._send(200, {'jsonrpc': '2.0', 'error': {'message': f'method not found: {method}'}, 'id': req_id})
            return

        try:
            result = handler(params)
            self._send(200, {'jsonrpc': '2.0', 'result': result, 'id': req_id})
        except Exception as e:  # noqa: BLE001
            self._send(200, {'jsonrpc': '2.0', 'error': {'message': str(e)}, 'id': req_id})


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _resolve_ffmpeg() -> Optional[str]:
    """Locate bundled ffmpeg next to the backend, falling back to system PATH."""
    # Bundled: backend/app.py -> ../ffmpeg/bin/ffmpeg.exe (dev and prod layout)
    here = os.path.dirname(os.path.abspath(__file__))
    bundled = os.path.join(here, '..', 'ffmpeg', 'bin', 'ffmpeg.exe')
    if os.path.exists(bundled):
        return os.path.abspath(bundled)
    # System fallback
    import shutil
    system = shutil.which('ffmpeg')
    return system


def main() -> None:
    global manager

    ffmpeg_path = _resolve_ffmpeg()
    if ffmpeg_path:
        print(f'FFMPEG:{ffmpeg_path}', flush=True)
    else:
        print('FFMPEG:NOT_FOUND', flush=True)

    init_db()

    # Event bridge: manager pushes events -> HTTP subscribers (long-poll via /events)
    event_queue: list[Dict[str, Any]] = []
    queue_lock = threading.Lock()

    def on_event(event: Dict[str, Any]) -> None:
        with queue_lock:
            event_queue.append(event)
            # keep only last 200
            if len(event_queue) > 200:
                del event_queue[:-200]

    manager = DownloadManager(on_event=on_event)

    class HandlerWithEvents(RPCHandler):
        def do_GET(self):  # noqa: N802
            if self.path == '/events':
                # Simple long-poll: wait up to 25s for an event
                import time
                deadline = time.time() + 25
                while time.time() < deadline:
                    with queue_lock:
                        if event_queue:
                            ev = event_queue.pop(0)
                            data = json.dumps(ev).encode('utf-8')
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/json')
                            self.send_header('Content-Length', str(len(data)))
                            self.end_headers()
                            self.wfile.write(data)
                            return
                    time.sleep(0.25)
                # timeout - empty response
                self.send_response(204)
                self.end_headers()
            else:
                self._send(404, {'error': 'not found'})

    port = find_free_port()
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), HandlerWithEvents)
    print(f'PORT:{port}', flush=True)

    # Run manager shutdown on server stop
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        manager.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
