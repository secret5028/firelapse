"""Verify Shell properties and both icons on a private, invisible test window."""
import ctypes as C
from ctypes import wintypes as W
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))

@unittest.skipUnless(sys.platform=='win32','Windows Shell integration')
class TaskbarIdentity(unittest.TestCase):
    def test_owned_window_has_firelapse_identity_and_icons(self):
        from taskbar_identity import WindowIdentity,properties,APP_ID
        user=C.WinDLL('user32');create=user.CreateWindowExW
        create.argtypes=(W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,C.c_int,C.c_int,C.c_int,C.c_int,W.HWND,W.HMENU,W.HINSTANCE,C.c_void_p)
        create.restype=W.HWND
        hwnd=create(0,'STATIC','FireLapse unit fixture',0,0,0,1,1,None,None,None,None)
        self.assertTrue(hwnd)
        identity=WindowIdentity(Path(__file__).resolve().parents[3])
        try:
            identity.apply(hwnd)
            values=properties(hwnd)
            self.assertEqual(values[5],APP_ID)
            self.assertEqual(values[4],'FireLapse')
            self.assertTrue(values[3].endswith('FireLapse.ico,0'))
            self.assertIn('FireLapse.cmd',values[2])
            user.SendMessageW.argtypes=(W.HWND,W.UINT,W.WPARAM,W.LPARAM);user.SendMessageW.restype=W.LPARAM
            for kind in (0,1):self.assertTrue(user.SendMessageW(hwnd,0x7F,kind,0))
        finally:
            user.DestroyWindow.argtypes=(W.HWND,);user.DestroyWindow(hwnd);identity.close()

if __name__=='__main__':unittest.main()
