from flask import Flask, request, jsonify, send_file
from yt_dlp import YoutubeDL
import os
import uuid
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

DEFAULT_YDL_ARGS = {
    'quiet': True,
    'cookiefile': 'cookies.txt',
    'extractor_args': {
        'youtube': [
            'client=mweb',  # Use mobile web client
            # Optional: add visitor_data if needed
            # 'player_skip=webpage,configs',
        ]
    },
    'sleep_interval_requests': 5,
    'ratelimit': 1_000_000,  # in bytes/sec (optional)
}


@app.route('/api/formats', methods=['POST'])
def get_formats():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        with YoutubeDL(DEFAULT_YDL_ARGS) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])

        resolutions = {}
        for f in formats:
            if f.get("vcodec") != "none" and f.get("height") is not None:
                label = f"{f['height']}p"
                if label not in resolutions:
                    resolutions[label] = f["format_id"]

        audio_available = any(f.get('vcodec') == 'none' for f in formats)

        return jsonify({
            'resolutions': [{"label": k, "value": v} for k, v in sorted(resolutions.items(), key=lambda x: int(x[0].replace('p', '')))],
            'audio': audio_available,
            'title': info.get('title'),
            'id': info.get('id')
        })

    except Exception as e:
        return jsonify({'error': f"Failed to fetch formats: {str(e)}"}), 500


@app.route('/api/download', methods=['POST'])
def download_video():
    try:
        data = request.json
        url = data.get('url')
        format_id = data.get('resolution')
        mode = data.get('mode')

        unique_id = uuid.uuid4().hex[:8]
        filename_template = f"%(title)s_{unique_id}.%(ext)s"
        output_path = os.path.join(DOWNLOAD_DIR, filename_template)

        ydl_opts = DEFAULT_YDL_ARGS.copy()
        ydl_opts['outtmpl'] = output_path

        if mode == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'merge_output_format': 'mp3'
            })

        elif mode == 'best':
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
            ydl_opts['merge_output_format'] = 'mp4'

        elif mode == 'video':
            ydl_opts['format'] = f"{format_id}+bestaudio/best"
            ydl_opts['merge_output_format'] = 'mp4'

        else:
            return jsonify({'error': 'Invalid mode'}), 400

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_filename = ydl.prepare_filename(info)

        return send_file(downloaded_filename, as_attachment=True)

    except Exception as e:
        return jsonify({'error': f"Download failed: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
