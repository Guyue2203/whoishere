import os
import time
import subprocess
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify
import psutil
import pystray
from PIL import Image, ImageDraw

app = Flask(__name__)

class RemoteDesktopDetector:
    def __init__(self):
        self.is_remote_session = False
        self.last_check_time = None
        
    def get_remote_desktop_users(self):
        """获取远程桌面连接用户信息 - 基于端口43389连接检测"""
        try:
            users = []
            
            # 方法1: 检查端口43389的ESTABLISHED连接
            try:
                result = subprocess.run(
                    ['netstat', '-an'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if '43389' in line and 'ESTABLISHED' in line:
                            # 解析连接信息
                            parts = line.split()
                            if len(parts) >= 4:
                                local_address = parts[1]
                                remote_address = parts[2]
                                state = parts[3]
                                
                                # 提取远程IP地址
                                if ':' in remote_address:
                                    remote_ip = remote_address.split(':')[0]
                                else:
                                    remote_ip = remote_address
                                
                                users.append({
                                    'username': f'Remote Connection from {remote_ip}',
                                    'session_name': 'RDP Connection',
                                    'session_id': 'Network',
                                    'state': 'Active',
                                    'connection_type': 'RDP',
                                    'remote_ip': remote_ip,
                                    'local_address': local_address,
                                    'remote_address': remote_address
                                })
            except Exception as e:
                print(f"检查网络连接时出错: {e}")
            
            # 方法2: 使用netstat -ano获取更详细的连接信息
            try:
                result = subprocess.run(
                    ['netstat', '-ano'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if '43389' in line and 'ESTABLISHED' in line:
                            parts = line.split()
                            if len(parts) >= 5:
                                local_address = parts[1]
                                remote_address = parts[2]
                                state = parts[3]
                                pid = parts[4]
                                
                                # 尝试获取进程信息
                                try:
                                    process = psutil.Process(int(pid))
                                    process_name = process.name()
                                except:
                                    process_name = 'Unknown'
                                
                                # 提取远程IP地址
                                if ':' in remote_address:
                                    remote_ip = remote_address.split(':')[0]
                                else:
                                    remote_ip = remote_address
                                
                                # 检查是否已存在该连接
                                existing_user = next((u for u in users if u.get('remote_ip') == remote_ip), None)
                                if not existing_user:
                                    users.append({
                                        'username': f'Remote Connection from {remote_ip}',
                                        'session_name': 'RDP Connection',
                                        'session_id': pid,
                                        'state': 'Active',
                                        'connection_type': 'RDP',
                                        'remote_ip': remote_ip,
                                        'local_address': local_address,
                                        'remote_address': remote_address,
                                        'process_name': process_name
                                    })
            except Exception as e:
                print(f"检查详细网络连接时出错: {e}")
            
            # 注意：不检测当前用户，因为当前用户一直登录着，没有意义
            
            return users
            
        except Exception as e:
            print(f"获取远程桌面用户信息时出错: {e}")
            return []

    def check_remote_desktop_status(self):
        """检测是否有远程桌面用户连接 - 检查所有用户的RDP连接"""
        try:
            # 获取所有远程桌面连接的用户
            remote_users = self.get_remote_desktop_users()
            
            # 如果有远程桌面用户连接，返回True
            if remote_users:
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
                self.is_remote_session = current_status
                print(f"状态已更新: {'有外部用户远程连接' if current_status else '没有外部用户远程连接'}")
            else:
                print(f"状态变化未确认，保持原状态: {'有外部用户远程连接' if self.is_remote_session else '没有外部用户远程连接'}")
        
        self.last_check_time = current_time
    
    def get_status_info(self):
        """获取状态信息"""
        remote_users = self.get_remote_desktop_users()
        return {
            'is_remote_session': self.is_remote_session,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'status_text': f'有 {len(remote_users)} 个外部用户通过远程桌面连接' if self.is_remote_session else '没有外部用户通过远程桌面连接',
            'remote_users': remote_users,
            'user_count': len(remote_users)
        }

# 创建检测器实例
detector = RemoteDesktopDetector()

# 全局变量
tray_icon = None

# 创建托盘图标
def create_icon():
    # 创建图标
    image = Image.new('RGB', (64, 64), color='blue')
    draw = ImageDraw.Draw(image)
    draw.ellipse([16, 16, 48, 48], fill='white', outline='black')
    draw.text((20, 20), "R", fill='black')
    return image

def update_tray_icon():
    """更新托盘图标状态"""
    if detector.is_remote_session:
        # 有连接时显示红色图标
        image = Image.new('RGB', (64, 64), color='red')
        draw = ImageDraw.Draw(image)
        draw.ellipse([16, 16, 48, 48], fill='white', outline='black')
        draw.text((20, 20), "R", fill='black')
    else:
        # 无连接时显示绿色图标
        image = Image.new('RGB', (64, 64), color='green')
        draw = ImageDraw.Draw(image)
        draw.ellipse([16, 16, 48, 48], fill='white', outline='black')
        draw.text((20, 20), "R", fill='black')
    
    return image

def show_status():
    """显示状态信息"""
    status = "有外部用户远程连接" if detector.is_remote_session else "没有外部用户远程连接"
    print(f"当前状态: {status}")

def open_web():
    """打开Web界面"""
    import webbrowser
    webbrowser.open('http://localhost:51472')

def quit_app():
    """退出应用"""
    global tray_icon
    print("正在退出服务...")
    if tray_icon:
        tray_icon.stop()
    os._exit(0)

# 创建托盘图标
tray_icon = pystray.Icon("WhoIsHere", create_icon(), "WhoIsHere - 远程桌面监控")
tray_icon.menu = pystray.Menu(
    pystray.MenuItem("状态", show_status),
    pystray.MenuItem("打开Web界面", open_web),
    pystray.MenuItem("退出", quit_app)
)

@app.route('/')
def index():
    """主页 - 显示状态页面"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """API - 获取当前状态"""
    detector.update_status()
    return jsonify(detector.get_status_info())


@app.route('/api/force_check')
def api_force_check():
    """API - 强制检查状态"""
    # 强制重新检测，跳过确认机制
    current_status = detector.check_remote_desktop_status()
    current_time = datetime.now()
    
    # 直接更新状态，不进行二次确认
    if current_status != detector.is_remote_session:
        detector.is_remote_session = current_status
        detector.last_check_time = current_time
        print(f"强制更新状态: {'有外部用户远程连接' if current_status else '没有外部用户远程连接'}")
    
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
            # 更新托盘图标
            if tray_icon:
                tray_icon.icon = update_tray_icon()
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
        
    </div>

    <script>
        function updateStatus(data) {
            const indicator = document.getElementById('statusIndicator');
            const text = document.getElementById('statusText');
            const lastCheck = document.getElementById('lastCheck');
            
            if (data.is_remote_session) {
                indicator.className = 'status-indicator status-connected';
                indicator.innerHTML = '🔴';
                text.textContent = data.status_text || '有用户通过远程桌面连接';
            } else {
                indicator.className = 'status-indicator status-disconnected';
                indicator.innerHTML = '🟢';
                text.textContent = data.status_text || '没有用户通过远程桌面连接';
            }
            
            if (data.last_check_time) {
                const time = new Date(data.last_check_time);
                lastCheck.textContent = `最后检查: ${time.toLocaleString()}`;
            }
        }
        
        
        function updateUsers(data) {
            const usersList = document.getElementById('usersList');
            if (data.remote_users && data.remote_users.length > 0) {
                usersList.innerHTML = data.remote_users.map(user => `
                    <div class="user-item">
                        <div class="user-name">🌐 ${user.username}</div>
                        <div class="user-details">
                            <div><strong>远程IP地址:</strong> ${user.remote_ip || 'Unknown'}</div>
                            <div><strong>连接状态:</strong> ${user.state}</div>
                            <div><strong>连接类型:</strong> ${user.connection_type}</div>
                            ${user.local_address ? `<div><strong>本地地址:</strong> ${user.local_address}</div>` : ''}
                            ${user.remote_address ? `<div><strong>远程地址:</strong> ${user.remote_address}</div>` : ''}
                            ${user.process_name ? `<div><strong>进程名称:</strong> ${user.process_name}</div>` : ''}
                            ${user.session_id ? `<div><strong>会话ID:</strong> ${user.session_id}</div>` : ''}
                        </div>
                        <span class="user-state ${user.state.toLowerCase() === 'active' ? 'state-active' : 'state-disconnected'}">
                            ${user.state}
                        </span>
                    </div>
                `).join('');
            } else {
                usersList.innerHTML = '<div class="no-users">当前没有用户通过远程桌面连接</div>';
            }
        }
        
        async function checkStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                updateStatus(data);
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
    
    # 启动Flask应用（在后台线程中）
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=51472, debug=False), daemon=True)
    flask_thread.start()
    
    print("🚀 远程桌面状态监控服务启动中...")
    print("📱 访问 http://localhost:51472 查看状态")
    print("💡 服务已最小化到系统托盘，右键图标可查看菜单")
    print("💡 关闭CMD窗口后服务会继续在托盘运行")
    
    # 启动托盘图标（这会阻塞主线程，保持程序运行）
    tray_icon.run()
