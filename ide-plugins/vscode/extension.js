const vscode = require('vscode');
const https = require('http');

function activate(context) {
    console.log('CodeDNA extension activated');
    
    const config = vscode.workspace.getConfiguration('codedna');
    const daemonUrl = config.get('daemonUrl', 'http://127.0.0.1:7842');
    
    const statusItem = vscode.window.createStatusBarItem('codedna.status', vscode.StatusBarAlignment.Right, 100);
    statusItem.text = '$(flame) CodeDNA';
    statusItem.tooltip = 'CodeDNA: Click for status';
    statusItem.command = 'codedna.showStatus';
    statusItem.show();
    
    updateDaemonStatus(statusItem);
    // Update status periodically
    const statusInterval = setInterval(() => updateDaemonStatus(statusItem), 30000);
    context.subscriptions.push({ dispose: () => clearInterval(statusInterval) });
    
    const commands = [
        vscode.commands.registerCommand('codedna.scanFile', scanCurrentFile),
        vscode.commands.registerCommand('codedna.showStatus', showStatus),
        vscode.commands.registerCommand('codedna.openDashboard', openDashboard),
    ];
    
    context.subscriptions.push(...commands, statusItem);
    
    if (config.get('autoScanOnSave', true)) {
        const fileWatcher = vscode.workspace.createFileSystemWatcher('**/*.py');
        fileWatcher.onDidSave(async (uri) => {
            if (uri.fsPath.endsWith('.py')) {
                await scanFileFromPath(uri.fsPath, statusItem);
            }
        });
        context.subscriptions.push(fileWatcher);
    }
}

async function updateDaemonStatus(statusItem) {
    try {
        const response = await makeRequest('/health', 'GET');
        if (response.statusCode === 200) {
            statusItem.text = '$(flame) CodeDNA: Online';
            statusItem.backgroundColor = undefined;
        }
    } catch (error) {
        statusItem.text = '$(flame) CodeDNA: Offline';
        statusItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
    }
}

function getDaemonUrl() {
    const config = vscode.workspace.getConfiguration('codedna');
    return config.get('daemonUrl', 'http://127.0.0.1:7842');
}

function makeRequest(path, method, body = null) {
    return new Promise((resolve, reject) => {
        const baseUrl = getDaemonUrl();
        const url = new URL(path, baseUrl);
        const options = { 
            hostname: url.hostname, 
            port: url.port || 7842, 
            path: url.pathname, 
            method: method, 
            headers: { 
                'Content-Type': 'application/json',
                'X-CodeDNA-Client': 'vscode-extension'
            } 
        };
        
        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => { 
                try {
                    resolve({ statusCode: res.statusCode, data: JSON.parse(data) });
                } catch (e) {
                    resolve({ statusCode: res.statusCode, data: data });
                }
            });
        });
        
        req.on('error', reject);
        req.setTimeout(5000, () => { req.destroy(); reject(new Error('Request timeout')); });
        if (body) { req.write(JSON.stringify(body)); }
        req.end();
    });
}

async function scanFileFromPath(filePath, statusItem) {
    try {
        const config = vscode.workspace.getConfiguration('codedna');
        const repoId = config.get('repoId');
        
        if (!repoId) {
            // No repo configured, skip scan
            return;
        }
        
        const response = await makeRequest('/api/v1/scan/file', 'POST', {
            repo_id: repoId,
            file_path: filePath,
            language: 'python'
        });
        
        if (response.statusCode === 200 && response.data.dna_score !== null) {
            const score = response.data.dna_score;
            
            // Show inline hint based on DNA score
            let hint;
            if (score >= 0.85) {
                hint = `✓ CodeDNA: ${(score * 100).toFixed(0)}% style match`;
            } else if (score >= 0.7) {
                hint = `⚠ CodeDNA: ${(score * 100).toFixed(0)}% style match (minor divergence)`;
            } else {
                hint = `⚠ CodeDNA: ${(score * 100).toFixed(0)}% style match (significant divergence)`;
            }
            
            statusItem.text = hint;
            statusItem.tooltip = response.data.explanation?.summary || `DNA Score: ${score}`;
            
        } else if (response.statusCode === 200 && response.data.degraded) {
            statusItem.text = '$(flame) CodeDNA: No baseline';
        }
        
    } catch (error) {
        console.error('Scan failed:', error);
    }
}

async function scanCurrentFile() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) { 
        vscode.window.showInformationMessage('No active editor'); 
        return; 
    }
    
    const filePath = editor.document.uri.fsPath;
    const statusItem = vscode.window.createStatusBarItem('codedna.scan', vscode.StatusBarAlignment.Right, 200);
    statusItem.text = '$(sync~spin) Scanning...';
    statusItem.show();
    
    await scanFileFromPath(filePath, statusItem);
    
    // Update status after a delay
    setTimeout(() => {
        const config = vscode.workspace.getConfiguration('codedna');
        const repoId = config.get('repoId');
        if (repoId) {
            updateDaemonStatus(statusItem);
        }
    }, 2000);
}

async function showStatus() {
    try {
        const response = await makeRequest('/api/v1/status', 'GET');
        if (response.statusCode === 200) {
            const data = response.data;
            let message = `CodeDNA: Running on ${getDaemonUrl()}\n`;
            message += `Schema: ${data.db_version}/${data.expected_schema_version}\n`;
            message += `Active Repos: ${data.active_repos?.length || 0}`;
            
            if (data.interrupted_jobs?.length > 0) {
                message += `\n⚠ Interrupted jobs: ${data.interrupted_jobs.length}`;
            }
            
            vscode.window.showInformationMessage(message);
        }
    } catch (error) {
        vscode.window.showErrorMessage('CodeDNA daemon is not running. Start it with: codedna daemon start');
    }
}

async function openDashboard() {
    vscode.env.openExternal(vscode.Uri.parse(getDaemonUrl()));
}

function deactivate() { 
    console.log('CodeDNA extension deactivated'); 
}

module.exports = { activate, deactivate };