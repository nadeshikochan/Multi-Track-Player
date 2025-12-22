"""
个人音乐推荐系统 - 本地音乐版 v4.0

核心理念：
这是针对本地音乐库的推荐系统。所有本地音乐都是用户喜欢的歌曲。
重点不是预测"喜欢/不喜欢"，而是：

    根据当前播放的歌曲，推荐风格/类型最相似的下一首

核心功能：
1. 学习歌曲之间的"相似性" - 通过用户的连续播放行为
2. 当用户听完A歌后继续听B歌（不跳过），说明A和B风格相似
3. 当用户听A歌时秒切换到C歌，说明A和C可能不太搭配
4. 构建歌曲相似度图，用于推荐

v4.0 更新：
- 修复歌曲库初始化问题 - 确保所有歌曲都被注册并参与推荐
- 增强日志系统 - 详细记录所有操作，方便调试
- 优化推荐算法 - 对新歌曲给予公平的推荐机会
- 添加调试信息输出
"""

import json
import math
import random
import time
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple, Set, Callable
from collections import deque
from pathlib import Path
import hashlib


# 日志回调函数类型
LogCallback = Callable[[str, str], None]


@dataclass
class SongFeatures:
    """歌曲特征"""
    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0
    
    # 歌曲嵌入向量 - 用于计算相似度
    # 通过用户行为学习，相似的歌在向量空间中靠近
    embedding: List[float] = field(default_factory=lambda: [random.gauss(0, 0.3) for _ in range(32)])
    
    # 播放统计
    play_count: int = 0
    last_played: float = 0
    
    # 作为"当前歌曲"时，下一首歌的播放质量
    # 用于评估这首歌是否适合作为推荐起点
    avg_transition_quality: float = 0.5
    transition_count: int = 0
    
    # 初始状态标记 - 用于识别未学习过的歌曲
    is_initialized: bool = False
    
    def get_id(self) -> str:
        return hashlib.md5(self.path.encode()).hexdigest()[:16]
    
    def update_embedding(self, delta: List[float], learning_rate: float):
        """更新嵌入向量"""
        for i in range(min(len(self.embedding), len(delta))):
            self.embedding[i] += learning_rate * delta[i]
        # 归一化到单位球面
        norm = math.sqrt(sum(x**2 for x in self.embedding))
        if norm > 1e-8:
            self.embedding = [x / norm for x in self.embedding]


@dataclass 
class TransitionRecord:
    """歌曲转换记录 - 记录从A歌到B歌的转换质量"""
    from_song: str
    to_song: str
    
    # 转换质量统计
    good_count: int = 0      # 听完/听大半后自然过渡
    neutral_count: int = 0   # 听一部分后切换
    bad_count: int = 0       # 秒切
    
    last_update: float = 0
    
    @property
    def total_count(self) -> int:
        return self.good_count + self.neutral_count + self.bad_count
    
    @property
    def quality_score(self) -> float:
        """计算转换质量分数 (0-1)"""
        if self.total_count == 0:
            return 0.5  # 未知
        # good=1, neutral=0.5, bad=0
        return (self.good_count + 0.5 * self.neutral_count) / self.total_count
    
    @property
    def is_reliable(self) -> bool:
        """是否有足够数据"""
        return self.total_count >= 2


