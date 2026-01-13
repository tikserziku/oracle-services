#!/usr/bin/env python3
"""
Oracle Admin API v2.0 - Full Service & Code Management
For MCP-Hub - create, edit, delete, run, diagnose
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import sys
import traceback

app = Flask(__name__)
CORS(app)

# Security: allowed directories for file operations
ALLOWED_PATHS = ['/home/ubuntu', '/var/www', '/tmp', '/opt', '/etc/systemd/system']
GROK_VOICE_DIR = '/home/ubuntu/grok-voice'

def is_path_allowed(path):
    """Check if path is within allowed directories"""
    abs_path = os.path.abspath(path)
    return any(abs_path.startswith(allowed) for allowed in ALLOWED_PATHS)

def run_cmd(cmd, timeout=30):
    """Run shell command and return result"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=timeout
        )
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'code': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'Command timeout'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============ FILE OPERATIONS ============

@app.route('/files/list', methods=['POST'])
def list_files():
    """List files in directory"""
    data = request.get_json() or {}
    path = data.get('path', '/home/ubuntu')

    if not is_path_allowed(path):
        return jsonify({'error': 'Path not allowed', 'allowed': ALLOWED_PATHS}), 403

    if not os.path.exists(path):
        return jsonify({'error': 'Path not found'}), 404

    try:
        items = []
        for item in os.listdir(path):
            full_path = os.path.join(path, item)
            is_dir = os.path.isdir(full_path)
            size = 0 if is_dir else os.path.getsize(full_path)
            items.append({
                'name': item,
                'type': 'directory' if is_dir else 'file',
                'size': size
            })
        return jsonify({'path': path, 'items': items, 'count': len(items)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/files/read', methods=['POST'])
def read_file():
    """Read file content"""
    data = request.get_json() or {}
    path = data.get('path')

    if not path:
        return jsonify({'error': 'Path required'}), 400

    if not is_path_allowed(path):
        return jsonify({'error': 'Path not allowed'}), 403

    if not os.path.exists(path):
        return jsonify({'error': 'File not found'}), 404

    if os.path.isdir(path):
        return jsonify({'error': 'Path is a directory'}), 400

    try:
        if os.path.getsize(path) > 1024 * 1024:
            return jsonify({'error': 'File too large (max 1MB)'}), 400

        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return jsonify({'path': path, 'content': content, 'size': len(content)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/files/write', methods=['POST'])
def write_file():
    """Write content to file"""
    data = request.get_json() or {}
    path = data.get('path')
    content = data.get('content', '')

    if not path:
        return jsonify({'error': 'Path required'}), 400

    if not is_path_allowed(path):
        return jsonify({'error': 'Path not allowed'}), 403

    try:
        dir_path = os.path.dirname(path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'path': path, 'size': len(content)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/files/delete', methods=['POST'])
def delete_file():
    """Delete a file"""
    data = request.get_json() or {}
    path = data.get('path')

    if not path:
        return jsonify({'error': 'Path required'}), 400

    if not is_path_allowed(path):
        return jsonify({'error': 'Path not allowed'}), 403

    if not os.path.exists(path):
        return jsonify({'error': 'File not found'}), 404

    try:
        if os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
        else:
            os.remove(path)
        return jsonify({'success': True, 'deleted': path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ SERVICE OPERATIONS ============

@app.route('/services/list', methods=['GET'])
def list_services():
    """List all grok-* services"""
    try:
        result = run_cmd('systemctl list-units --type=service --all "grok-*"')
        services = []
        for line in result['stdout'].split('\n'):
            if 'grok-' in line and '.service' in line:
                parts = line.split()
                if len(parts) >= 4:
                    services.append({
                        'name': parts[0].replace('.service', ''),
                        'load': parts[1],
                        'active': parts[2],
                        'sub': parts[3]
                    })
        return jsonify({'services': services, 'count': len(services)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/services/status', methods=['POST'])
def service_status():
    """Get detailed service status"""
    data = request.get_json() or {}
    service = data.get('service')

    if not service:
        return jsonify({'error': 'Service name required'}), 400

    if not service.startswith('grok-'):
        return jsonify({'error': 'Only grok-* services allowed'}), 403

    result = run_cmd(f'systemctl status {service}')
    return jsonify({
        'service': service,
        'status': result['stdout'],
        'active': 'active (running)' in result['stdout']
    })

@app.route('/services/logs', methods=['POST'])
def service_logs():
    """Get service logs"""
    data = request.get_json() or {}
    service = data.get('service')
    lines = data.get('lines', 50)

    if not service:
        return jsonify({'error': 'Service name required'}), 400

    if not service.startswith('grok-'):
        return jsonify({'error': 'Only grok-* services allowed'}), 403

    result = run_cmd(f'journalctl -u {service} -n {lines} --no-pager')
    return jsonify({
        'service': service,
        'logs': result['stdout'],
        'lines': lines
    })

@app.route('/services/restart', methods=['POST'])
def restart_service():
    """Restart a service"""
    data = request.get_json() or {}
    service = data.get('service')

    if not service:
        return jsonify({'error': 'Service name required'}), 400

    if not service.startswith('grok-'):
        return jsonify({'error': 'Only grok-* services allowed'}), 403

    result = run_cmd(f'sudo systemctl restart {service}')
    if result['success']:
        return jsonify({'success': True, 'service': service, 'message': 'Service restarted'})
    else:
        return jsonify({'error': result['stderr'] or 'Restart failed'}), 500

@app.route('/services/stop', methods=['POST'])
def stop_service():
    """Stop a service"""
    data = request.get_json() or {}
    service = data.get('service')

    if not service:
        return jsonify({'error': 'Service name required'}), 400

    if not service.startswith('grok-'):
        return jsonify({'error': 'Only grok-* services allowed'}), 403

    result = run_cmd(f'sudo systemctl stop {service}')
    return jsonify({'success': result['success'], 'service': service})

@app.route('/services/start', methods=['POST'])
def start_service():
    """Start a service"""
    data = request.get_json() or {}
    service = data.get('service')

    if not service:
        return jsonify({'error': 'Service name required'}), 400

    if not service.startswith('grok-'):
        return jsonify({'error': 'Only grok-* services allowed'}), 403

    result = run_cmd(f'sudo systemctl start {service}')
    return jsonify({'success': result['success'], 'service': service})

@app.route('/services/create', methods=['POST'])
def create_service():
    """Create a new systemd service from Python file"""
    data = request.get_json() or {}
    name = data.get('name')  # e.g., "my-bot"
    python_code = data.get('code')
    port = data.get('port')
    description = data.get('description', f'Service {name}')
    env_vars = data.get('env', {})

    if not name or not python_code:
        return jsonify({'error': 'Name and code required'}), 400

    if not name.startswith('grok-'):
        name = f'grok-{name}'

    try:
        # 1. Save Python file
        py_file = f'{GROK_VOICE_DIR}/{name}.py'
        with open(py_file, 'w', encoding='utf-8') as f:
            f.write(python_code)

        # 2. Create service file
        env_lines = '\n'.join([f'Environment={k}={v}' for k, v in env_vars.items()])

        service_content = f'''[Unit]
Description={description}
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory={GROK_VOICE_DIR}
Environment=PYTHONUNBUFFERED=1
{env_lines}
ExecStart=/usr/bin/python3 {py_file}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
'''

        service_file = f'/etc/systemd/system/{name}.service'

        # Write service file via sudo
        tmp_service = f'/tmp/{name}.service'
        with open(tmp_service, 'w') as f:
            f.write(service_content)

        run_cmd(f'sudo mv {tmp_service} {service_file}')
        run_cmd('sudo systemctl daemon-reload')
        run_cmd(f'sudo systemctl enable {name}')
        run_cmd(f'sudo systemctl start {name}')

        # Check if started
        status = run_cmd(f'systemctl is-active {name}')
        is_active = status['stdout'].strip() == 'active'

        return jsonify({
            'success': True,
            'service': name,
            'python_file': py_file,
            'service_file': service_file,
            'active': is_active,
            'port': port
        })

    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/services/delete', methods=['POST'])
def delete_service():
    """Delete a service completely"""
    data = request.get_json() or {}
    service = data.get('service')
    delete_files = data.get('delete_files', True)

    if not service:
        return jsonify({'error': 'Service name required'}), 400

    if not service.startswith('grok-'):
        return jsonify({'error': 'Only grok-* services allowed'}), 403

    try:
        # Stop and disable
        run_cmd(f'sudo systemctl stop {service}')
        run_cmd(f'sudo systemctl disable {service}')

        # Remove service file
        service_file = f'/etc/systemd/system/{service}.service'
        if os.path.exists(service_file):
            run_cmd(f'sudo rm {service_file}')

        # Remove Python file if requested
        py_file = f'{GROK_VOICE_DIR}/{service}.py'
        if delete_files and os.path.exists(py_file):
            os.remove(py_file)

        run_cmd('sudo systemctl daemon-reload')

        return jsonify({
            'success': True,
            'deleted': service,
            'files_deleted': delete_files
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/services/edit', methods=['POST'])
def edit_service():
    """Edit service Python code"""
    data = request.get_json() or {}
    service = data.get('service')
    new_code = data.get('code')
    restart = data.get('restart', True)

    if not service or not new_code:
        return jsonify({'error': 'Service and code required'}), 400

    if not service.startswith('grok-'):
        return jsonify({'error': 'Only grok-* services allowed'}), 403

    try:
        py_file = f'{GROK_VOICE_DIR}/{service}.py'

        # Backup old file
        if os.path.exists(py_file):
            backup = f'{py_file}.backup'
            run_cmd(f'cp {py_file} {backup}')

        # Write new code
        with open(py_file, 'w', encoding='utf-8') as f:
            f.write(new_code)

        # Restart if requested
        if restart:
            run_cmd(f'sudo systemctl restart {service}')

        status = run_cmd(f'systemctl is-active {service}')
        is_active = status['stdout'].strip() == 'active'

        return jsonify({
            'success': True,
            'service': service,
            'file': py_file,
            'restarted': restart,
            'active': is_active
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ CODE EXECUTION ============

@app.route('/code/run', methods=['POST'])
def run_code():
    """Run Python code and return output"""
    data = request.get_json() or {}
    code = data.get('code')
    timeout = min(data.get('timeout', 30), 60)  # Max 60 seconds

    if not code:
        return jsonify({'error': 'Code required'}), 400

    try:
        # Save to temp file
        tmp_file = '/tmp/mcp_run_code.py'
        with open(tmp_file, 'w', encoding='utf-8') as f:
            f.write(code)

        # Run with timeout
        result = run_cmd(f'cd {GROK_VOICE_DIR} && python3 {tmp_file}', timeout=timeout)

        os.remove(tmp_file)

        return jsonify({
            'success': result['success'],
            'output': result['stdout'],
            'error': result['stderr'],
            'code': result['code']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/code/check', methods=['POST'])
def check_code():
    """Check Python code for syntax errors"""
    data = request.get_json() or {}
    code = data.get('code')

    if not code:
        return jsonify({'error': 'Code required'}), 400

    try:
        # Save to temp file
        tmp_file = '/tmp/mcp_check_code.py'
        with open(tmp_file, 'w', encoding='utf-8') as f:
            f.write(code)

        # Check syntax
        result = run_cmd(f'python3 -m py_compile {tmp_file}')

        os.remove(tmp_file)

        if result['success']:
            return jsonify({'valid': True, 'message': 'Syntax OK'})
        else:
            return jsonify({'valid': False, 'error': result['stderr']})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ ERROR DIAGNOSTICS ============

@app.route('/diagnose/service', methods=['POST'])
def diagnose_service():
    """Full diagnostic for a service"""
    data = request.get_json() or {}
    service = data.get('service')

    if not service:
        return jsonify({'error': 'Service name required'}), 400

    if not service.startswith('grok-'):
        return jsonify({'error': 'Only grok-* services allowed'}), 403

    try:
        diagnosis = {
            'service': service,
            'checks': []
        }

        # 1. Check if service exists
        service_file = f'/etc/systemd/system/{service}.service'
        diagnosis['service_file_exists'] = os.path.exists(service_file)

        # 2. Check Python file
        py_file = f'{GROK_VOICE_DIR}/{service}.py'
        diagnosis['python_file_exists'] = os.path.exists(py_file)

        # 3. Service status
        status = run_cmd(f'systemctl status {service}')
        diagnosis['status'] = status['stdout']
        diagnosis['is_active'] = 'active (running)' in status['stdout']
        diagnosis['is_failed'] = 'failed' in status['stdout'].lower()

        # 4. Recent errors from journal
        errors = run_cmd(f'journalctl -u {service} -p err -n 20 --no-pager')
        diagnosis['recent_errors'] = errors['stdout']

        # 5. Last 30 log lines
        logs = run_cmd(f'journalctl -u {service} -n 30 --no-pager')
        diagnosis['recent_logs'] = logs['stdout']

        # 6. Check Python syntax if file exists
        if diagnosis['python_file_exists']:
            syntax = run_cmd(f'python3 -m py_compile {py_file}')
            diagnosis['syntax_valid'] = syntax['success']
            if not syntax['success']:
                diagnosis['syntax_error'] = syntax['stderr']

        # 7. Check port if in service file
        if diagnosis['service_file_exists']:
            with open(service_file, 'r') as f:
                service_content = f.read()
            diagnosis['service_config'] = service_content

        # Summary
        issues = []
        if not diagnosis['service_file_exists']:
            issues.append('Service file not found')
        if not diagnosis['python_file_exists']:
            issues.append('Python file not found')
        if diagnosis['is_failed']:
            issues.append('Service is in failed state')
        if diagnosis.get('python_file_exists') and not diagnosis.get('syntax_valid', True):
            issues.append('Python syntax error')

        diagnosis['issues'] = issues
        diagnosis['healthy'] = len(issues) == 0 and diagnosis['is_active']

        return jsonify(diagnosis)

    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/diagnose/all', methods=['GET'])
def diagnose_all():
    """Quick health check of all services"""
    try:
        result = run_cmd('systemctl list-units --type=service --all "grok-*" --no-pager')

        services = []
        for line in result['stdout'].split('\n'):
            if 'grok-' in line and '.service' in line:
                parts = line.split()
                if len(parts) >= 4:
                    name = parts[0].replace('.service', '')
                    active = parts[2]
                    sub = parts[3]

                    services.append({
                        'name': name,
                        'active': active,
                        'sub': sub,
                        'healthy': active == 'active' and sub == 'running'
                    })

        healthy_count = sum(1 for s in services if s['healthy'])

        return jsonify({
            'services': services,
            'total': len(services),
            'healthy': healthy_count,
            'unhealthy': len(services) - healthy_count
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ SERVICE INFO ============

@app.route('/services/info', methods=['POST'])
def service_info():
    """Get detailed service info including Python file path"""
    data = request.get_json() or {}
    service = data.get('service')

    if not service:
        return jsonify({'error': 'Service name required'}), 400

    if not service.startswith('grok-'):
        service = f'grok-{service}'

    try:
        info = {'service': service}

        # Read service file
        service_file = f'/etc/systemd/system/{service}.service'
        if os.path.exists(service_file):
            with open(service_file, 'r') as f:
                content = f.read()
            info['service_file'] = content

            # Extract Python file from ExecStart
            for line in content.split('\n'):
                if 'ExecStart' in line:
                    # Parse: ExecStart=/usr/bin/python3 /path/to/file.py
                    parts = line.split()
                    for part in parts:
                        if part.endswith('.py'):
                            info['python_file'] = part
                            info['python_filename'] = os.path.basename(part)
                            break
                if 'Description=' in line:
                    info['description'] = line.split('=', 1)[1].strip()

            # Extract port if present
            import re
            port_match = re.search(r'--port[=\s](\d+)', content)
            if port_match:
                info['port'] = int(port_match.group(1))
        else:
            info['error'] = 'Service file not found'

        # Check if active
        status = run_cmd(f'systemctl is-active {service}')
        info['active'] = status['stdout'].strip() == 'active'

        return jsonify(info)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/services/mapping', methods=['GET'])
def services_mapping():
    """Get mapping of all services to their Python files"""
    try:
        mapping = []

        # List all grok-* service files
        service_dir = '/etc/systemd/system'
        for filename in os.listdir(service_dir):
            if filename.startswith('grok-') and filename.endswith('.service'):
                service_name = filename.replace('.service', '')
                service_path = os.path.join(service_dir, filename)

                with open(service_path, 'r') as f:
                    content = f.read()

                entry = {'service': service_name, 'service_file': service_path}

                # Extract Python file
                for line in content.split('\n'):
                    if 'ExecStart' in line:
                        parts = line.split()
                        for part in parts:
                            if part.endswith('.py'):
                                entry['python_file'] = part
                                entry['python_filename'] = os.path.basename(part)
                                break
                    if 'Description=' in line:
                        entry['description'] = line.split('=', 1)[1].strip()

                # Check if active
                status = run_cmd(f'systemctl is-active {service_name}')
                entry['active'] = status['stdout'].strip() == 'active'

                mapping.append(entry)

        return jsonify({'services': mapping, 'count': len(mapping)})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ DEPLOY OPERATIONS ============

@app.route('/deploy/html', methods=['POST'])
def deploy_html():
    """Deploy HTML file to web directory"""
    data = request.get_json() or {}
    filename = data.get('filename')
    content = data.get('content')
    subdomain = data.get('subdomain', '')

    if not filename or not content:
        return jsonify({'error': 'Filename and content required'}), 400

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ['.html', '.css', '.js', '.json', '.txt', '.svg', '.ico']:
        return jsonify({'error': 'Only web files allowed'}), 403

    try:
        if subdomain:
            deploy_path = f'/var/www/{subdomain}/{filename}'
            os.makedirs(f'/var/www/{subdomain}', exist_ok=True)
        else:
            deploy_path = f'/var/www/html/{filename}'

        with open(deploy_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return jsonify({
            'success': True,
            'path': deploy_path,
            'url': f'http://158.180.56.74/{filename}' if not subdomain else f'http://158.180.56.74/{subdomain}/{filename}'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ HEALTH CHECK ============

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'name': 'Oracle Admin API',
        'version': '2.0',
        'features': ['files', 'services', 'deploy', 'code', 'diagnose']
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
