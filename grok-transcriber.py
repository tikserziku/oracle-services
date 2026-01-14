import os
import sys
import subprocess
import logging
import uuid
import tempfile

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определяем путь к yt-dlp в виртуальном окружении
def get_ytdlp_path():
    """Получить путь к yt-dlp"""
    # Приоритет: standalone бинарник (nightly) > venv > python -m
    
    # 1. Проверяем standalone бинарник (nightly build - самый свежий)
    if os.path.exists('/usr/local/bin/yt-dlp'):
        return '/usr/local/bin/yt-dlp'
    
    # 2. Проверяем в ~/.local/bin
    local_bin = os.path.expanduser('~/.local/bin/yt-dlp')
    if os.path.exists(local_bin):
        return local_bin
    
    # 3. Попробуем найти в виртуальном окружении
    venv_ytdlp = os.path.join(sys.prefix, 'Scripts', 'yt-dlp.exe')
    if os.path.exists(venv_ytdlp):
        return venv_ytdlp
    
    # 4. Используем python -m yt_dlp как fallback
    return [sys.executable, '-m', 'yt_dlp']

def download_video(url, output_path=None):
    """
    Загружает видео по URL с помощью yt-dlp
    
    Args:
        url: URL видео (TikTok, YouTube и др.)
        output_path: Путь для сохранения видео (если None, создается временный)
    
    Returns:
        Путь к загруженному видео
    """
    try:
        # Если путь не указан, создаем временный
        if not output_path:
            temp_dir = tempfile.mkdtemp()
            output_path = os.path.join(temp_dir, f"video_{uuid.uuid4().hex}.mp4")
        
        # Конвертируем YouTube Shorts в обычный формат
        if '/shorts/' in url:
            video_id = url.split('/shorts/')[-1].split('?')[0]
            original_url = url
            url = f"https://www.youtube.com/watch?v={video_id}"
            logger.info(f"YouTube Shorts обнаружен, конвертируем:")
            logger.info(f"  Было: {original_url}")
            logger.info(f"  Стало: {url}")

        logger.info(f"Начинаем загрузку видео из {url}")

        # Команда для загрузки видео
        ytdlp = get_ytdlp_path()
        logger.info(f"Используем yt-dlp: {ytdlp}")

        # Базовые опции
        options = [
            '-f', 'best',
            '-o', output_path,
            '--no-playlist',
            '--no-warnings',
        ]

        # Для YouTube добавляем опции для обхода блокировок
        if 'youtube.com' in url or 'youtu.be' in url:
            # Используем mobile/android client - работает без cookies!
            options.extend([
                '--extractor-args', 'youtube:player_client=android,mweb,web',
            ])
            logger.info("Используем Android/Mobile client для обхода YouTube bot detection")

            # Дополнительно пробуем cookies если они есть (как fallback)
            cookies_path = os.path.join(os.path.dirname(__file__), 'youtube_cookies.txt')
            if os.path.exists(cookies_path):
                try:
                    import shutil
                    temp_cookies = os.path.join(tempfile.gettempdir(), f'yt_cookies_{uuid.uuid4().hex}.txt')
                    shutil.copy2(cookies_path, temp_cookies)
                    options.extend(['--cookies', temp_cookies])
                    logger.info("+ Добавлены cookies из файла youtube_cookies.txt")
                except Exception as e:
                    logger.warning(f"Не удалось загрузить cookies: {e}")

        # Добавляем URL
        options.append(url)

        # Формируем финальную команду
        if isinstance(ytdlp, list):
            cmd = ytdlp + options
        else:
            cmd = [ytdlp] + options
        
        # Выполняем команду
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if os.path.exists(output_path):
            logger.info(f"Видео успешно загружено: {output_path}")
            return output_path
        else:
            logger.error("Файл не создан после загрузки")
            raise FileNotFoundError("Файл не создан после загрузки")
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при загрузке видео: {e.stderr}")
        raise Exception(f"Не удалось загрузить видео: {e.stderr}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при загрузке видео: {str(e)}")
        raise

def extract_audio(video_path, output_path=None):
    """
    Извлекает аудио из видео с помощью ffmpeg
    
    Args:
        video_path: Путь к видеофайлу
        output_path: Путь для сохранения аудио (если None, создается автоматически)
    
    Returns:
        Путь к извлеченному аудиофайлу
    """
    try:
        if not os.path.exists(video_path):
            logger.error(f"Видеофайл не найден: {video_path}")
            raise FileNotFoundError(f"Видеофайл не найден: {video_path}")
        
        # Если путь не указан, создаем на основе пути к видео
        if not output_path:
            output_path = os.path.splitext(video_path)[0] + ".mp3"
        
        logger.info(f"Извлекаем аудио из {video_path}")
        
        # Команда для извлечения аудио
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # Отключаем видео
            '-acodec', 'libmp3lame',  # Кодек MP3
            '-ab', '128k',  # Битрейт
            '-ar', '44100',  # Частота дискретизации
            '-y',  # Перезаписывать существующий файл
            output_path
        ]
        
        # Выполняем команду
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if os.path.exists(output_path):
            logger.info(f"Аудио успешно извлечено: {output_path}")
            return output_path
        else:
            logger.error("Аудиофайл не создан после обработки")
            raise FileNotFoundError("Аудиофайл не создан после обработки")
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при извлечении аудио: {e.stderr}")
        raise Exception(f"Не удалось извлечь аудио: {e.stderr}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при извлечении аудио: {str(e)}")
        raise

# Тестовая функция
def test_download_and_extract():
    url = "https://www.tiktok.com/@visaginas360/video/7504038733700795670"
    try:
        video_path = download_video(url)
        audio_path = extract_audio(video_path)
        return video_path, audio_path
    except Exception as e:
        logger.error(f"Ошибка в тестовой функции: {str(e)}")
        return None, None
