import yt_dlp
import os
import asyncio
from config import Config

class VideoDownloader:
    def __init__(self):
        self.temp_dir = Config.TEMP_DIR
        os.makedirs(self.temp_dir, exist_ok=True)

    def get_platform(self, url):
        url_lower = url.lower()
        for platform in Config.SUPPORTED_PLATFORMS:
            if platform in url_lower:
                return platform.split('.')[0]
        return 'unknown'

    def get_ydl_opts(self, quality='best', audio_only=False):
        opts = {
            'outtmpl': os.path.join(self.temp_dir, '%(id)s_%(format_id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }

        if audio_only:
            opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            })
        else:
            if quality == 'best':
                opts['format'] = 'best[filesize<<50M]/bestvideo[filesize<<50M]+bestaudio/best'
            elif quality == '1080':
                opts['format'] = 'best[height<=1080][filesize<<50M]/bestvideo[height<=1080][filesize<<50M]+bestaudio/best'
            elif quality == '720':
                opts['format'] = 'best[height<=720][filesize<<50M]/best'
            else:
                opts['format'] = 'best[filesize<<50M]/best'

            opts['merge_output_format'] = 'mp4'

        return opts

    async def download(self, url, quality='best', audio_only=False, progress_hook=None):
        loop = asyncio.get_event_loop()

        def _download():
            opts = self.get_ydl_opts(quality, audio_only)

            if progress_hook:
                opts['progress_hooks'] = [progress_hook]

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                if audio_only and not filename.endswith('.mp3'):
                    filename = filename.rsplit('.', 1)[0] + '.mp3'

                if not os.path.exists(filename):
                    base = filename.rsplit('.', 1)[0]
                    for ext in ['.mp4', '.mkv', '.webm', '.mp3']:
                        if os.path.exists(base + ext):
                            filename = base + ext
                            break

                return {
                    'filename': filename,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'thumbnail': info.get('thumbnail'),
                    'filesize': os.path.getsize(filename) if os.path.exists(filename) else 0,
                    'width': info.get('width', 0),
                    'height': info.get('height', 0),
                }

        return await loop.run_in_executor(None, _download)

    async def get_info(self, url):
        loop = asyncio.get_event_loop()

        def _get_info():
            opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title'),
                    'duration': info.get('duration'),
                    'uploader': info.get('uploader'),
                    'thumbnail': info.get('thumbnail'),
                    'description': info.get('description', '')[:200],
                }

        return await loop.run_in_executor(None, _get_info)

    def cleanup(self, filename):
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except Exception as e:
            print(f"Cleanup error: {e}")
