"""
在线音乐API客户端

支持多个音源:
- kw: 酷我音乐
- kg: 酷狗音乐
- tx: QQ音乐
- wy: 网易云音乐
- mg: 咪咕音乐

支持两种API模式:
1. 导入的音源脚本 (如新澜音源)
2. 网易云API (用户提供的接口)
"""

import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import threading
import re


# API配置
DEFAULT_API_URL = "https://source.shiqianjiang.cn"
DEFAULT_API_KEY = "CERU_KEY-47FFA828BA6FF9FF50CF83E87EC97056"

# 网易云API备选地址
NETEASE_API_FALLBACKS = [
    "https://netease-cloud-music-api-five-roan-88.vercel.app",
]

# 支持的音源和音质
MUSIC_QUALITY = {
    'kw': ['128k', '320k', 'flac', 'flac24bit', 'hires'],
    'mg': ['128k', '320k', 'flac', 'flac24bit', 'hires'],
    'kg': ['128k', '320k', 'flac', 'flac24bit', 'hires', 'atmos', 'master'],
    'tx': ['128k', '320k', 'flac', 'flac24bit', 'hires', 'atmos', 'atmos_plus', 'master'],
    'wy': ['128k', '320k', 'flac', 'flac24bit', 'hires', 'atmos', 'master']
}

MUSIC_SOURCES = list(MUSIC_QUALITY.keys())

# 音源名称映射
SOURCE_NAMES = {
    'kw': '酷我音乐',
    'kg': '酷狗音乐',
    'tx': 'QQ音乐',
    'wy': '网易云音乐',
    'mg': '咪咕音乐'
}

SOURCE_CODES = {v: k for k, v in SOURCE_NAMES.items()}


@dataclass
class OnlineSong:
    """在线歌曲信息"""
    song_id: str
    name: str
    artist: str
    album: str = ""
    duration: float = 0.0
    source: str = ""
    pic_url: str = ""
    quality: str = "320k"
    hash: str = ""
    songmid: str = ""
    copyright_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'song_id': self.song_id,
            'name': self.name,
            'artist': self.artist,
            'album': self.album,
            'duration': self.duration,
            'source': self.source,
            'pic_url': self.pic_url,
            'quality': self.quality
        }
    
    def get_platform_id(self) -> str:
        if self.hash:
            return self.hash
        if self.songmid:
            return self.songmid
        if self.copyright_id:
            return self.copyright_id
        return self.song_id


