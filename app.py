import ssl
import os
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

from flask import Flask, render_template, request, jsonify, send_file
import re
import yt_dlp
from pathlib import Path
import certifi
import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import unicodedata
import string

app = Flask(__name__)

# İndirilen dosyaların saklanacağı klasör
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# yt-dlp için genel ayarlar
YDL_OPTIONS = {
    'format': 'best',
    'outtmpl': '%(title)s.%(ext)s',
    'nocheckcertificate': True,
    'no_check_certificate': True,
    'no_warnings': True,
    'quiet': True,
    'extract_flat': False,
    'noplaylist': True,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
}

# requests için SSL doğrulamasını devre dışı bırak
requests.packages.urllib3.disable_warnings()
session = requests.Session()
session.verify = False

def sanitize_filename(filename):
    # Türkçe karakterleri İngilizce karakterlere dönüştür
    filename = filename.replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c')
    filename = filename.replace('İ', 'I').replace('Ğ', 'G').replace('Ü', 'U').replace('Ş', 'S').replace('Ö', 'O').replace('Ç', 'C')
    
    # Unicode normalleştirme
    filename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode('ASCII')
    
    # Sadece alfanumerik karakterler, tire ve alt çizgi kullan
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = ''.join(c for c in filename if c in valid_chars)
    
    # Boşlukları tire ile değiştir
    filename = filename.replace(' ', '-')
    
    return filename

