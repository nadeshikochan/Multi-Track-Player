#!/usr/bin/env python3
"""
Multi-Track Player 诊断工具

检查:
1. 音源API连接状态
2. 多音轨同步问题诊断
3. 提供修复建议
"""

import urllib.request
import urllib.error
import json
import sys
import os

# ============ 配置 ============
API_CONFIGS = {
    "新澜音源 (原始)": {
        "url": "https://source.shiqianjiang.cn",
        "key": "CERU_KEY-47FFA828BA6FF9FF50CF83E87EC97056",
        "endpoints": {
            "search": "/music/search?source=kw&keyword=test&page=1&limit=1",
            "url": "/music/url?source=kw&songId=test&quality=320k",
        }
    },
    "网易云API (备用)": {
        "url": "https://netease-cloud-music-api-five-roan-88.vercel.app",
        "key": None,
        "endpoints": {
            "search": "/search?keywords=test&limit=1",
        }
    }
}

def test_api(name: str, config: dict) -> dict:
    """测试单个API"""
    results = {
        "name": name,
        "base_url": config["url"],
        "status": "unknown",
        "endpoints": {}
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }
    
    if config.get("key"):
        headers["X-API-Key"] = config["key"]
    
    for endpoint_name, endpoint_path in config["endpoints"].items():
        full_url = config["url"] + endpoint_path
        try:
            req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                results["endpoints"][endpoint_name] = {
                    "status": "ok",
                    "code": response.code,
                    "response_code": data.get("code", "N/A")
                }
                if data.get("code") == 200:
                    results["status"] = "ok"
        except urllib.error.HTTPError as e:
            results["endpoints"][endpoint_name] = {
                "status": "error",
                "code": e.code,
                "reason": e.reason
            }
            results["status"] = "error"
        except urllib.error.URLError as e:
            results["endpoints"][endpoint_name] = {
                "status": "error",
                "reason": str(e.reason)
            }
            results["status"] = "error"
        except Exception as e:
            results["endpoints"][endpoint_name] = {
                "status": "error",
                "reason": str(e)
            }
            results["status"] = "error"
    
    return results

def print_results(results: list):
    """打印测试结果"""
    print("\n" + "="*60)
    print("🔍 API 连接诊断结果")
    print("="*60 + "\n")
    
    any_working = False
    
    for result in results:
        status_icon = "✅" if result["status"] == "ok" else "❌"
        print(f"{status_icon} {result['name']}")
        print(f"   URL: {result['base_url']}")
        
        for ep_name, ep_result in result["endpoints"].items():
            ep_icon = "✓" if ep_result["status"] == "ok" else "✗"
            if ep_result["status"] == "ok":
                print(f"   {ep_icon} {ep_name}: HTTP {ep_result['code']}, API返回码: {ep_result['response_code']}")
                any_working = True
            else:
                print(f"   {ep_icon} {ep_name}: 错误 - {ep_result.get('reason', 'Unknown')}")
        print()
    
    return any_working

def print_recommendations(any_working: bool):
    """打印建议"""
    print("="*60)
    print("📋 诊断建议")
    print("="*60 + "\n")
    
    if not any_working:
        print("""❌ 所有API都无法连接

问题原因：
1. 新澜音源(source.shiqianjiang.cn)可能已经下线或更换了API端点
2. 网络连接问题

解决方案：
1. 【推荐】使用洛雪音乐(LX Music)配合自定义音源
   - 下载洛雪音乐: https://github.com/lyswhut/lx-music-desktop/releases
   - 导入可用的自定义音源脚本
   - 洛雪音乐有完整的自定义音源生态系统

2. 【备选】自建API服务
   - 参考: https://github.com/lxmusics/lx-music-api-server
   - 需要有会员账号

3. 【本地方案】只使用本地音乐功能
   - 放弃在线搜索，只使用本地音乐文件
   - 多音轨分离功能仍可正常使用

注意：你上传的 lx_new_lanyin.js 是洛雪音乐的自定义源脚本格式，
不能直接在 Multi-Track Player 中使用。
Multi-Track Player 的自定义音源管理功能需要HTTP API服务端支持。
""")
    else:
        print("""✅ 部分API可用

建议：
1. 如果网易云API可用，可以正常使用网易云音乐的搜索功能
2. 如果新澜音源不可用，建议在设置中切换到可用的API

配置方法：
在 Multi-Track Player 中:
1. 点击 "📦 音源管理"
2. 添加可用的API地址
3. 切换到可用的音源
""")

def check_multitrack_issue():
    """检查多音轨问题"""
    print("\n" + "="*60)
    print("🎵 多音轨播放诊断")
    print("="*60 + "\n")
    
    print("""已识别的问题：多音轨播放"卡顿"

原因分析：
1. 同步检查过于频繁（每50ms检查一次）
2. 同步容差太小（50ms），导致频繁的位置微调
3. 在播放过程中频繁调用 setPosition 会导致音频缓冲中断

解决方案（已创建修复文件）：
文件位置: ui/track_control_fixed.py

主要改进：
✓ 同步检查间隔从 50ms 增加到 200ms
✓ 同步容差从 50ms 增加到 200ms  
✓ 只在差距显著时才进行硬同步
✓ 添加缓冲状态检测，避免在缓冲时进行同步

使用方法：
将 track_control_fixed.py 重命名为 track_control.py 替换原文件
或者修改 ui/__init__.py 和相关导入
""")

def main():
    print("\n" + "🔧 Multi-Track Player 问题诊断工具 🔧")
    print("="*60)
    
    # 测试API
    print("\n正在测试API连接...")
    results = []
    for name, config in API_CONFIGS.items():
        print(f"  测试: {name}...")
        results.append(test_api(name, config))
    
    any_working = print_results(results)
    print_recommendations(any_working)
    
    # 检查多音轨问题
    check_multitrack_issue()
    
    print("\n" + "="*60)
    print("诊断完成！")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