class OnlineMusicClient:
    """在线音乐API客户端"""
    
    def __init__(self, api_url: str = DEFAULT_API_URL, api_key: str = DEFAULT_API_KEY):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.timeout = 15
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._lock = threading.Lock()
        self.netease_api_url = None
        self._init_netease_api()
        
    def _init_netease_api(self):
        for url in NETEASE_API_FALLBACKS:
            try:
                test_url = f"{url}/search?keywords=test&limit=1"
                req = urllib.request.Request(test_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                with urllib.request.urlopen(req, timeout=5) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    if result.get('code') == 200:
                        self.netease_api_url = url
                        print(f"[在线音乐] 网易云API可用: {url}")
                        break
            except Exception:
                continue
        
    def set_api_url(self, url: str):
        if url:
            self.api_url = url.rstrip('/')
        
    def set_api_key(self, key: str):
        if key:
            self.api_key = key
        
    def _request(self, url: str, method: str = 'GET', 
                 data: Optional[Dict] = None, use_auth: bool = True) -> Optional[Dict]:
        try:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            if use_auth and self.api_key:
                headers['X-API-Key'] = self.api_key
                
            if method == 'GET':
                req = urllib.request.Request(url, headers=headers)
            else:
                body = json.dumps(data).encode('utf-8') if data else None
                req = urllib.request.Request(url, data=body, method=method, headers=headers)
                
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            print(f"HTTP错误 {e.code}: {e.reason}")
            return None
        except urllib.error.URLError as e:
            print(f"URL错误: {e.reason}")
            return None
        except json.JSONDecodeError:
            print("JSON解析失败")
            return None
        except Exception as e:
            print(f"请求错误: {e}")
            return None
            
    def check_connection(self) -> tuple:
        try:
            url = f"{self.api_url}/music/search?source=kw&keyword=test&page=1&limit=1"
            result = self._request(url)
            if result and result.get('code') == 200:
                return True, "音源API连接成功"
        except Exception:
            pass
            
        if self.netease_api_url:
            return True, "网易云API连接成功"
            
        return False, "无法连接到任何API服务器"
    
    def check_connection_simple(self) -> bool:
        success, _ = self.check_connection()
        return success
            
    def search(self, keyword: str, source: str = 'kw', 
               page: int = 1, limit: int = 30) -> List[OnlineSong]:
        songs = []
        
        songs = self._search_source_api(keyword, source, page, limit)
        if songs:
            return songs
            
        if source == 'wy' and self.netease_api_url:
            songs = self._search_netease_api(keyword, limit, (page - 1) * limit)
            
        return songs
        
    def _search_source_api(self, keyword: str, source: str, 
                           page: int, limit: int) -> List[OnlineSong]:
        url = f"{self.api_url}/music/search?source={source}&keyword={urllib.parse.quote(keyword)}&page={page}&limit={limit}"
        
        result = self._request(url)
        if not result or result.get('code') != 200:
            return []
            
        songs = []
        song_list = result.get('data', result.get('list', []))
        
        if isinstance(song_list, list):
            for item in song_list:
                try:
                    song = self._parse_source_song(item, source)
                    if song:
                        songs.append(song)
                except Exception as e:
                    print(f"解析歌曲失败: {e}")
                    continue
                    
        return songs
        
    def _parse_source_song(self, item: dict, source: str) -> Optional[OnlineSong]:
        song_id = str(item.get('id', item.get('songId', '')))
        hash_id = str(item.get('hash', ''))
        songmid = str(item.get('songmid', item.get('mid', '')))
        copyright_id = str(item.get('copyrightId', ''))
        
        final_id = hash_id or songmid or copyright_id or song_id
        if not final_id:
            return None
        
        artist = item.get('artist', item.get('singer', ''))
        if isinstance(artist, list):
            artist = ', '.join([a.get('name', str(a)) if isinstance(a, dict) else str(a) for a in artist])
        elif isinstance(artist, dict):
            artist = artist.get('name', '')
        
        return OnlineSong(
            song_id=final_id,
            name=item.get('name', item.get('songname', item.get('title', ''))),
            artist=artist,
            album=item.get('album', item.get('albumName', '')),
            duration=float(item.get('duration', item.get('interval', 0))),
            source=source,
            pic_url=item.get('pic', item.get('img', item.get('cover', ''))),
            hash=hash_id,
            songmid=songmid,
            copyright_id=copyright_id
        )
        
    def _search_netease_api(self, keyword: str, limit: int = 30, 
                            offset: int = 0) -> List[OnlineSong]:
        if not self.netease_api_url:
            return []
            
        url = f"{self.netease_api_url}/search?keywords={urllib.parse.quote(keyword)}&limit={limit}&offset={offset}&type=1"
        
        result = self._request(url, use_auth=False)
        if not result or result.get('code') != 200:
            url = f"{self.netease_api_url}/cloudsearch?keywords={urllib.parse.quote(keyword)}&limit={limit}&offset={offset}&type=1"
            result = self._request(url, use_auth=False)
            
        if not result or result.get('code') != 200:
            return []
            
        songs = []
        song_list = result.get('result', {}).get('songs', [])
        
        for item in song_list:
            try:
                song = self._parse_netease_song(item)
                if song:
                    songs.append(song)
            except Exception as e:
                print(f"解析网易云歌曲失败: {e}")
                continue
                
        return songs
        
    def _parse_netease_song(self, item: dict) -> Optional[OnlineSong]:
        song_id = str(item.get('id', ''))
        if not song_id:
            return None
            
        artists = item.get('artists', item.get('ar', []))
        artist_names = ', '.join([a.get('name', '') for a in artists if a.get('name')])
        
        album = item.get('album', item.get('al', {}))
        album_name = album.get('name', '') if isinstance(album, dict) else ''
        pic_url = album.get('picUrl', '') if isinstance(album, dict) else ''
        
        duration = float(item.get('duration', 0)) / 1000
        
        return OnlineSong(
            song_id=song_id,
            name=item.get('name', ''),
            artist=artist_names,
            album=album_name,
            duration=duration,
            source='wy',
            pic_url=pic_url,
        )
        
    def get_music_url(self, song: OnlineSong, quality: str = '320k') -> Optional[str]:
        song_id = song.get_platform_id()
        if not song_id:
            return None
        
        url = self._get_url_source_api(song, quality)
        if url:
            return url
            
        if song.source == 'wy' and self.netease_api_url:
            url = self._get_url_netease_api(song_id, quality)
            if url:
                return url
                
        return None
        
    def _get_url_source_api(self, song: OnlineSong, quality: str) -> Optional[str]:
        song_id = song.get_platform_id()
        url = f"{self.api_url}/music/url?source={song.source}&songId={song_id}&quality={quality}"
        
        result = self._request(url)
        if not result:
            return None
            
        if result.get('code') == 200:
            music_url = result.get('url') or (result.get('data', {}).get('url') if isinstance(result.get('data'), dict) else result.get('data'))
            if music_url:
                return music_url
                
        return None
        
    def _get_url_netease_api(self, song_id: str, quality: str) -> Optional[str]:
        if not self.netease_api_url:
            return None
            
        level_map = {
            '128k': 'standard',
            '320k': 'exhigh', 
            'flac': 'lossless',
            'hires': 'hires'
        }
        level = level_map.get(quality, 'exhigh')
        
        url = f"{self.netease_api_url}/song/url/v1?id={song_id}&level={level}"
        result = self._request(url, use_auth=False)
        
        if not result or result.get('code') != 200:
            return None
            
        data = result.get('data', [])
        if data and len(data) > 0:
            return data[0].get('url')
            
        return None
        
    def get_lyric(self, song: OnlineSong) -> Optional[str]:
        song_id = song.get_platform_id()
        if not song_id:
            return None
        
        lyric = self._get_lyric_source_api(song)
        if lyric:
            return lyric
            
        if song.source == 'wy' and self.netease_api_url:
            lyric = self._get_lyric_netease_api(song_id)
            if lyric:
                return lyric
                
        return None
        
    def _get_lyric_source_api(self, song: OnlineSong) -> Optional[str]:
        song_id = song.get_platform_id()
        url = f"{self.api_url}/music/lyric?source={song.source}&songId={song_id}"
        
        result = self._request(url)
        if not result or result.get('code') != 200:
            return None
            
        data = result.get('data', {})
        if isinstance(data, str):
            return data
            
        lyric = data.get('lyric', data.get('lrc', ''))
        tlyric = data.get('tlyric', data.get('tlrc', ''))
        
        if tlyric and lyric:
            return self._merge_lyrics(lyric, tlyric)
        return lyric
        
    def _get_lyric_netease_api(self, song_id: str) -> Optional[str]:
        if not self.netease_api_url:
            return None
            
        url = f"{self.netease_api_url}/lyric?id={song_id}"
        result = self._request(url, use_auth=False)
        
        if not result or result.get('code') != 200:
            return None
            
        lrc = result.get('lrc', {}).get('lyric', '')
        tlyric = result.get('tlyric', {}).get('lyric', '')
        
        if tlyric and lrc:
            return self._merge_lyrics(lrc, tlyric)
        return lrc
        
    def get_pic(self, song: OnlineSong) -> Optional[bytes]:
        pic_url = song.pic_url
        
        if not pic_url:
            song_id = song.get_platform_id()
            if song_id:
                url = f"{self.api_url}/music/pic?source={song.source}&songId={song_id}"
                result = self._request(url)
                if result and result.get('code') == 200:
                    pic_url = result.get('url') or result.get('data')
                
        if pic_url:
            try:
                req = urllib.request.Request(pic_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    return response.read()
            except Exception as e:
                print(f"获取封面失败: {e}")
                
        return None
        
    def _merge_lyrics(self, lyric: str, tlyric: str) -> str:
        def parse_lrc(text):
            lines = {}
            pattern = r'\[(\d+:\d+(?:\.\d+)?)\](.+)?'
            for line in text.split('\n'):
                match = re.match(pattern, line.strip())
                if match:
                    time_str = match.group(1)
                    content = match.group(2) or ''
                    lines[time_str] = content.strip()
            return lines
            
        orig_lines = parse_lrc(lyric)
        trans_lines = parse_lrc(tlyric)
        
        result_lines = []
        for time_str in sorted(orig_lines.keys()):
            result_lines.append(f"[{time_str}]{orig_lines[time_str]}")
            if time_str in trans_lines and trans_lines[time_str]:
                result_lines.append(f"[{time_str}]{trans_lines[time_str]}")
                
        return '\n'.join(result_lines)
    
    def get_hot_songs(self, source: str = 'kw', limit: int = 20) -> List[OnlineSong]:
        return self.search("热门", source, 1, limit)
    
    def get_available_qualities(self, source: str) -> List[str]:
        return MUSIC_QUALITY.get(source, ['128k', '320k'])
    
    def get_comment(self, song: OnlineSong, page: int = 1, limit: int = 20) -> Optional[Dict]:
        if song.source != 'wy' or not self.netease_api_url:
            return None
            
        song_id = song.get_platform_id()
        offset = (page - 1) * limit
        
        url = f"{self.netease_api_url}/comment/music?id={song_id}&limit={limit}&offset={offset}"
        result = self._request(url, use_auth=False)
        
        if not result or result.get('code') != 200:
            return None
            
        return {
            'total': result.get('total', 0),
            'comments': result.get('comments', []),
            'hotComments': result.get('hotComments', [])
        }


# 兼容旧API - 别名
LXMusicClient = OnlineMusicClient


class LXMusicLocalClient:
    """落雪音乐本地客户端"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 23330):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.timeout = 5
        
    def _request(self, endpoint: str) -> Optional[Dict]:
        url = f"{self.base_url}{endpoint}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception:
            return None
            
    def get_status(self) -> Optional[Dict]:
        return self._request('/status')
        
    def get_lyric(self) -> Optional[str]:
        try:
            with urllib.request.urlopen(f"{self.base_url}/lyric", timeout=self.timeout) as response:
                return response.read().decode('utf-8')
        except Exception:
            return None
            
    def play(self):
        self._request('/play')
        
    def pause(self):
        self._request('/pause')
        
    def skip_next(self):
        self._request('/skip-next')
        
    def skip_prev(self):
        self._request('/skip-prev')


# 便捷函数
_default_client: Optional[OnlineMusicClient] = None

def get_client() -> OnlineMusicClient:
    global _default_client
    if _default_client is None:
        _default_client = OnlineMusicClient()
    return _default_client
    
def configure(api_url: str = None, api_key: str = None):
    client = get_client()
    if api_url:
        client.set_api_url(api_url)
    if api_key:
        client.set_api_key(api_key)
    
def search(keyword: str, source: str = 'kw') -> List[OnlineSong]:
    return get_client().search(keyword, source)
    
def get_url(song: OnlineSong, quality: str = '320k') -> Optional[str]:
    return get_client().get_music_url(song, quality)


class NeteaseCloudMusicAPI:
    """网易云音乐公共API客户端"""
    
    PUBLIC_APIS = NETEASE_API_FALLBACKS
    
    def __init__(self, api_url: str = None):
        self.api_url = api_url or (self.PUBLIC_APIS[0] if self.PUBLIC_APIS else None)
        self.timeout = 15
        
    def _request(self, endpoint: str, params: dict = None) -> Optional[Dict]:
        try:
            url = f"{self.api_url}{endpoint}"
            if params:
                url += "?" + urllib.parse.urlencode(params)
                
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://music.163.com/',
            }
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"网易云API请求错误: {e}")
            return None
            
    def search(self, keyword: str, limit: int = 30, offset: int = 0) -> List[OnlineSong]:
        result = self._request('/search', {
            'keywords': keyword,
            'limit': limit,
            'offset': offset,
            'type': 1
        })
        
        if not result:
            result = self._request('/cloudsearch', {
                'keywords': keyword,
                'limit': limit,
                'offset': offset,
                'type': 1
            })
            
        if not result or result.get('code') != 200:
            return []
            
        songs = []
        song_list = result.get('result', {}).get('songs', [])
        
        for item in song_list:
            try:
                artists = item.get('artists', item.get('ar', []))
                artist_names = ', '.join([a.get('name', '') for a in artists if a.get('name')])
                
                album = item.get('album', item.get('al', {}))
                album_name = album.get('name', '') if isinstance(album, dict) else ''
                pic_url = album.get('picUrl', '') if isinstance(album, dict) else ''
                
                song = OnlineSong(
                    song_id=str(item.get('id', '')),
                    name=item.get('name', ''),
                    artist=artist_names,
                    album=album_name,
                    duration=float(item.get('duration', 0)) / 1000,
                    source='wy',
                    pic_url=pic_url,
                )
                songs.append(song)
            except Exception as e:
                print(f"解析网易云歌曲失败: {e}")
                continue
                
        return songs
        
    def check_connection(self) -> tuple:
        try:
            result = self._request('/search', {'keywords': 'test', 'limit': 1})
            if result and result.get('code') == 200:
                return True, "网易云API连接成功"
            return False, "API返回异常"
        except Exception as e:
            return False, f"连接失败: {str(e)}"


class MultiSourceMusicClient:
    """多源音乐客户端"""
    
    def __init__(self, 
                 lx_api_url: str = DEFAULT_API_URL,
                 lx_api_key: str = DEFAULT_API_KEY,
                 netease_api_url: str = None):
        self.lx_client = OnlineMusicClient(lx_api_url, lx_api_key)
        self.netease_client = NeteaseCloudMusicAPI(netease_api_url) if netease_api_url else None
        
    def search(self, keyword: str, source: str = 'kw', 
               use_netease_search: bool = False) -> List[OnlineSong]:
        if use_netease_search and self.netease_client:
            songs = self.netease_client.search(keyword)
            for song in songs:
                song.source = source
            return songs
        else:
            return self.lx_client.search(keyword, source)
            
    def get_music_url(self, song: OnlineSong, quality: str = '320k') -> Optional[str]:
        return self.lx_client.get_music_url(song, quality)
        
    def get_lyric(self, song: OnlineSong) -> Optional[str]:
        return self.lx_client.get_lyric(song)
        
    def get_pic(self, song: OnlineSong) -> Optional[bytes]:
        return self.lx_client.get_pic(song)