def download_with_progress(url, format_type, format_id=None):
    video_id = extract_video_id(url)
    if not video_id:
        raise Exception("Video ID alınamadı")

    output_path = os.path.join(DOWNLOAD_FOLDER, f"{video_id}_{format_type}")
    
    ydl_opts = {
        'format': format_id if format_id else ('bestaudio' if format_type == 'mp3' else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'),
        'outtmpl': output_path + '.%(ext)s',
        'nocheckcertificate': True,
        'no_check_certificate': True,
        'no_warnings': True,
        'quiet': True,
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 10,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }

    if format_type == 'mp3':
        ydl_opts.update({
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
        final_path = output_path + '.mp3'
    else:
        ydl_opts.update({
            'merge_output_format': 'mp4',
            'format_sort': ['res:1080', 'ext:mp4:m4a']
        })
        final_path = output_path + '.mp4'

    if os.path.exists(final_path):
        os.remove(final_path)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if os.path.exists(final_path):
            return final_path
        else:
            files = os.listdir(DOWNLOAD_FOLDER)
            possible_files = [f for f in files if video_id in f]
            if possible_files:
                return os.path.join(DOWNLOAD_FOLDER, possible_files[0])
            raise Exception("Dosya bulunamadı")
    except Exception as e:
        print(f"İndirme hatası: {str(e)}")
        raise

def extract_video_id(url):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/|v\/|youtu.be\/)([0-9A-Za-z_-]{11})',
        r'(?:watch\?v=)([0-9A-Za-z_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def is_valid_youtube_url(url):
    video_id = extract_video_id(url)
    return video_id is not None

def get_video_details(url):
    try:
        video_id = extract_video_id(url)
        if not video_id:
            raise Exception("Geçerli video ID'si bulunamadı")

        api_url = f"https://www.youtube.com/oembed?url=http://www.youtube.com/watch?v={video_id}&format=json"
        response = session.get(api_url)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'title': data.get('title', 'Bilinmeyen Başlık'),
                'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                'author': data.get('author_name', 'Bilinmeyen'),
                'duration': 0
            }
        else:
            return {
                'title': f"Video {video_id}",
                'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                'duration': 0,
                'author': 'Bilinmeyen'
            }

    except Exception as e:
        print(f"Video bilgileri alınırken hata: {str(e)}")
        return {
            'title': f"Video {video_id}",
            'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            'duration': 0,
            'author': 'Bilinmeyen'
        }

def get_video_formats(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'no_check_certificate': True,
            'socket_timeout': 30,
            'retries': 10,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                formats = []
                seen_qualities = set()
                
                # Ses formatlarını ekle
                audio_formats = []
                for f in info['formats']:
                    if f.get('vcodec') == 'none' and f.get('acodec') != 'none' and f.get('abr'):
                        format_info = {
                            'format_id': f.get('format_id', ''),
                            'ext': 'mp3',
                            'resolution': 'N/A',
                            'filesize': f.get('filesize', 0),
                            'vcodec': 'none',
                            'acodec': f.get('acodec', ''),
                            'format_note': 'Ses',
                            'abr': int(f.get('abr', 0)),
                            'display_name': f"Ses - MP3 {int(f.get('abr', 0))}kbps"
                        }
                        audio_formats.append(format_info)
                
                # Ses formatlarını bit rate'e göre sırala
                audio_formats.sort(key=lambda x: x['abr'], reverse=True)
                formats.extend(audio_formats)

                # Video formatlarını ekle
                for f in info['formats']:
                    if f.get('vcodec') != 'none' and f.get('height'):
                        height = f.get('height', 0)
                        if height not in seen_qualities:
                            seen_qualities.add(height)
                            format_info = {
                                'format_id': f"{f.get('format_id', '')}+bestaudio",
                                'ext': 'mp4',
                                'height': height,
                                'resolution': f"{f.get('width', '')}x{height}",
                                'filesize': f.get('filesize', 0),
                                'vcodec': f.get('vcodec', ''),
                                'acodec': 'mp4a.40.2',
                                'format_note': f.get('format_note', ''),
                                'display_name': f"Video - {height}p MP4"
                            }
                            formats.append(format_info)

                # Video formatlarını çözünürlüğe göre sırala
                formats.sort(key=lambda x: (
                    0 if x.get('ext') == 'mp3' else 1,  # Ses formatları önce
                    -int(x.get('height', 0)) if x.get('height') else 0  # Sonra video çözünürlüğüne göre
                ))

                return formats

            except Exception as e:
                print(f"Format bilgileri alınırken hata: {str(e)}")
                return [
                    {
                        'format_id': 'ba/b',
                        'ext': 'mp3',
                        'resolution': 'N/A',
                        'filesize': 0,
                        'vcodec': 'none',
                        'acodec': 'mp3',
                        'format_note': 'Ses',
                        'display_name': 'Ses - MP3 128kbps'
                    },
                    {
                        'format_id': 'bv*[height=1080]+ba/b',
                        'ext': 'mp4',
                        'height': 1080,
                        'resolution': '1920x1080',
                        'filesize': 0,
                        'vcodec': 'h264',
                        'acodec': 'mp4a.40.2',
                        'format_note': 'Video',
                        'display_name': 'Video - 1080p MP4'
                    },
                    {
                        'format_id': 'bv*[height=720]+ba/b',
                        'ext': 'mp4',
                        'height': 720,
                        'resolution': '1280x720',
                        'filesize': 0,
                        'vcodec': 'h264',
                        'acodec': 'mp4a.40.2',
                        'format_note': 'Video',
                        'display_name': 'Video - 720p MP4'
                    },
                    {
                        'format_id': 'bv*[height=480]+ba/b',
                        'ext': 'mp4',
                        'height': 480,
                        'resolution': '854x480',
                        'filesize': 0,
                        'vcodec': 'h264',
                        'acodec': 'mp4a.40.2',
                        'format_note': 'Video',
                        'display_name': 'Video - 480p MP4'
                    },
                    {
                        'format_id': 'bv*[height=360]+ba/b',
                        'ext': 'mp4',
                        'height': 360,
                        'resolution': '640x360',
                        'filesize': 0,
                        'vcodec': 'h264',
                        'acodec': 'mp4a.40.2',
                        'format_note': 'Video',
                        'display_name': 'Video - 360p MP4'
                    }
                ]

    except Exception as e:
        print(f"Format bilgileri alınırken hata: {str(e)}")
        return []

def is_youtube_url(url):
    youtube_regex = (
        r'(https?://)?(www\.)?' 
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )
    return bool(re.match(youtube_regex, url))

def is_instagram_url(url):
    instagram_regex = (
        r'(https?://)?(www\.)?' 
        r'instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)'
    )
    return bool(re.match(instagram_regex, url))

def extract_instagram_id(url):
    instagram_regex = (
        r'(https?://)?(www\.)?' 
        r'instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)'
    )
    match = re.search(instagram_regex, url)
    return match.group(3) if match else None

def get_instagram_info(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'nocheckcertificate': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            return {
                'title': info.get('title', 'Instagram Video'),
                'thumbnail_url': info.get('thumbnail', ''),
                'author': info.get('uploader', 'Instagram User'),
                'duration': info.get('duration', 0)
            }
    except Exception as e:
        print(f"Instagram bilgileri alınırken hata: {str(e)}")
        post_id = extract_instagram_id(url)
        return {
            'title': f'Instagram Post {post_id}',
            'thumbnail_url': '',
            'author': 'Instagram User',
            'duration': 0
        }

def get_instagram_formats(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            
            if info.get('formats'):
                # Video formatları
                video_formats = [f for f in info['formats'] if f.get('vcodec') != 'none']
                for f in video_formats:
                    format_info = {
                        'format_id': f.get('format_id', ''),
                        'ext': 'mp4',
                        'height': f.get('height', 0),
                        'filesize': f.get('filesize', 0),
                        'vcodec': f.get('vcodec', ''),
                        'acodec': f.get('acodec', ''),
                        'format_note': 'Video',
                        'display_name': f"Video - {f.get('height', 0)}p MP4"
                    }
                    formats.append(format_info)
                
                # Ses formatı (eğer varsa)
                audio_formats = [f for f in info['formats'] if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
                if audio_formats:
                    format_info = {
                        'format_id': audio_formats[0].get('format_id', ''),
                        'ext': 'mp3',
                        'filesize': audio_formats[0].get('filesize', 0),
                        'vcodec': 'none',
                        'acodec': audio_formats[0].get('acodec', ''),
                        'format_note': 'Ses',
                        'display_name': 'Ses - MP3'
                    }
                    formats.append(format_info)
            
            return formats
    except Exception as e:
        print(f"Instagram format bilgileri alınırken hata: {str(e)}")
        return [
            {
                'format_id': 'best',
                'ext': 'mp4',
                'height': 720,
                'filesize': 0,
                'vcodec': 'h264',
                'acodec': 'aac',
                'format_note': 'Video',
                'display_name': 'Video - En İyi Kalite'
            }
        ]

def is_twitter_url(url):
    twitter_regex = (
        r'(https?://)?(www\.)?' 
        r'(twitter|x)\.com/[A-Za-z0-9_]+/status/([0-9]+)'
    )
    return bool(re.match(twitter_regex, url))

def extract_twitter_id(url):
    twitter_regex = (
        r'(https?://)?(www\.)?' 
        r'(twitter|x)\.com/[A-Za-z0-9_]+/status/([0-9]+)'
    )
    match = re.search(twitter_regex, url)
    return match.group(4) if match else None

def get_twitter_info(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'nocheckcertificate': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            return {
                'title': info.get('title', 'Twitter Video'),
                'thumbnail_url': info.get('thumbnail', ''),
                'author': info.get('uploader', 'Twitter User'),
                'duration': info.get('duration', 0)
            }
    except Exception as e:
        print(f"Twitter bilgileri alınırken hata: {str(e)}")
        tweet_id = extract_twitter_id(url)
        return {
            'title': f'Tweet {tweet_id}',
            'thumbnail_url': '',
            'author': 'Twitter User',
            'duration': 0
        }

def get_twitter_formats(url):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            
            if info.get('formats'):
                # Video formatları
                video_formats = [f for f in info['formats'] if f.get('vcodec') != 'none']
                for f in video_formats:
                    format_info = {
                        'format_id': f.get('format_id', ''),
                        'ext': 'mp4',
                        'height': f.get('height', 0),
                        'filesize': f.get('filesize', 0),
                        'vcodec': f.get('vcodec', ''),
                        'acodec': f.get('acodec', ''),
                        'format_note': 'Video',
                        'display_name': f"Video - {f.get('height', 0)}p MP4"
                    }
                    formats.append(format_info)
                
                # Ses formatı (eğer varsa)
                audio_formats = [f for f in info['formats'] if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
                if audio_formats:
                    format_info = {
                        'format_id': audio_formats[0].get('format_id', ''),
                        'ext': 'mp3',
                        'filesize': audio_formats[0].get('filesize', 0),
                        'vcodec': 'none',
                        'acodec': audio_formats[0].get('acodec', ''),
                        'format_note': 'Ses',
                        'display_name': 'Ses - MP3'
                    }
                    formats.append(format_info)
            
            return formats
    except Exception as e:
        print(f"Twitter format bilgileri alınırken hata: {str(e)}")
        return [
            {
                'format_id': 'best',
                'ext': 'mp4',
                'height': 720,
                'filesize': 0,
                'vcodec': 'h264',
                'acodec': 'aac',
                'format_note': 'Video',
                'display_name': 'Video - En İyi Kalite'
            }
        ]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/video-info', methods=['POST'])
def get_video_info():
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL gerekli'}), 400
        
        if is_youtube_url(url):
            if not extract_video_id(url):
                return jsonify({'error': 'Geçersiz YouTube URL\'si'}), 400
            video_info = get_video_details(url)
        elif is_instagram_url(url):
            if not extract_instagram_id(url):
                return jsonify({'error': 'Geçersiz Instagram URL\'si'}), 400
            video_info = get_instagram_info(url)
        elif is_twitter_url(url):
            if not extract_twitter_id(url):
                return jsonify({'error': 'Geçersiz Twitter URL\'si'}), 400
            video_info = get_twitter_info(url)
        else:
            return jsonify({'error': 'Desteklenmeyen URL formatı'}), 400

        return jsonify(video_info)
        
    except Exception as e:
        print(f"API hatası: {str(e)}")
        return jsonify({'error': f"Video bilgileri alınamadı: {str(e)}"}), 500

@app.route('/api/formats', methods=['POST'])
def get_formats():
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL gerekli'}), 400
        
        if is_youtube_url(url):
            if not extract_video_id(url):
                return jsonify({'error': 'Geçersiz YouTube URL\'si'}), 400
            formats = get_video_formats(url)
        elif is_instagram_url(url):
            if not extract_instagram_id(url):
                return jsonify({'error': 'Geçersiz Instagram URL\'si'}), 400
            formats = get_instagram_formats(url)
        elif is_twitter_url(url):
            if not extract_twitter_id(url):
                return jsonify({'error': 'Geçersiz Twitter URL\'si'}), 400
            formats = get_twitter_formats(url)
        else:
            return jsonify({'error': 'Desteklenmeyen URL formatı'}), 400

        return jsonify({'formats': formats})
        
    except Exception as e:
        print(f"Format bilgileri alınamadı: {str(e)}")
        return jsonify({'error': f"Format bilgileri alınamadı: {str(e)}"}), 500

@app.route('/api/download')
def download_video():
    try:
        url = request.args.get('url')
        format_type = request.args.get('format')
        format_id = request.args.get('format_id')
        
        if not url or not format_type:
            return jsonify({'error': 'URL ve format gerekli'}), 400

        # URL'nin geçerliliğini kontrol et
        if is_youtube_url(url):
            video_id = extract_video_id(url)
            if not video_id:
                return jsonify({'error': 'Geçersiz YouTube URL\'si'}), 400
        elif is_instagram_url(url):
            video_id = extract_instagram_id(url)
            if not video_id:
                return jsonify({'error': 'Geçersiz Instagram URL\'si'}), 400
        elif is_twitter_url(url):
            video_id = extract_twitter_id(url)
            if not video_id:
                return jsonify({'error': 'Geçersiz Twitter URL\'si'}), 400
        else:
            return jsonify({'error': 'Desteklenmeyen URL formatı'}), 400

        # Video bilgilerini al
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = sanitize_filename(info.get('title', video_id))

        # İndirme seçeneklerini ayarla
        output_path = os.path.join(DOWNLOAD_FOLDER, f"{title}_{format_type}")
        
        ydl_opts = {
            'format': format_id if format_id else ('bestaudio' if format_type == 'mp3' else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'),
            'outtmpl': output_path + '.%(ext)s',
            'nocheckcertificate': True,
            'no_check_certificate': True,
            'no_warnings': True,
            'quiet': True,
            'noplaylist': True,
            'socket_timeout': 10,
            'retries': 3,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        }

        if format_type == 'mp3':
            ydl_opts.update({
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
            final_path = output_path + '.mp3'
            content_type = 'audio/mpeg'
            download_ext = '.mp3'
        else:
            ydl_opts.update({
                'merge_output_format': 'mp4',
            })
            final_path = output_path + '.mp4'
            content_type = 'video/mp4'
            download_ext = '.mp4'

        # Eğer dosya zaten varsa sil
        if os.path.exists(final_path):
            os.remove(final_path)

        # Dosyayı indir
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # İndirilen dosyayı kontrol et
        if os.path.exists(final_path):
            safe_filename = f"{title}{download_ext}"
            response = send_file(
                final_path,
                as_attachment=True,
                download_name=safe_filename,
                mimetype=content_type
            )
            response.headers['Content-Type'] = content_type
            response.headers['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
            return response
        else:
            return jsonify({'error': 'Dosya indirilemedi'}), 500

    except Exception as e:
        print(f"İndirme hatası: {str(e)}")
        return jsonify({'error': f"İndirme başarısız: {str(e)}"}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_file(
            os.path.join(DOWNLOAD_FOLDER, filename),
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)