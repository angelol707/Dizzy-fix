const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let pythonProcess = null;

function startPythonServer() {
    const isWin = process.platform === 'win32';
    const python = isWin ? 'python' : 'python3';

    pythonProcess = spawn(python, ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000'], {
        cwd: __dirname,
        stdio: 'pipe',
        // Sur Windows, évite d'ouvrir une console noire
        windowsHide: true
    });

    pythonProcess.stdout.on('data', (d) => console.log('[Python]', d.toString().trim()));
    pythonProcess.stderr.on('data', (d) => console.log('[Python]', d.toString().trim()));
    pythonProcess.on('close', (code) => console.log('[Python] Serveur arrêté, code:', code));
}

function waitForServer(retries, callback) {
    http.get('http://127.0.0.1:8000/', (res) => {
        callback(true);
    }).on('error', () => {
        if (retries <= 0) return callback(false);
        setTimeout(() => waitForServer(retries - 1, callback), 500);
    });
}

function createMainWindow() {
    const mainWindow = new BrowserWindow({
        width: 900,
        height: 600,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            devTools: true
        },
        autoHideMenuBar: true
    });

    mainWindow.loadFile('login.html');
}

app.whenReady().then(() => {
    startPythonServer();

    // Attendre que le serveur Python soit prêt (max 15 secondes)
    waitForServer(30, (ready) => {
        if (!ready) console.warn('[Electron] Serveur Python non disponible — vérifie que les dépendances Python sont installées.');
        createMainWindow();
    });

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
    });
});

app.on('window-all-closed', () => {
    if (pythonProcess) {
        pythonProcess.kill();
        pythonProcess = null;
    }
    if (process.platform !== 'darwin') app.quit();
});
