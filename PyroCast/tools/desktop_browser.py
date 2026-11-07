"""An owned Chromium window, with a profile separate from normal browsing."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import shutil
import subprocess


def executable():
    import winreg
    preferred = 'chrome'
    try:
        key = r'Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as current:
            if winreg.QueryValueEx(current, 'ProgId')[0].startswith('MSEdge'):
                preferred = 'msedge'
    except OSError:
        pass
    folders = {'chrome': 'Google/Chrome/Application', 'msedge': 'Microsoft/Edge/Application'}
    for name in (preferred, 'msedge' if preferred == 'chrome' else 'chrome'):
        binary = name+'.exe'
        for root in (os.getenv('ProgramFiles'), os.getenv('ProgramFiles(x86)'), os.getenv('LOCALAPPDATA')):
            if root:
                path = Path(root)/folders[name]/binary
                if path.is_file():
                    return path
        if path := shutil.which(binary):
            return Path(path)
    raise RuntimeError('FireLapse 전용 창을 열려면 Chrome 또는 Microsoft Edge가 필요합니다.')


def start(browser, profile, url):
    return subprocess.Popen([str(browser), '--user-data-dir='+str(profile), '--app='+url,
                             '--no-first-run', '--no-default-browser-check', '--disable-background-mode'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def windows(pid):
    user = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = (callback_type, wintypes.LPARAM)
    user.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user.IsWindowVisible.argtypes = (wintypes.HWND,)
    user.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    found = []

    @callback_type
    def collect(hwnd, _):
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user.IsWindowVisible(hwnd):
            name = ctypes.create_unicode_buffer(64)
            user.GetClassNameW(hwnd, name, len(name))
            if name.value.startswith('Chrome_WidgetWin_'):
                found.append(hwnd)
        return True

    user.EnumWindows(collect, 0)
    return found


def focus(handles):
    if handles:
        user = ctypes.WinDLL('user32')
        user.IsIconic.argtypes = (wintypes.HWND,)
        user.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
        user.SetForegroundWindow.argtypes = (wintypes.HWND,)
        if user.IsIconic(handles[0]):
            user.ShowWindow(handles[0], 9)  # SW_RESTORE
        user.SetForegroundWindow(handles[0])


def close(process):
    if process is None or process.poll() is not None:
        return
    user = ctypes.WinDLL('user32')
    user.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    for hwnd in windows(process.pid):
        user.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)
