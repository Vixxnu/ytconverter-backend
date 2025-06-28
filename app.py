from flask import Flask, request, jsonify, send_file
from yt_dlp import YoutubeDL
import os
import uuid
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@app.route('/api/formats', methods=['POST'])
def get_formats():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        with YoutubeDL({'quiet': True, 'cookiefile': 'cookies.txt'}) as ydl:
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
        return jsonify({'error': str(e)}), 500


@app.route('/api/download', methods=['POST'])
def download_video():
    try:
        data = request.json
        url = data.get('url')
        format_id = data.get('resolution')
        mode = data.get('mode')

        print(f"URL: {url}")
        print(f"Format ID: {format_id}")
        print(f"Mode: {mode}")

        unique_id = uuid.uuid4().hex[:8]
        filename_template = f"%(title)s_{unique_id}.%(ext)s"
        output_path = os.path.join(DOWNLOAD_DIR, filename_template)

        ydl_opts = {}

        if mode == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_path,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'merge_output_format': 'mp3',
                'cookiefile': 'cookies.txt'
            }

        elif mode == 'best':
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'outtmpl': output_path,
                'merge_output_format': 'mp4',
                'cookiefile': 'cookies.txt'
            }

        elif mode == 'video':
            ydl_opts = {
                'format': f"{format_id}+bestaudio/best",
                'outtmpl': output_path,
                'merge_output_format': 'mp4',
                'cookiefile': 'cookies.txt'
            }
        else:
            return jsonify({'error': 'Invalid mode'}), 400

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_filename = ydl.prepare_filename(info)

        print("Downloaded:", downloaded_filename)
        return send_file(downloaded_filename, as_attachment=True)

    except Exception as e:
        print("Download Error:", str(e))
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
