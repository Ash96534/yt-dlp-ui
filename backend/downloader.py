"""yt-dlp download engine with progress hooks, concurrency, pause/resume/cancel."""
from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

import yt_dlp

from config import deep_merge, load_config, save_config, USER_CONFIG_PATH
from job_queue import JobQueue, PRIORITY_ORDER

# --------------------------------------------------------------------------- #
# Job state machine
# --------------------------------------------------------------------------- #
JOB_QUEUED = 'queued'
JOB_RUNNING = 'running'
JOB_PAUSED = 'paused'
JOB_COMPLETED = 'completed'
JOB_FAILED = 'failed'
JOB_CANCELLED = 'cancelled'

VALID_TRANSITIONS = {
    JOB_QUEUED: {JOB_RUNNING, JOB_CANCELLED},
    JOB_RUNNING: {JOB_PAUSED, JOB_COMPLETED, JOB_FAILED},
    JOB_PAUSED: {JOB_RUNNING, JOB_CANCELLED},
    JOB_COMPLETED: set(),
    JOB_FAILED: {JOB_QUEUED},       # retry
    JOB_CANCELLED: set(),
}


@dataclass
class DownloadJob:
    job_id: str
    url: str
    title: str = ''
    status: str = JOB_QUEUED
    progress: float = 0.0
    speed: str = ''
    eta: str = ''
    downloaded_bytes: int = 0
    total_bytes: Optional[int] = None
    filepath: Optional[str] = None
    error: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    priority: str = 'normal'
    attempts: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Download manager