class PersonalMusicRecommender:
    """
    本地音乐推荐系统
    
    核心逻辑：根据当前播放的歌曲，推荐风格最相似的下一首
    """
    
    def __init__(self, data_dir: str = "./recommender_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 核心数据
        self.songs: Dict[str, SongFeatures] = {}  # path -> features
        self.transitions: Dict[str, TransitionRecord] = {}  # "from->to" -> record
        
        # 播放历史 - 用于学习
        self.play_history: deque = deque(maxlen=500)
        
        # 当前状态
        self.current_song: Optional[str] = None
        self.current_start_time: float = 0
        self.previous_song: Optional[str] = None
        
        # 最近播放 - 用于避免重复
        self.recent_plays: deque = deque(maxlen=20)
        
        # 当前会话喜好
        self.current_session_likes: deque = deque(maxlen=10)
        self.current_session_dislikes: deque = deque(maxlen=5)
        
        # 参数
        self.embedding_dim = 32
        self.base_learning_rate = 0.15  # 基础学习率
        self.learning_rate = 0.15  # 当前学习率（动态调整）
        self.similarity_threshold = 0.3  # 最低相似度阈值
        self.exploration_rate = 0.15  # 探索率：给新歌曲的机会
        
        # 动态学习率相关
        self.consecutive_likes = 0  # 连续喜欢计数
        self.consecutive_dislikes = 0  # 连续不喜欢计数
        
        # 日志系统
        self._log_callback: Optional[LogCallback] = None
        self._log_history: deque = deque(maxlen=500)
        
        self._load_data()
        self._log("INFO", f"推荐系统初始化完成，数据目录: {self.data_dir}")
        self._log("INFO", f"已加载 {len(self.songs)} 首歌曲数据，{len(self.transitions)} 条转换记录")
    
    def set_log_callback(self, callback: LogCallback):
        """设置日志回调函数，用于将日志发送到UI"""
        self._log_callback = callback
    
    def _log(self, level: str, message: str):
        """记录日志"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        # 保存到历史
        self._log_history.append({
            'timestamp': timestamp,
            'level': level,
            'message': message
        })
        
        # 打印到控制台
        print(f"[推荐系统] {log_entry}")
        
        # 调用回调（如果设置了）
        if self._log_callback:
            try:
                self._log_callback(level, message)
            except Exception as e:
                print(f"[推荐系统] 日志回调失败: {e}")
    
    def get_log_history(self) -> List[Dict]:
        """获取日志历史"""
        return list(self._log_history)
    
    def _load_data(self):
        """加载数据"""
        songs_file = self.data_dir / "songs.json"
        transitions_file = self.data_dir / "transitions.json"
        
        if songs_file.exists():
            try:
                with open(songs_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for path, song_data in data.items():
                        # 兼容旧数据：添加 is_initialized 字段
                        if 'is_initialized' not in song_data:
                            song_data['is_initialized'] = True  # 旧数据视为已初始化
                        self.songs[path] = SongFeatures(**song_data)
            except Exception as e:
                self._log("ERROR", f"加载歌曲数据失败: {e}")
        
        if transitions_file.exists():
            try:
                with open(transitions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, trans_data in data.items():
                        self.transitions[key] = TransitionRecord(**trans_data)
            except Exception as e:
                self._log("ERROR", f"加载转换数据失败: {e}")
    
    def save_data(self):
        """保存数据"""
        songs_file = self.data_dir / "songs.json"
        transitions_file = self.data_dir / "transitions.json"
        
        try:
            with open(songs_file, 'w', encoding='utf-8') as f:
                songs_data = {path: asdict(song) for path, song in self.songs.items()}
                json.dump(songs_data, f, ensure_ascii=False, indent=2)
            
            with open(transitions_file, 'w', encoding='utf-8') as f:
                trans_data = {key: asdict(trans) for key, trans in self.transitions.items()}
                json.dump(trans_data, f, ensure_ascii=False, indent=2)
            
            self._log("INFO", f"数据已保存：{len(self.songs)} 首歌曲，{len(self.transitions)} 条转换记录")
        except Exception as e:
            self._log("ERROR", f"保存数据失败: {e}")
    
    def save(self):
        """保存数据的别名"""
        self.save_data()
    
    def register_song(self, song_info: Dict[str, Any]) -> Optional[SongFeatures]:
        """注册单首歌曲"""
        path = song_info.get('path', '')
        if not path:
            return None
            
        if path not in self.songs:
            self.songs[path] = SongFeatures(
                path=path,
                title=song_info.get('title', ''),
                artist=song_info.get('artist', ''),
                album=song_info.get('album', ''),
                duration=song_info.get('duration', 0),
                is_initialized=False  # 新歌标记为未初始化
            )
            self._log("DEBUG", f"新歌曲注册: {song_info.get('title', path)}")
        else:
            song = self.songs[path]
            if song_info.get('title'):
                song.title = song_info['title']
            if song_info.get('artist'):
                song.artist = song_info['artist']
        
        return self.songs[path]
    
    def register_song_pool(self, songs: List[Dict[str, Any]]):
        """
        批量注册歌曲池 - 这是关键的初始化方法！
        
        应该在加载音乐库后立即调用，确保所有歌曲都参与推荐
        """
        new_count = 0
        updated_count = 0
        
        for song_info in songs:
            path = song_info.get('path', '')
            if not path:
                continue
                
            if path not in self.songs:
                self.songs[path] = SongFeatures(
                    path=path,
                    title=song_info.get('title', ''),
                    artist=song_info.get('artist', ''),
                    album=song_info.get('album', ''),
                    duration=song_info.get('duration', 0),
                    is_initialized=False
                )
                new_count += 1
            else:
                # 更新已有歌曲的元数据
                song = self.songs[path]
                if song_info.get('title'):
                    song.title = song_info['title']
                if song_info.get('artist'):
                    song.artist = song_info['artist']
                updated_count += 1
        
        total = len(self.songs)
        self._log("INFO", f"歌曲池已更新: 新增 {new_count} 首, 更新 {updated_count} 首, 总共 {total} 首")
        
        # 统计已学习和未学习的歌曲
        learned = sum(1 for s in self.songs.values() if s.is_initialized)
        unlearned = total - learned
        self._log("INFO", f"学习状态: {learned} 首已学习, {unlearned} 首待学习")
    
    def on_song_start(self, song_info: Dict[str, Any]):
        """歌曲开始播放"""
        path = song_info.get('path', '')
        self.register_song(song_info)
        
        # 记录上一首
        if self.current_song:
            self.previous_song = self.current_song
        
        self.current_song = path
        self.current_start_time = time.time()
        
        if path in self.songs:
            song = self.songs[path]
            song.play_count += 1
            song.last_played = time.time()
            
            title = song.title or os.path.basename(path)
            self._log("INFO", f"开始播放: {title} (第 {song.play_count} 次)")
        
        self.recent_plays.append(path)
    
    def on_song_end(self, song_info: Dict[str, Any], listen_time: float, action: str):
        """
        歌曲结束播放 - 核心学习时机
        
        播放行为决定学习方式：
        - complete/听完: 说明当前喜欢这种类型，强化这首歌的权重
        - half/听一半: 一般喜欢，轻微正向
        - skip/秒切: 当前不想听这种类型，降低相似歌曲的推荐权重
        """
        path = song_info.get('path', '')
        duration = song_info.get('duration', 0) or 180
        
        if path not in self.songs:
            self.register_song(song_info)
        
        song = self.songs.get(path)
        title = song.title if song else os.path.basename(path)
        
        # 计算播放比例
        ratio = listen_time / duration if duration > 0 else 0
        
        self._log("DEBUG", f"on_song_end 被调用: {title}, listen_time={listen_time:.1f}s, duration={duration:.1f}s, action={action}")
        
        # 根据action参数直接判断（播放器已经检测好了）
        if action == 'complete':
            quality = 'good'
            self._record_current_preference(path, 'like')
        elif action == 'half':
            quality = 'neutral'
            self._record_current_preference(path, 'neutral')
        elif action == 'skip':
            quality = 'bad'
            self._record_current_preference(path, 'dislike')
        else:
            # 回退到比例判断
            if ratio >= 0.7:
                quality = 'good'
                self._record_current_preference(path, 'like')
            elif ratio >= 0.3:
                quality = 'neutral'
                self._record_current_preference(path, 'neutral')
            else:
                quality = 'bad'
                self._record_current_preference(path, 'dislike')
        
        # 【新增】动态调整学习率
        self._adjust_learning_rate(quality)
        
        quality_emoji = {'good': '✅', 'neutral': '➡️', 'bad': '⏭️'}[quality]
        self._log("INFO", f"学习反馈: {quality_emoji} {quality} - {title} (播放 {ratio:.0%}, 学习率 {self.learning_rate:.3f})")
        
        # 标记歌曲已被学习
        if song:
            song.is_initialized = True
        
        # 如果有上一首歌，更新转换记录和嵌入
        if self.previous_song and self.previous_song != path:
            prev_song = self.songs.get(self.previous_song)
            prev_title = prev_song.title if prev_song else os.path.basename(self.previous_song)
            self._log("DEBUG", f"更新转换关系: {prev_title} → {title} ({quality})")
            
            self._update_transition(self.previous_song, path, quality)
            self._update_embeddings(self.previous_song, path, quality)
        
        # 记录历史
        self.play_history.append({
            'song': path,
            'prev_song': self.previous_song,
            'quality': quality,
            'listen_time': listen_time,
            'duration': duration,
            'ratio': ratio,
            'timestamp': time.time()
        })
        
        # 定期保存
        if len(self.play_history) % 10 == 0:
            self.save_data()
    
    def _record_current_preference(self, path: str, preference: str):
        """记录当前的喜好偏向"""
        if preference == 'like':
            self.current_session_likes.append(path)
            if path in self.current_session_dislikes:
                self.current_session_dislikes.remove(path)
        elif preference == 'dislike':
            self.current_session_dislikes.append(path)
            if path in self.current_session_likes:
                self.current_session_likes.remove(path)
    
    def _adjust_learning_rate(self, quality: str):
        """
        动态调整学习率
        
        策略：
        - 连续喜欢 → 降低学习率（推荐准确，不需要大幅调整）
        - 连续不喜欢 → 提高学习率（推荐不准，需要快速调整）
        - 行为反转 → 重置计数器
        """
        if quality == 'good':
            self.consecutive_likes += 1
            self.consecutive_dislikes = 0
        elif quality == 'bad':
            self.consecutive_dislikes += 1
            self.consecutive_likes = 0
        else:
            # neutral 轻微重置
            self.consecutive_likes = max(0, self.consecutive_likes - 1)
            self.consecutive_dislikes = max(0, self.consecutive_dislikes - 1)
        
        # 计算动态学习率
        if self.consecutive_dislikes >= 3:
            # 连续跳过3首以上 → 快速学习模式
            self.learning_rate = min(0.35, self.base_learning_rate * 2.0)
            self._log("DEBUG", f"快速学习模式激活 (连续跳过 {self.consecutive_dislikes} 首)")
        elif self.consecutive_dislikes >= 2:
            # 连续跳过2首 → 提高学习率
            self.learning_rate = min(0.25, self.base_learning_rate * 1.5)
        elif self.consecutive_likes >= 5:
            # 连续喜欢5首以上 → 稳定模式
            self.learning_rate = max(0.05, self.base_learning_rate * 0.5)
            self._log("DEBUG", f"稳定模式 (连续完成 {self.consecutive_likes} 首)")
        elif self.consecutive_likes >= 3:
            # 连续喜欢3首 → 轻微降低
            self.learning_rate = max(0.08, self.base_learning_rate * 0.7)
        else:
            # 正常模式
            self.learning_rate = self.base_learning_rate
    
    def _update_transition(self, from_path: str, to_path: str, quality: str):
        """更新转换记录"""
        key = f"{from_path}->{to_path}"
        
        if key not in self.transitions:
            self.transitions[key] = TransitionRecord(
                from_song=from_path,
                to_song=to_path
            )
        
        trans = self.transitions[key]
        if quality == 'good':
            trans.good_count += 1
        elif quality == 'neutral':
            trans.neutral_count += 1
        else:
            trans.bad_count += 1
        trans.last_update = time.time()
        
        # 更新源歌曲的平均转换质量
        if from_path in self.songs:
            song = self.songs[from_path]
            song.transition_count += 1
            quality_value = {'good': 1.0, 'neutral': 0.5, 'bad': 0.0}[quality]
            song.avg_transition_quality += (quality_value - song.avg_transition_quality) / song.transition_count
    
    def _update_embeddings(self, from_path: str, to_path: str, quality: str):
        """根据转换质量更新歌曲嵌入"""
        if from_path not in self.songs or to_path not in self.songs:
            return
        
        from_song = self.songs[from_path]
        to_song = self.songs[to_path]
        
        # 计算方向向量 (from -> to)
        direction = [
            to_song.embedding[i] - from_song.embedding[i] 
            for i in range(self.embedding_dim)
        ]
        
        lr = self.learning_rate
        
        if quality == 'good':
            # 好的转换：让两首歌靠近
            to_song.update_embedding([-d * 0.5 for d in direction], lr)
            from_song.update_embedding([d * 0.5 for d in direction], lr)
        elif quality == 'bad':
            # 差的转换：让两首歌远离
            to_song.update_embedding([d * 0.3 for d in direction], lr)
            from_song.update_embedding([-d * 0.3 for d in direction], lr)
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 * norm2 < 1e-8:
            return 0
        return dot / (norm1 * norm2)
    
    def get_next_recommendation(self, 
                                 current_song: Optional[Dict] = None,
                                 exclude_paths: Optional[Set[str]] = None
                                 ) -> Optional[Tuple[Dict, str]]:
        """获取下一首推荐歌曲"""
        if not self.songs:
            self._log("WARNING", "歌曲库为空，无法推荐")
            return None
        
        current_path = current_song.get('path') if current_song else None
        exclude = set(exclude_paths or [])
        exclude.update(self.recent_plays)
        
        if current_path:
            exclude.add(current_path)
        
        # 如果没有当前歌曲，随机选一首
        if not current_path or current_path not in self.songs:
            available = [p for p in self.songs if p not in exclude]
            if not available:
                available = list(self.songs.keys())
            selected = random.choice(available)
            self._log("INFO", f"随机选择: {self.songs[selected].title or os.path.basename(selected)}")
            return self._make_song_info(selected), "随机播放"
        
        current = self.songs[current_path]
        
        # 计算所有候选歌曲的得分
        candidates = []
        for path, song in self.songs.items():
            if path in exclude:
                continue
            
            score, reason = self._compute_similarity_score(current, song, current_path, path)
            candidates.append((path, score, reason))
        
        if not candidates:
            available = [p for p in self.songs if p != current_path]
            if available:
                selected = random.choice(available)
                return self._make_song_info(selected), "随机推荐"
            return None
        
        # 按得分排序
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # 从top candidates中选择
        top_n = min(5, len(candidates))
        weights = [0.4, 0.25, 0.15, 0.12, 0.08][:top_n]
        
        selected_idx = random.choices(range(top_n), weights=weights[:top_n])[0]
        selected_path, score, reason = candidates[selected_idx]
        
        self._log("INFO", f"推荐: {self.songs[selected_path].title or os.path.basename(selected_path)} (得分: {score:.3f}, {reason})")
        
        return self._make_song_info(selected_path), reason
    
    def _compute_similarity_score(self, current: SongFeatures, candidate: SongFeatures,
                                   current_path: str, candidate_path: str) -> Tuple[float, str]:
        """
        计算候选歌曲的相似度得分
        
        综合考虑：
        1. 与当前会话喜欢的歌曲的相似度
        2. 嵌入向量相似度
        3. 历史转换记录
        4. 艺术家/专辑匹配
        5. 探索加成（给新歌曲机会）
        """
        score = 0.0
        reasons = []
        
        # 0. 探索加成 - 给未学习过的歌曲一个基础分数
        if not candidate.is_initialized:
            exploration_bonus = self.exploration_rate * 0.3
            score += exploration_bonus
            reasons.append("新歌探索")
        
        # 1. 当前会话喜好加成 (权重: 25%)
        session_score = self._compute_session_preference_score(candidate_path, candidate)
        if session_score > 0:
            score += 0.25 * session_score
            if session_score > 0.7:
                reasons.append("符合当前喜好")
        elif session_score < 0:
            score += 0.25 * session_score
            if session_score < -0.3:
                reasons.append("当前不太想听")
        
        # 2. 嵌入相似度 (权重: 35%)
        embedding_sim = self._cosine_similarity(current.embedding, candidate.embedding)
        embedding_score = (embedding_sim + 1) / 2
        score += 0.35 * embedding_score
        
        if embedding_sim > 0.7:
            reasons.append("风格很相似")
        elif embedding_sim > 0.4:
            reasons.append("风格接近")
        
        # 3. 历史转换记录 (权重: 25%)
        trans_key = f"{current_path}->{candidate_path}"
        if trans_key in self.transitions:
            trans = self.transitions[trans_key]
            if trans.is_reliable:
                trans_score = trans.quality_score
                score += 0.25 * trans_score
                if trans_score > 0.7:
                    reasons.append("以前衔接很好")
                elif trans_score > 0.5:
                    reasons.append("衔接不错")
        else:
            score += 0.25 * 0.5
        
        # 4. 元数据匹配 (权重: 15%)
        meta_score = 0.0
        
        if current.artist and candidate.artist:
            if current.artist.lower() == candidate.artist.lower():
                meta_score += 0.6
                reasons.append("同一艺术家")
            elif current.artist.lower() in candidate.artist.lower() or \
                 candidate.artist.lower() in current.artist.lower():
                meta_score += 0.3
        
        if current.album and candidate.album:
            if current.album.lower() == candidate.album.lower():
                meta_score += 0.4
                if "同一艺术家" not in reasons:
                    reasons.append("同一专辑")
        
        score += 0.15 * min(1.0, meta_score)
        
        # 5. 新鲜度调整
        if candidate.last_played > 0:
            hours_since = (time.time() - candidate.last_played) / 3600
            if hours_since < 0.5:
                score *= 0.8
            elif hours_since > 24:
                score *= 1.05
        
        reason = "；".join(reasons) if reasons else "智能推荐"
        return score, reason
    
    def _compute_session_preference_score(self, candidate_path: str, candidate: SongFeatures) -> float:
        """计算候选歌曲与当前会话喜好的匹配度"""
        like_score = 0.0
        dislike_score = 0.0
        
        if self.current_session_likes:
            like_sims = []
            for liked_path in self.current_session_likes:
                if liked_path in self.songs and liked_path != candidate_path:
                    liked_song = self.songs[liked_path]
                    sim = self._cosine_similarity(candidate.embedding, liked_song.embedding)
                    like_sims.append(sim)
            if like_sims:
                like_score = sum(like_sims) / len(like_sims)
        
        if self.current_session_dislikes:
            dislike_sims = []
            for disliked_path in self.current_session_dislikes:
                if disliked_path in self.songs and disliked_path != candidate_path:
                    disliked_song = self.songs[disliked_path]
                    sim = self._cosine_similarity(candidate.embedding, disliked_song.embedding)
                    dislike_sims.append(sim)
            if dislike_sims:
                dislike_score = sum(dislike_sims) / len(dislike_sims)
        
        final_score = like_score - dislike_score * 0.5
        return max(-1.0, min(1.0, final_score))
    
    def _make_song_info(self, path: str) -> Dict:
        """构建歌曲信息字典"""
        if path in self.songs:
            song = self.songs[path]
            return {
                'path': song.path,
                'title': song.title,
                'artist': song.artist,
                'album': song.album,
                'duration': song.duration
            }
        return {'path': path}
    
    def get_similar_songs(self, song_path: str, count: int = 10) -> List[Tuple[Dict, float]]:
        """获取与指定歌曲最相似的歌曲列表"""
        if song_path not in self.songs:
            return []
        
        current = self.songs[song_path]
        
        similarities = []
        for path, song in self.songs.items():
            if path == song_path:
                continue
            
            sim = self._cosine_similarity(current.embedding, song.embedding)
            similarities.append((path, sim))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for path, sim in similarities[:count]:
            results.append((self._make_song_info(path), sim))
        
        return results
    
    def get_top_recommendations(self, 
                                 current_song: Optional[Dict] = None,
                                 count: int = 20,
                                 exclude_paths: Optional[Set[str]] = None
                                 ) -> List[Tuple[Dict, str]]:
        """获取推荐排名前N的歌曲列表"""
        if not self.songs:
            self._log("WARNING", "歌曲库为空，无法生成推荐列表")
            return []
        
        current_path = current_song.get('path') if current_song else None
        exclude = set(exclude_paths or [])
        exclude.update(self.recent_plays)
        
        if current_path:
            exclude.add(current_path)
        
        self._log("DEBUG", f"生成推荐列表: 当前歌曲={current_path}, 排除={len(exclude)}首, 歌曲库={len(self.songs)}首")
        
        # 如果没有当前歌曲，返回随机歌曲列表
        if not current_path or current_path not in self.songs:
            available = [p for p in self.songs if p not in exclude]
            if not available:
                available = list(self.songs.keys())
            random.shuffle(available)
            self._log("INFO", f"无当前歌曲，返回 {min(count, len(available))} 首随机推荐")
            return [(self._make_song_info(p), "随机播放") for p in available[:count]]
        
        current = self.songs[current_path]
        
        # 计算所有候选歌曲的得分
        candidates = []
        for path, song in self.songs.items():
            if path in exclude:
                continue
            
            score, reason = self._compute_similarity_score(current, song, current_path, path)
            candidates.append((path, score, reason))
        
        if not candidates:
            available = [p for p in self.songs if p != current_path]
            random.shuffle(available)
            self._log("WARNING", f"无候选歌曲（排除太多），返回 {min(count, len(available))} 首随机推荐")
            return [(self._make_song_info(p), "随机推荐") for p in available[:count]]
        
        # 按得分排序
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # 记录推荐详情
        self._log("DEBUG", f"候选歌曲: {len(candidates)} 首")
        for i, (path, score, reason) in enumerate(candidates[:5]):
            song = self.songs[path]
            title = song.title or os.path.basename(path)
            self._log("DEBUG", f"  Top {i+1}: {title} (得分: {score:.3f}, {reason})")
        
        # 返回前N个推荐
        results = []
        for path, score, reason in candidates[:count]:
            results.append((self._make_song_info(path), reason))
        
        self._log("INFO", f"返回 {len(results)} 首推荐")
        return results
    
    def on_positive_feedback(self):
        """用户觉得当前推荐很好"""
        recent = list(self.play_history)[-5:]
        for record in recent:
            if record.get('prev_song') and record.get('song'):
                self._update_embeddings(record['prev_song'], record['song'], 'good')
        
        self._log("INFO", "收到正向反馈 👍，已强化最近的转换关系")
    
    def on_negative_feedback(self):
        """用户觉得当前推荐不好"""
        recent = list(self.play_history)[-3:]
        for record in recent:
            if record.get('prev_song') and record.get('song'):
                self._update_embeddings(record['prev_song'], record['song'], 'bad')
        
        self._log("INFO", "收到负向反馈 👎，已削弱最近的转换关系")
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        total_songs = len(self.songs)
        total_transitions = len(self.transitions)
        
        # 统计已学习和未学习的歌曲
        learned_songs = sum(1 for s in self.songs.values() if s.is_initialized)
        unlearned_songs = total_songs - learned_songs
        
        # 按播放次数排序的歌曲列表
        all_songs = sorted(
            [
                {
                    'path': s.path,
                    'title': s.title or os.path.basename(s.path),
                    'artist': s.artist,
                    'score': round(s.avg_transition_quality, 3),
                    'confidence': min(1.0, s.transition_count / 10),
                    'play_count': s.play_count,
                    'skip_count': 0,
                    'complete_count': s.play_count,
                    'is_learned': s.is_initialized,
                }
                for s in self.songs.values()
            ],
            key=lambda x: x['play_count'],
            reverse=True
        )
        
        # 找出转换质量最好的歌曲
        top_songs = sorted(
            [(s.path, s.avg_transition_quality, min(1.0, s.transition_count / 10)) 
             for s in self.songs.values() if s.transition_count >= 3],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # 当前会话喜好
        session_likes_info = []
        for path in self.current_session_likes:
            if path in self.songs:
                song = self.songs[path]
                session_likes_info.append(song.title or os.path.basename(path))
        
        session_dislikes_info = []
        for path in self.current_session_dislikes:
            if path in self.songs:
                song = self.songs[path]
                session_dislikes_info.append(song.title or os.path.basename(path))
        
        return {
            'total_songs': total_songs,
            'learned_songs': learned_songs,
            'unlearned_songs': unlearned_songs,
            'total_plays': sum(s.play_count for s in self.songs.values()),
            'total_skips': 0,
            'skip_rate': 0,
            'transition_count': total_transitions,
            'history_events': len(self.play_history),
            'session': {
                'songs_played': len(self.recent_plays),
                'songs_completed': len(self.current_session_likes),
                'songs_skipped': len(self.current_session_dislikes),
                'recent_skip_rate': len(self.current_session_dislikes) / max(1, len(self.recent_plays)),
                'is_picky_mode': self.consecutive_dislikes >= 2,  # 使用动态计数
                'is_relaxed_mode': self.consecutive_likes >= 3,  # 使用动态计数
                'consecutive_good': self.consecutive_likes,  # 连续喜欢计数
                'consecutive_bad': self.consecutive_dislikes,  # 连续跳过计数
                'current_learning_rate': self.learning_rate,
                'base_learning_rate': self.base_learning_rate,
                'current_likes': session_likes_info,
                'current_dislikes': session_dislikes_info,
            },
            'top_songs': [
                {'path': p, 'score': round(s, 3), 'confidence': round(c, 3)}
                for p, s, c in top_songs
            ],
            'bottom_songs': [],
            'all_songs': all_songs,
            'exploration_rate': self.exploration_rate
        }
    
    def reset(self):
        """重置所有数据"""
        self.songs.clear()
        self.transitions.clear()
        self.play_history.clear()
        self.recent_plays.clear()
        self.current_session_likes.clear()
        self.current_session_dislikes.clear()
        self.current_song = None
        self.previous_song = None
        self.save_data()
        self._log("WARNING", "所有数据已重置")
    
    def reset_session(self):
        """重置当前会话"""
        self.recent_plays.clear()
        self.previous_song = None
        self.current_session_likes.clear()
        self.current_session_dislikes.clear()
        # 重置动态学习率
        self.consecutive_likes = 0
        self.consecutive_dislikes = 0
        self.learning_rate = self.base_learning_rate
        self._log("INFO", "当前会话已重置")
    
    def export_model(self, filepath: str):
        """导出模型"""
        model_data = {
            'songs': {path: asdict(song) for path, song in self.songs.items()},
            'transitions': {key: asdict(trans) for key, trans in self.transitions.items()},
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(model_data, f, ensure_ascii=False, indent=2)
        self._log("INFO", f"模型已导出到: {filepath}")
    
    def import_model(self, filepath: str):
        """导入模型"""
        with open(filepath, 'r', encoding='utf-8') as f:
            model_data = json.load(f)
        
        for path, song_data in model_data.get('songs', {}).items():
            if 'is_initialized' not in song_data:
                song_data['is_initialized'] = True
            self.songs[path] = SongFeatures(**song_data)
        
        for key, trans_data in model_data.get('transitions', {}).items():
            self.transitions[key] = TransitionRecord(**trans_data)
        
        self._log("INFO", f"模型已导入: {len(self.songs)} 首歌曲")
    
    def get_song_info(self, path: str) -> Optional[Dict]:
        """获取歌曲信息"""
        if path in self.songs:
            return self._make_song_info(path)
        return None
    
    def get_all_song_paths(self) -> List[str]:
        """获取所有歌曲路径"""
        return list(self.songs.keys())
