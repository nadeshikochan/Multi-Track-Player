"""
自定义音源管理模块

模仿洛雪音乐的自定义音源机制，支持导入外部音源脚本
"""

import os
import re
import json
import threading
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass
from pathlib import Path
import urllib.request
import urllib.parse


@dataclass
class CustomSourceInfo:
    """自定义音源信息"""
    name: str
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    homepage: str = ""
    script_path: str = ""
    enabled: bool = True
    sources: Dict[str, Any] = None  # 支持的音源配置
    
    def __post_init__(self):
        if self.sources is None:
            self.sources = {}


class CustomSourceManager:
    """
    自定义音源管理器
    
    负责加载、管理和执行自定义音源脚本
    类似洛雪音乐的自定义源机制
    """
    
    # 支持的音源类型
    SUPPORTED_SOURCES = ['kw', 'kg', 'tx', 'wy', 'mg', 'local']
    
    # 支持的音质
    SUPPORTED_QUALITYS = ['128k', '320k', 'flac', 'flac24bit', 'hires']
    
    def __init__(self, sources_dir: str = None):
        """
        初始化音源管理器
        
        Args:
            sources_dir: 音源脚本存储目录
        """
        if sources_dir is None:
            sources_dir = os.path.join(os.path.expanduser("~"), ".multi_track_player", "sources")
        self.sources_dir = sources_dir
        os.makedirs(self.sources_dir, exist_ok=True)
        
        self.sources: Dict[str, CustomSourceInfo] = {}
        self.active_source: Optional[str] = None
        self._lock = threading.Lock()
        
        # API配置
        self._api_configs: Dict[str, Dict[str, str]] = {}
        
        # 加载保存的音源配置
        self._load_config()
        
    def _load_config(self):
        """加载音源配置"""
        config_path = os.path.join(self.sources_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self._api_configs = config.get('api_configs', {})
                    self.active_source = config.get('active_source')
            except Exception as e:
                print(f"加载音源配置失败: {e}")
                
    def _save_config(self):
        """保存音源配置"""
        config_path = os.path.join(self.sources_dir, "config.json")
        try:
            config = {
                'api_configs': self._api_configs,
                'active_source': self.active_source,
                'sources': {k: {'enabled': v.enabled} for k, v in self.sources.items()}
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存音源配置失败: {e}")
            
    def parse_source_script(self, script_content: str) -> Optional[CustomSourceInfo]:
        """
        解析音源脚本头部信息
        
        Args:
            script_content: 脚本内容
            
        Returns:
            音源信息或None
        """
        # 解析注释头部
        # 格式: @name, @description, @version, @author, @homepage
        patterns = {
            'name': r'@name\s+(.+?)(?:\n|\*)',
            'description': r'@description\s+(.+?)(?:\n|\*)',
            'version': r'@version\s+(.+?)(?:\n|\*)',
            'author': r'@author\s+(.+?)(?:\n|\*)',
            'homepage': r'@homepage\s+(.+?)(?:\n|\*)',
        }
        
        info = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, script_content, re.IGNORECASE)
            if match:
                info[key] = match.group(1).strip()
                
        if not info.get('name'):
            return None
            
        return CustomSourceInfo(
            name=info.get('name', ''),
            description=info.get('description', ''),
            version=info.get('version', '1.0.0'),
            author=info.get('author', ''),
            homepage=info.get('homepage', '')
        )
        
    def import_source_from_file(self, file_path: str) -> tuple:
        """
        从文件导入音源
        
        Args:
            file_path: 音源脚本文件路径
            
        Returns:
            (success, message, source_info)
        """
        try:
            if not os.path.exists(file_path):
                return False, f"文件不存在: {file_path}", None
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            source_info = self.parse_source_script(content)
            if not source_info:
                return False, "无法解析音源脚本，请确保脚本包含正确的头部信息(@name)", None
                
            # 复制脚本到音源目录
            dest_path = os.path.join(self.sources_dir, f"{source_info.name}.js")
            with open(dest_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            source_info.script_path = dest_path
            
            with self._lock:
                self.sources[source_info.name] = source_info
                
            self._save_config()
            
            return True, f"成功导入音源: {source_info.name}", source_info
            
        except Exception as e:
            return False, f"导入失败: {str(e)}", None
            
    def import_source_from_url(self, url: str) -> tuple:
        """
        从URL导入音源
        
        Args:
            url: 音源脚本URL
            
        Returns:
            (success, message, source_info)
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read().decode('utf-8')
                
            source_info = self.parse_source_script(content)
            if not source_info:
                return False, "无法解析音源脚本，请确保脚本包含正确的头部信息(@name)", None
                
            # 保存脚本到音源目录
            dest_path = os.path.join(self.sources_dir, f"{source_info.name}.js")
            with open(dest_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            source_info.script_path = dest_path
            
            with self._lock:
                self.sources[source_info.name] = source_info
                
            self._save_config()
            
            return True, f"成功导入音源: {source_info.name}", source_info
            
        except urllib.error.URLError as e:
            return False, f"网络错误: {str(e)}", None
        except Exception as e:
            return False, f"导入失败: {str(e)}", None
            
    def remove_source(self, source_name: str) -> tuple:
        """
        移除音源
        
        Args:
            source_name: 音源名称
            
        Returns:
            (success, message)
        """
        with self._lock:
            if source_name not in self.sources:
                return False, f"音源不存在: {source_name}"
                
            source = self.sources[source_name]
            
            # 删除脚本文件
            if source.script_path and os.path.exists(source.script_path):
                try:
                    os.remove(source.script_path)
                except Exception as e:
                    print(f"删除脚本文件失败: {e}")
                    
            del self.sources[source_name]
            
            if self.active_source == source_name:
                self.active_source = None
                
        self._save_config()
        return True, f"已移除音源: {source_name}"
        
    def set_active_source(self, source_name: str) -> tuple:
        """
        设置活动音源
        
        Args:
            source_name: 音源名称
            
        Returns:
            (success, message)
        """
        with self._lock:
            if source_name not in self.sources:
                return False, f"音源不存在: {source_name}"
                
            self.active_source = source_name
            
        self._save_config()
        return True, f"已切换到音源: {source_name}"
        
    def get_all_sources(self) -> List[CustomSourceInfo]:
        """获取所有音源"""
        with self._lock:
            return list(self.sources.values())
            
    def get_active_source(self) -> Optional[CustomSourceInfo]:
        """获取当前活动音源"""
        with self._lock:
            if self.active_source and self.active_source in self.sources:
                return self.sources[self.active_source]
            return None
            
    def scan_sources_dir(self):
        """扫描音源目录，加载所有音源"""
        if not os.path.exists(self.sources_dir):
            return
            
        for filename in os.listdir(self.sources_dir):
            if filename.endswith('.js'):
                file_path = os.path.join(self.sources_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    source_info = self.parse_source_script(content)
                    if source_info:
                        source_info.script_path = file_path
                        with self._lock:
                            self.sources[source_info.name] = source_info
                except Exception as e:
                    print(f"加载音源失败 {filename}: {e}")
                    
    def set_api_config(self, source_name: str, api_url: str, api_key: str = ""):
        """
        设置音源的API配置
        
        Args:
            source_name: 音源名称
            api_url: API地址
            api_key: API密钥
        """
        self._api_configs[source_name] = {
            'api_url': api_url,
            'api_key': api_key
        }
        self._save_config()
        
    def get_api_config(self, source_name: str) -> Dict[str, str]:
        """获取音源的API配置"""
        return self._api_configs.get(source_name, {})


class SourceAPIProxy:
    """
    音源API代理
    
    提供统一的API接口，根据当前活动音源路由请求
    """
    
    def __init__(self, source_manager: CustomSourceManager):
        self.source_manager = source_manager
        self.timeout = 15
        
    def _request(self, url: str, headers: Dict[str, str] = None) -> Optional[str]:
        """发送HTTP请求"""
        try:
            if headers is None:
                headers = {}
            headers['User-Agent'] = 'MultiTrackPlayer/1.0'
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            print(f"请求失败: {e}")
            return None
            
    def search(self, keyword: str, source: str = 'kw', page: int = 1) -> List[Dict]:
        """
        搜索歌曲
        
        Args:
            keyword: 搜索关键词
            source: 音源代码
            page: 页码
            
        Returns:
            搜索结果列表
        """
        active_source = self.source_manager.get_active_source()
        if not active_source:
            return []
            
        config = self.source_manager.get_api_config(active_source.name)
        if not config.get('api_url'):
            return []
            
        api_url = config['api_url'].rstrip('/')
        api_key = config.get('api_key', '')
        
        url = f"{api_url}/music/search?source={source}&keyword={urllib.parse.quote(keyword)}&page={page}"
        
        headers = {}
        if api_key:
            headers['X-API-Key'] = api_key
            
        result = self._request(url, headers)
        if not result:
            return []
            
        try:
            data = json.loads(result)
            if data.get('code') == 200:
                return data.get('data', data.get('list', []))
        except json.JSONDecodeError:
            pass
            
        return []
        
    def get_music_url(self, song_id: str, source: str, quality: str = '320k') -> Optional[str]:
        """
        获取音乐播放链接
        
        Args:
            song_id: 歌曲ID
            source: 音源代码
            quality: 音质
            
        Returns:
            播放链接或None
        """
        active_source = self.source_manager.get_active_source()
        if not active_source:
            return None
            
        config = self.source_manager.get_api_config(active_source.name)
        if not config.get('api_url'):
            return None
            
        api_url = config['api_url'].rstrip('/')
        api_key = config.get('api_key', '')
        
        url = f"{api_url}/music/url?source={source}&songId={song_id}&quality={quality}"
        
        headers = {}
        if api_key:
            headers['X-API-Key'] = api_key
            
        result = self._request(url, headers)
        if not result:
            return None
            
        try:
            data = json.loads(result)
            if data.get('code') == 200:
                return data.get('url') or data.get('data', {}).get('url')
        except json.JSONDecodeError:
            pass
            
        return None


# 预设的热门音源配置
PRESET_SOURCES = [
    {
        'name': '新澜音源',
        'api_url': 'https://source.shiqianjiang.cn',
        'api_key': 'CERU_KEY-47FFA828BA6FF9FF50CF83E87EC97056',
        'description': '支持多平台高音质音乐'
    }
]


def get_preset_sources() -> List[Dict]:
    """获取预设音源列表"""
    return PRESET_SOURCES