# --------------------------------------------------------------------------- #
class DownloadManager:
    def __init__(self, on_event: Callable[[Dict[str, Any]], None]):
        self.on_event = on_event
        self.config = load_config()
        self.queue = JobQueue()
        self.jobs: Dict[str, DownloadJob] = {}
        self._lock = threading.Lock()
        self._workers: List[threading.Thread] = []
        self._stop = threading.Event()
        self._active: Dict[str, yt_dlp.YoutubeDL] = {}  # job_id -> running ydl
        self._start_workers()

    # -- lifecycle ---------------------------------------------------------- #
    def _start_workers(self) -> None:
        n = int(self.config.get('downloads', {}).get('concurrent_downloads', 3))
        self._stop.clear()
        for _ in range(n):
            t = threading.Thread(target=self._worker_loop, daemon=True)
            t.start()
            self._workers.append(t)

    def shutdown(self) -> None:
        self._stop.set()
        self.queue._condition.notify_all()

    # -- public API --------------------------------------------------------- #
    def create_job(self, url: str, config_overrides: Optional[Dict[str, Any]] = None,
                   priority: str = 'normal') -> str:
        job_id = str(uuid.uuid4())
        merged_config = deep_merge(self.config, config_overrides or {})
        job = DownloadJob(
            job_id=job_id,
            url=url,
            status=JOB_QUEUED,
            config=merged_config,
            priority=priority,
        )
        with self._lock:
            self.jobs[job_id] = job
        self.queue.push(job_id, {'url': url, 'config': merged_config}, priority=priority)
        self._emit('download:created', job.to_dict())
        return job_id

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [j.to_dict() for j in self.jobs.values()]

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            j = self.jobs.get(job_id)
            return j.to_dict() if j else None

    def control(self, job_id: str, action: str) -> bool:
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return False
            current = job.status

        if action == 'pause':
            if current not in (JOB_RUNNING,):
                return False
            self._set_status(job_id, JOB_PAUSED)
            # Signal the active yt-dlp to stop via its own mechanism handled in worker
            return True

        if action == 'resume':
            if current not in (JOB_PAUSED, JOB_FAILED):
                return False
            self._set_status(job_id, JOB_QUEUED)
            job = self.jobs.get(job_id)
            if job:
                job.attempts += 1
                job.progress = 0.0
                job.error = None
            self.queue.push(job_id, {'url': job.url, 'config': job.config}, priority=job.priority)
            self._emit('download:created', job.to_dict())
            return True

        if action == 'cancel':
            if current in (JOB_COMPLETED, JOB_CANCELLED):
                return False
            self._set_status(job_id, JOB_CANCELLED)
            ydl = self._active.pop(job_id, None)
            if ydl:
                # yt-dlp checks this to abort
                ydl._abort_download = True  # type: ignore[attr-defined]
            return True

        if action == 'retry':
            if current not in (JOB_FAILED, JOB_CANCELLED):
                return False
            self._set_status(job_id, JOB_QUEUED)
            job = self.jobs.get(job_id)
            if job:
                job.attempts += 1
                job.progress = 0.0
                job.error = None
                job.filepath = None
            self.queue.push(job_id, {'url': job.url, 'config': job.config}, priority=job.priority)
            return True

        return False

    def remove_job(self, job_id: str, delete_file: bool = False) -> bool:
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return False
            filepath = job.filepath
            self.queue.remove(job_id)
            del self.jobs[job_id]
        if delete_file and filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        self._emit('download:removed', {'job_id': job_id})
        return True

    # -- internal ----------------------------------------------------------- #
    def _set_status(self, job_id: str, status: str) -> None:
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return
            job.status = status
            job.updated_at = time.time()
            snapshot = job.to_dict()
        self._emit('download:status', {'job_id': job_id, 'status': status, 'job': snapshot})

    def _emit(self, event: str, payload: Dict[str, Any]) -> None:
        try:
            self.on_event({'event': event, **payload})
        except Exception:
            pass

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            item = self.queue.pop(block=True, timeout=1.0)
            if item is None:
                continue
            job_id = item.job_id
            data = item.data or {}
            url = data.get('url')
            config = data.get('config', {})

            with self._lock:
                job = self.jobs.get(job_id)
            if not job or job.status != JOB_QUEUED:
                continue

            self._run_download(job_id, url, config)

    def _run_download(self, job_id: str, url: str, config: Dict[str, Any]) -> None:
        self._set_status(job_id, JOB_RUNNING)

        def progress_hook(d: Dict[str, Any]) -> None:
            status = d.get('status')
            if status == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                pct = (downloaded / total * 100) if total else 0.0
                speed = d.get('speed') or 0
                eta = d.get('eta') or 0
                with self._lock:
                    job = self.jobs.get(job_id)
                    if job:
                        job.progress = round(pct, 2)
                        job.speed = self._fmt_speed(speed)
                        job.eta = self._fmt_eta(eta)
                        job.downloaded_bytes = downloaded
                        job.total_bytes = total if total else None
                        snapshot = job.to_dict()
                self._emit('download:progress', {'job_id': job_id, 'job': snapshot})
            elif status == 'finished':
                with self._lock:
                    job = self.jobs.get(job_id)
                    if job:
                        job.progress = 100.0
                        snapshot = job.to_dict()
                self._emit('download:progress', {'job_id': job_id, 'job': snapshot})

        ydl_opts = self._build_ydl_opts(config, progress_hook)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                with self._lock:
                    self._active[job_id] = ydl
                    job = self.jobs.get(job_id)
                    if job:
                        job.attempts += 1
                        snapshot = job.to_dict()
                self._emit('download:started', {'job_id': job_id, 'job': snapshot})

                info = ydl.extract_info(url, download=True)

                # Check if aborted/cancelled mid-download
                with self._lock:
                    job = self.jobs.get(job_id)
                    if job and job.status == JOB_CANCELLED:
                        self._emit('download:cancelled', {'job_id': job_id})
                        self._active.pop(job_id, None)
                        return

                filepath = ydl.prepare_filename(info)
                # Post-process may change extension; try to locate actual file
                if not os.path.exists(filepath):
                    # try common post-processed extensions
                    base, _ = os.path.splitext(filepath)
                    for ext in ('.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.opus'):
                        cand = base + ext
                        if os.path.exists(cand):
                            filepath = cand
                            break

                with self._lock:
                    job = self.jobs.get(job_id)
                    if job:
                        job.status = JOB_COMPLETED
                        job.progress = 100.0
                        job.filepath = filepath
                        job.updated_at = time.time()
                        snapshot = job.to_dict()
                self._active.pop(job_id, None)
                self._emit('download:completed', {'job_id': job_id, 'job': snapshot})

        except yt_dlp.utils.DownloadError as e:
            self._handle_job_error(job_id, str(e), retryable=True)
        except Exception as e:  # noqa: BLE001
            self._handle_job_error(job_id, f'{type(e).__name__}: {e}', retryable=False)

    def _handle_job_error(self, job_id: str, message: str, retryable: bool) -> None:
        with self._lock:
            job = self.jobs.get(job_id)
            self._active.pop(job_id, None)
            if not job:
                return
            max_retries = int(self.config.get('downloads', {}).get('max_retries', 5))
            if retryable and job.attempts < max_retries and job.status != JOB_CANCELLED:
                job.status = JOB_QUEUED
                job.error = message
                job.updated_at = time.time()
                snapshot = job.to_dict()
                # requeue with backoff
                def requeue() -> None:
                    time.sleep(float(self.config.get('downloads', {}).get('retry_sleep', 10)))
                    self.queue.push(job_id, {'url': job.url, 'config': job.config}, priority=job.priority)
                threading.Thread(target=requeue, daemon=True).start()
            else:
                job.status = JOB_FAILED
                job.error = message
                job.updated_at = time.time()
                snapshot = job.to_dict()
        self._emit('download:failed', {'job_id': job_id, 'error': message, 'job': snapshot})

    # -- helpers ------------------------------------------------------------ #
    def _build_ydl_opts(self, config: Dict[str, Any], progress_hook: Callable) -> Dict[str, Any]:
        fmt_cfg = config.get('format', {})
        dl_cfg = config.get('downloads', {})
        net_cfg = config.get('network', {})
        auth_cfg = config.get('auth', {})
        post_cfg = config.get('postprocessing', {})

        outtmpl = config.get('downloads', {}).get('path_templates', {}).get(
            'video', '{download_root}/{uploader}/{title}.{ext}'
        )
        # Replace placeholders crudely; yt-dlp handles its own, but we set a root
        download_root = config.get('downloads', {}).get('default_path', '{user_home}/Downloads/YTDLP-WebUI')
        download_root = download_root.replace('{user_home}', os.path.expanduser('~'))
        os.makedirs(download_root, exist_ok=True)

        opts: Dict[str, Any] = {
            'format': fmt_cfg.get('preferred', 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'),
            'outtmpl': os.path.join(download_root, '%(title)s.%(ext)s'),
            'merge_output_format': fmt_cfg.get('merge_output_format', 'mp4'),
            'noplaylist': fmt_cfg.get('noplaylist', True),
            'ignoreerrors': fmt_cfg.get('ignore_errors', False),
            'no_warnings': fmt_cfg.get('no_warnings', False),
            'geobypass': fmt_cfg.get('geo_bypass', True),
            'retries': int(dl_cfg.get('max_retries', 5)),
            'fragment_retries': int(dl_cfg.get('fragment_retries', 10)),
            'socket_timeout': int(net_cfg.get('socket_timeout', 30)),
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
        }

        if fmt_cfg.get('audio_only'):
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = opts.get('postprocessors', []) + [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': fmt_cfg.get('audio_format', 'mp3'),
                'preferredquality': fmt_cfg.get('audio_quality', '0'),
            }]
            if fmt_cfg.get('keep_video') is False:
                opts['postprocessors'].append({'key': 'FFmpegMerger'})  # cleanup

        if fmt_cfg.get('embed_thumbnail'):
            opts['postprocessors'] = opts.get('postprocessors', []) + [
                {'key': 'EmbedThumbnail'},
                {'key': 'FFmpegMetadata'},
            ]
            opts['writethumbnail'] = True

        if fmt_cfg.get('embed_metadata'):
            opts['postprocessors'] = opts.get('postprocessors', []) + [
                {'key': 'FFmpegMetadata'},
            ]

        if fmt_cfg.get('write_subs'):
            opts['writesubtitles'] = True
            opts['subtitleslangs'] = fmt_cfg.get('subs_lang', ['en'])

        if fmt_cfg.get('write_auto_subs'):
            opts['writeautomaticsub'] = True
            opts['subtitleslangs'] = fmt_cfg.get('subs_lang', ['en'])

        if fmt_cfg.get('write_info_json'):
            opts['writeinfojson'] = True

        if auth_cfg.get('cookies_from_browser'):
            opts['cookiesfrombrowser'] = auth_cfg.get('cookies_from_browser')
        if auth_cfg.get('cookies_file'):
            opts['cookiefile'] = auth_cfg.get('cookies_file')
        if auth_cfg.get('username'):
            opts['username'] = auth_cfg.get('username')
        if auth_cfg.get('password'):
            opts['password'] = auth_cfg.get('password')

        if net_cfg.get('proxy'):
            opts['proxy'] = net_cfg.get('proxy')

        ffmpeg_loc = post_cfg.get('ffmpeg_location')
        if not ffmpeg_loc:
            # Auto-detect bundled ffmpeg next to the backend
            here = os.path.dirname(os.path.abspath(__file__))
            bundled = os.path.join(here, '..', 'ffmpeg', 'bin', 'ffmpeg.exe')
            if os.path.exists(bundled):
                ffmpeg_loc = os.path.abspath(bundled)
        if ffmpeg_loc:
            opts['ffmpeg_location'] = ffmpeg_loc

        return opts

    @staticmethod
    def _fmt_speed(bytes_per_sec: Any) -> str:
        try:
            b = float(bytes_per_sec or 0)
        except (TypeError, ValueError):
            return ''
        if b >= 1024 ** 3:
            return f'{b / 1024 ** 3:.2f} GB/s'
        if b >= 1024 ** 2:
            return f'{b / 1024 ** 2:.2f} MB/s'
        if b >= 1024:
            return f'{b / 1024:.2f} KB/s'
        return f'{b:.0f} B/s'

    @staticmethod
    def _fmt_eta(seconds: Any) -> str:
        try:
            s = int(seconds or 0)
        except (TypeError, ValueError):
            return ''
        if s < 60:
            return f'{s}s'
        m, s = divmod(s, 60)
        if m < 60:
            return f'{m}m {s}s'
        h, m = divmod(m, 60)
        return f'{h}h {m}m {s}s'
