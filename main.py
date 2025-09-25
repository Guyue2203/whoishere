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
        
    def get_remote_desktop_users(self):
        """获取远程桌面连接用户信息"""
        try:
            users = []
            
            # 方法1: 使用query session命令
            try:
                result = subprocess.run(
                    ['query', 'session'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[2:]:  # 跳过标题行
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 4:
                                session_name = parts[0]
                                username = parts[1]
                                session_id = parts[2]
                                session_state = parts[3]
                                
                                # 检查是否是远程桌面会话
                                if session_name.startswith('rdp-tcp') or session_name.startswith('RDP-'):
                                    users.append({
                                        'username': username,
                                        'session_name': session_name,
                                        'session_id': session_id,
                                        'state': session_state,
                                        'connection_type': 'RDP'
                                    })
            except Exception as e:
                print(f"查询会话信息时出错: {e}")
            
            # 方法2: 使用qwinsta命令 (更详细的信息)
            try:
                result = subprocess.run(
                    ['qwinsta'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:  # 跳过标题行
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 5:
                                session_name = parts[0]
                                username = parts[1]
                                session_id = parts[2]
                                session_state = parts[3]
                                session_type = parts[4] if len(parts) > 4 else 'Unknown'
                                
                                # 检查是否是远程桌面会话
                                if session_name.startswith('rdp-tcp') or session_name.startswith('RDP-'):
                                    # 检查是否已存在该用户
                                    existing_user = next((u for u in users if u['username'] == username), None)
                                    if not existing_user:
                                        users.append({
                                            'username': username,
                                            'session_name': session_name,
                                            'session_id': session_id,
                                            'state': session_state,
                                            'type': session_type,
                                            'connection_type': 'RDP'
                                        })
            except Exception as e:
                print(f"查询详细会话信息时出错: {e}")
            
            # 方法3: 检查当前用户环境变量
            current_user = os.environ.get('USERNAME', 'Unknown')
            session_name = os.environ.get('SESSIONNAME', '')
            if session_name.startswith('RDP-'):
                # 检查是否已存在该用户
                existing_user = next((u for u in users if u['username'] == current_user), None)
                if not existing_user:
                    users.append({
                        'username': current_user,
                        'session_name': session_name,
                        'session_id': 'Current',
                        'state': 'Active',
                        'connection_type': 'RDP'
                    })
            
            return users
            
        except Exception as e:
            print(f"获取远程桌面用户信息时出错: {e}")
            return []

    def check_remote_desktop_status(self):
        """检测是否通过远程桌面连接 - 更严格的检测"""
        try:
            # 方法1: 检查环境变量 (最可靠的方法)
            session_name = os.environ.get('SESSIONNAME', '')
            if session_name.startswith('RDP-'):
                return True
            
            # 方法2: 检查当前会话是否通过RDP连接
            try:
                result = subprocess.run(
                    ['query', 'session', os.environ.get('USERNAME', '')],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    # 检查输出中是否包含RDP会话
                    if 'rdp-tcp' in result.stdout.lower() or 'RDP-' in result.stdout:
                        return True
            except:
                pass
            
            # 方法3: 检查活动RDP会话
            try:
                result = subprocess.run(
                    ['query', 'session'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[2:]:  # 跳过标题行
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 4:
                                session_name = parts[0]
                                username = parts[1]
                                session_state = parts[3]
                                
                                # 检查是否是活动的RDP会话
                                if (session_name.startswith('rdp-tcp') or session_name.startswith('RDP-')) and session_state.lower() == 'active':
                                    return True
            except:
                pass
            
            # 方法4: 检查RDP进程 (作为辅助检测)
            rdp_processes = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'rdp' in proc.info['name'].lower():
                        rdp_processes += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # 如果有很多RDP进程，可能是通过RDP连接
            if rdp_processes > 2:
                return True
                
            return False
            
        except Exception as e:
            print(f"检测远程桌面状态时出错: {e}")
            return False
    
    def update_status(self):
        """更新连接状态 - 带确认机制"""
        current_status = self.check_remote_desktop_status()
        current_time = datetime.now()
        
        # 如果状态发生变化，进行二次确认
        if current_status != self.is_remote_session:
            # 等待1秒后再次检查，避免误判
            time.sleep(1)
            confirmed_status = self.check_remote_desktop_status()
            
            # 只有确认状态一致才更新
            if confirmed_status == current_status:
                self.connection_history.append({
                    'timestamp': current_time.isoformat(),
                    'status': 'connected' if current_status else 'disconnected',
                    'message': '远程桌面已连接' if current_status else '远程桌面已断开'
                })
                
                # 只保留最近50条记录
                if len(self.connection_history) > 50:
                    self.connection_history = self.connection_history[-50:]
                
                self.is_remote_session = current_status
                print(f"状态已更新: {'远程桌面已连接' if current_status else '远程桌面已断开'}")
            else:
                print(f"状态变化未确认，保持原状态: {'远程桌面已连接' if self.is_remote_session else '本地使用'}")
        
        self.last_check_time = current_time
    
    def get_status_info(self):
        """获取状态信息"""
        remote_users = self.get_remote_desktop_users()
        return {
            'is_remote_session': self.is_remote_session,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'status_text': '远程桌面已连接' if self.is_remote_session else '本地使用',
            'connection_history': self.connection_history[-10:],  # 最近10条记录
            'remote_users': remote_users,
            'user_count': len(remote_users)
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
    # 强制重新检测，跳过确认机制
    current_status = detector.check_remote_desktop_status()
    current_time = datetime.now()
    
    # 直接更新状态，不进行二次确认
    if current_status != detector.is_remote_session:
        detector.connection_history.append({
            'timestamp': current_time.isoformat(),
            'status': 'connected' if current_status else 'disconnected',
            'message': '远程桌面已连接' if current_status else '远程桌面已断开'
        })
        
        # 只保留最近50条记录
        if len(detector.connection_history) > 50:
            detector.connection_history = detector.connection_history[-50:]
        
        detector.is_remote_session = current_status
        detector.last_check_time = current_time
        print(f"强制更新状态: {'远程桌面已连接' if current_status else '远程桌面已断开'}")
    
    return jsonify({
        'message': '状态已强制更新',
        'status': detector.get_status_info()
    })

@app.route('/api/users')
def api_users():
    """API - 获取远程桌面连接用户"""
    users = detector.get_remote_desktop_users()
    return jsonify({
        'users': users,
        'count': len(users),
        'timestamp': datetime.now().isoformat()
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
        .users-section {
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 5px;
        }
        .user-item {
            padding: 15px;
            margin: 10px 0;
            background: white;
            border-radius: 8px;
            border-left: 4px solid #e74c3c;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .user-name {
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
        }
        .user-details {
            font-size: 14px;
            color: #7f8c8d;
            line-height: 1.4;
        }
        .user-state {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
            margin-top: 5px;
        }
        .state-active {
            background: #d4edda;
            color: #155724;
        }
        .state-disconnected {
            background: #f8d7da;
            color: #721c24;
        }
        .no-users {
            text-align: center;
            color: #7f8c8d;
            font-style: italic;
            padding: 20px;
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
            <button class="refresh-btn" onclick="forceCheck()" style="background: #e74c3c;">⚡ 强制检查</button>
        </div>
        
        <div class="users-section">
            <h3>👥 当前远程桌面用户</h3>
            <div id="usersList">加载中...</div>
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
        
        function updateUsers(data) {
            const usersList = document.getElementById('usersList');
            if (data.remote_users && data.remote_users.length > 0) {
                usersList.innerHTML = data.remote_users.map(user => `
                    <div class="user-item">
                        <div class="user-name">👤 ${user.username}</div>
                        <div class="user-details">
                            <div>会话名称: ${user.session_name}</div>
                            <div>会话ID: ${user.session_id}</div>
                            <div>连接类型: ${user.connection_type}</div>
                            ${user.type ? `<div>会话类型: ${user.type}</div>` : ''}
                        </div>
                        <span class="user-state ${user.state.toLowerCase() === 'active' ? 'state-active' : 'state-disconnected'}">
                            ${user.state}
                        </span>
                    </div>
                `).join('');
            } else {
                usersList.innerHTML = '<div class="no-users">当前没有远程桌面用户连接</div>';
            }
        }
        
        async function checkStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                updateStatus(data);
                updateHistory(data);
                updateUsers(data);
            } catch (error) {
                console.error('获取状态失败:', error);
                document.getElementById('statusText').textContent = '获取状态失败';
            }
        }
        
        async function forceCheck() {
            try {
                document.getElementById('statusText').textContent = '强制检查中...';
                const response = await fetch('/api/force_check');
                const data = await response.json();
                updateStatus(data.status);
                updateHistory(data.status);
                updateUsers(data.status);
                console.log('强制检查完成:', data.message);
            } catch (error) {
                console.error('强制检查失败:', error);
                document.getElementById('statusText').textContent = '强制检查失败';
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
    print("   - GET /api/users - 获取远程桌面用户")
    print("   - GET /api/force_check - 强制检查状态")
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=51472, debug=True)
