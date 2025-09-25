import os
import time
import json
import subprocess
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request
import psutil

app = Flask(__name__)

class RemoteDesktopDetector:
    def __init__(self):
        self.is_remote_session = False
        self.last_check_time = None
        self.connection_history = []
        
    def check_remote_desktop_status(self):
        """检测是否通过远程桌面连接"""
        try:
            # 方法1: 检查环境变量
            if os.environ.get('SESSIONNAME', '').startswith('RDP-'):
                return True
                
            # 方法2: 检查进程
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and 'rdp' in proc.info['name'].lower():
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
            # 方法3: 检查注册表 (Windows)
            try:
                result = subprocess.run(
                    ['reg', 'query', 'HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server', 
                     '/v', 'fDenyTSConnections'],
                    capture_output=True, text=True, timeout=5
                )
                if '0x0' in result.stdout:  # 远程桌面已启用
                    # 进一步检查是否有活动连接
                    result2 = subprocess.run(
                        ['query', 'session'],
                        capture_output=True, text=True, timeout=5
                    )
                    if 'rdp-tcp' in result2.stdout.lower():
                        return True
            except:
                pass
                
            return False
            
        except Exception as e:
            print(f"检测远程桌面状态时出错: {e}")
            return False
    
    def update_status(self):
        """更新连接状态"""
        current_status = self.check_remote_desktop_status()
        current_time = datetime.now()
        
        # 如果状态发生变化，记录历史
        if current_status != self.is_remote_session:
            self.connection_history.append({
                'timestamp': current_time.isoformat(),
                'status': 'connected' if current_status else 'disconnected',
                'message': '远程桌面已连接' if current_status else '远程桌面已断开'
            })
            
            # 只保留最近50条记录
            if len(self.connection_history) > 50:
                self.connection_history = self.connection_history[-50:]
        
        self.is_remote_session = current_status
        self.last_check_time = current_time
    
    def get_status_info(self):
        """获取状态信息"""
        return {
            'is_remote_session': self.is_remote_session,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'status_text': '远程桌面已连接' if self.is_remote_session else '本地使用',
            'connection_history': self.connection_history[-10:]  # 最近10条记录
        }

# 创建检测器实例
detector = RemoteDesktopDetector()

@app.route('/')
def index():
    """主页 - 显示状态页面"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """API - 获取当前状态"""
    detector.update_status()
    return jsonify(detector.get_status_info())

@app.route('/api/history')
def api_history():
    """API - 获取连接历史"""
    return jsonify({
        'history': detector.connection_history,
        'total_records': len(detector.connection_history)
    })

@app.route('/api/force_check')
def api_force_check():
    """API - 强制检查状态"""
    detector.update_status()
    return jsonify({
        'message': '状态已更新',
        'status': detector.get_status_info()
    })

def background_monitor():
    """后台监控线程"""
    while True:
        try:
            detector.update_status()
            time.sleep(10)  # 每10秒检查一次
        except Exception as e:
            print(f"后台监控出错: {e}")
            time.sleep(10)

if __name__ == '__main__':
    # 创建模板目录和文件
    os.makedirs('templates', exist_ok=True)
    
    # 创建HTML模板
    html_template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>远程桌面状态监控</title>
    <style>
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
        }
        .status-card {
            padding: 30px;
            text-align: center;
        }
        .status-indicator {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            margin: 0 auto 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: bold;
            color: white;
            transition: all 0.3s ease;
        }
        .status-connected {
            background: #e74c3c;
            animation: pulse 2s infinite;
        }
        .status-disconnected {
            background: #27ae60;
        }
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
        .status-text {
            font-size: 24px;
            margin: 20px 0;
            color: #2c3e50;
        }
        .last-check {
            color: #7f8c8d;
            font-size: 14px;
        }
        .history {
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 5px;
        }
        .history-item {
            padding: 10px;
            margin: 5px 0;
            background: white;
            border-radius: 5px;
            border-left: 4px solid #3498db;
        }
        .history-time {
            font-size: 12px;
            color: #7f8c8d;
        }
        .refresh-btn {
            background: #3498db;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 10px;
        }
        .refresh-btn:hover {
            background: #2980b9;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🖥️ 远程桌面状态监控</h1>
            <p>实时监控远程桌面连接状态</p>
        </div>
        
        <div class="status-card">
            <div id="statusIndicator" class="status-indicator">
                <span id="statusIcon">⏳</span>
            </div>
            <div id="statusText" class="status-text">检查中...</div>
            <div id="lastCheck" class="last-check">最后检查: --</div>
            <button class="refresh-btn" onclick="checkStatus()">🔄 刷新状态</button>
        </div>
        
        <div class="history">
            <h3>📋 连接历史</h3>
            <div id="historyList">加载中...</div>
        </div>
    </div>

    <script>
        function updateStatus(data) {
            const indicator = document.getElementById('statusIndicator');
            const text = document.getElementById('statusText');
            const lastCheck = document.getElementById('lastCheck');
            
            if (data.is_remote_session) {
                indicator.className = 'status-indicator status-connected';
                indicator.innerHTML = '🔴';
                text.textContent = '远程桌面已连接';
            } else {
                indicator.className = 'status-indicator status-disconnected';
                indicator.innerHTML = '🟢';
                text.textContent = '本地使用';
            }
            
            if (data.last_check_time) {
                const time = new Date(data.last_check_time);
                lastCheck.textContent = `最后检查: ${time.toLocaleString()}`;
            }
        }
        
        function updateHistory(data) {
            const historyList = document.getElementById('historyList');
            if (data.connection_history && data.connection_history.length > 0) {
                historyList.innerHTML = data.connection_history.map(item => `
                    <div class="history-item">
                        <div>${item.message}</div>
                        <div class="history-time">${new Date(item.timestamp).toLocaleString()}</div>
                    </div>
                `).join('');
            } else {
                historyList.innerHTML = '<div class="history-item">暂无历史记录</div>';
            }
        }
        
        async function checkStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                updateStatus(data);
                updateHistory(data);
            } catch (error) {
                console.error('获取状态失败:', error);
                document.getElementById('statusText').textContent = '获取状态失败';
            }
        }
        
        // 页面加载时检查状态
        checkStatus();
        
        // 每10秒自动刷新
        setInterval(checkStatus, 10000);
    </script>
</body>
</html>'''
    
    # 写入HTML模板文件
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(html_template)
    
    # 启动后台监控线程
    monitor_thread = threading.Thread(target=background_monitor, daemon=True)
    monitor_thread.start()
    
    print("🚀 远程桌面状态监控服务启动中...")
    print("📱 访问 http://localhost:51472 查看状态")
    print("🔧 API端点:")
    print("   - GET /api/status - 获取当前状态")
    print("   - GET /api/history - 获取连接历史")
    print("   - GET /api/force_check - 强制检查状态")
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=51472, debug=True)
