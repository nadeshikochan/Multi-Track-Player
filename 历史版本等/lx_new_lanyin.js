/*!
 * @name 新澜音源(LX版)
 * @description 移植自 CeruMusic 插件，支持全平台高音质
 * @version v2.0.5
 * @author 时迁酱 (Original), Ported by LX
 */

const API_URL = "https://source.shiqianjiang.cn";
const API_KEY = "CERU_KEY-47FFA828BA6FF9FF50CF83E87EC97056";

// 定义支持的源和音质
const MUSIC_QUALITY = {
  kw: ["128k", "320k", "flac", "flac24bit", "hires"],
  mg: ["128k", "320k", "flac", "flac24bit", "hires"],
  kg: ["128k", "320k", "flac", "flac24bit", "hires", "atmos", "master"],
  tx: ["128k", "320k", "flac", "flac24bit", "hires", "atmos", "atmos_plus", "master"],
  wy: ["128k", "320k", "flac", "flac24bit", "hires", "atmos", "master"]
};

const MUSIC_SOURCE = Object.keys(MUSIC_QUALITY);

// 从全局对象获取 LX 工具
const { EVENT_NAMES, request, on, send, env, version } = globalThis.lx;

// 封装 HTTP 请求
const httpFetch = (url, options = { method: "GET" }) => {
  return new Promise((resolve, reject) => {
    console.log(`[新澜音源] 请求: ${url}`);
    request(url, options, (err, resp) => {
      if (err) return reject(err);
      resolve(resp);
    });
  });
};

// 核心逻辑：获取音乐链接
const handleGetMusicUrl = async (source, musicInfo, quality) => {
  // 兼容各平台的 ID 获取
  const songId = musicInfo.hash ?? musicInfo.songmid ?? musicInfo.copyrightId ?? musicInfo.id;
  
  if (!songId) throw new Error("无法获取歌曲ID");

  console.log(`[新澜音源] 开始解析: Source=${source}, ID=${songId}, Quality=${quality}`);

  // CeruMusic 的 API 结构
  // GET /music/url?source=xxx&songId=xxx&quality=xxx
  const targetUrl = `${API_URL}/music/url?source=${source}&songId=${songId}&quality=${quality}`;

  const resp = await httpFetch(targetUrl, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY, // 关键鉴权头
      "User-Agent": `CeruMusic-Plugin/v2.0.1` 
    },
    timeout: 15000,
  });

  const { body } = resp;

  if (!body) throw new Error("API返回空数据");

  // 处理业务逻辑
  // CeruMusic API 成功通常返回 code: 200
  if (body.code === 200) {
      // 优先取 body.url，部分接口可能在不同层级，做一下兼容
      const musicUrl = body.url || (body.data ? body.data.url : null);
      if (musicUrl) {
          console.log(`[新澜音源] 解析成功: ${musicUrl}`);
          return musicUrl;
      } else {
        throw new Error("API返回成功但没有链接");
      }
  }

  // 错误处理
  switch (body.code) {
    case 403:
      throw new Error("API Key失效或鉴权失败");
    case 429:
      throw new Error("请求过于频繁，请稍后再试");
    case 500:
      throw new Error(`服务器错误: ${body.message || '未知错误'}`);
    default:
      throw new Error(body.message || `未知错误码: ${body.code}`);
  }
};

// 注册源信息
const musicSources = {};
MUSIC_SOURCE.forEach((item) => {
  musicSources[item] = {
    name: item,
    type: "music",
    actions: ["musicUrl"],
    qualitys: MUSIC_QUALITY[item],
  };
});

// 监听 LX 请求事件
on(EVENT_NAMES.request, ({ action, source, info }) => {
  switch (action) {
    case "musicUrl":
      return handleGetMusicUrl(source, info.musicInfo, info.type)
        .then((url) => Promise.resolve(url))
        .catch((err) => {
            console.error(`[新澜音源] 错误:`, err);
            return Promise.reject(err);
        });
    default:
      console.error(`未支持的操作: ${action}`);
      return Promise.reject("action not support");
  }
});

// 通知 LX 初始化完成
send(EVENT_NAMES.inited, {
  status: true,
  openDevTools: false, // 是否开启开发者工具，调试时可改为 true
  sources: musicSources,
});
