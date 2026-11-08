"""Brand only FireLapse's owned browser windows, using documented Shell properties.

https://learn.microsoft.com/windows/win32/properties/props-system-appusermodel-relaunchiconresource
"""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import subprocess
import uuid
import os

APP_ID='FireLapse.Desktop'

class GUID(C.Structure):
    _fields_=[('bytes',C.c_ubyte*16)]
    @classmethod
    def parse(cls,value):return cls((C.c_ubyte*16).from_buffer_copy(uuid.UUID(value).bytes_le))

class Key(C.Structure):
    _fields_=[('fmtid',GUID),('pid',W.DWORD)]

class VariantValue(C.Union):
    _fields_=[('text',C.c_wchar_p),('storage',C.c_ubyte*16)]

class Variant(C.Structure):
    _fields_=[('vt',W.WORD),('r1',W.WORD),('r2',W.WORD),('r3',W.WORD),('value',VariantValue)]

FMTID=GUID.parse('9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3')
IID=GUID.parse('886d8eeb-8cf2-4446-8d02-cdba1dbdcf99')

def properties(hwnd, values=None):
    """Set/read RelaunchCommand(2), Icon(3), Name(4), AppID(5)."""
    ole=C.OleDLL('ole32');shell=C.WinDLL('shell32')
    ole.CoInitializeEx.argtypes=(C.c_void_p,W.DWORD)
    initialized=False
    try:
        ole.CoInitializeEx(None,2);initialized=True
    except OSError:
        pass  # The launcher thread can already have another COM apartment.
    get=shell.SHGetPropertyStoreForWindow
    get.argtypes=(W.HWND,C.POINTER(GUID),C.POINTER(C.c_void_p));get.restype=C.c_long
    store=C.c_void_p()
    try:
        hr=get(hwnd,C.byref(IID),C.byref(store))
        if hr<0:raise OSError(f'SHGetPropertyStoreForWindow failed: {hr:#x}')
        table=C.cast(store,C.POINTER(C.POINTER(C.c_void_p))).contents
        method=lambda index,*args:C.WINFUNCTYPE(C.c_long,C.c_void_p,*args)(table[index])
        result={}
        for pid in (2,3,4,5):
            key=Key(FMTID,pid);value=Variant()
            if values is not None:
                value.vt=31;value.value.text=values[pid]  # VT_LPWSTR; SetValue copies it.
                hr=method(6,C.POINTER(Key),C.POINTER(Variant))(store,C.byref(key),C.byref(value))
            else:
                hr=method(5,C.POINTER(Key),C.POINTER(Variant))(store,C.byref(key),C.byref(value))
                if hr>=0:
                    result[pid]=value.value.text if value.vt==31 else None
                    ole.PropVariantClear(C.byref(value))
            if hr<0:raise OSError(f'IPropertyStore pid={pid} failed: {hr:#x}')
        if values is not None:
            hr=method(7)(store)
            if hr<0:raise OSError(f'IPropertyStore.Commit failed: {hr:#x}')
        return result
    finally:
        if store.value:C.WINFUNCTYPE(W.ULONG,C.c_void_p)(C.cast(store,C.POINTER(C.POINTER(C.c_void_p))).contents[2])(store)
        if initialized:ole.CoUninitialize()

class WindowIdentity:
    def __init__(self, install):
        self.install=Path(install).resolve();self.icon=self.install/'FireLapse.ico'
        self.handles=[];self.user=C.WinDLL('user32',use_last_error=True)
        load=self.user.LoadImageW
        load.argtypes=(W.HINSTANCE,W.LPCWSTR,W.UINT,C.c_int,C.c_int,W.UINT);load.restype=W.HANDLE
        for size in (16,32):
            h=load(None,str(self.icon),1,size,size,0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if not h:raise C.WinError(C.get_last_error())
            self.handles.append(h)
        self.user.SendMessageTimeoutW.argtypes=(W.HWND,W.UINT,W.WPARAM,W.LPARAM,W.UINT,W.UINT,C.POINTER(C.c_size_t))
        self.user.SendMessageTimeoutW.restype=W.LPARAM

    def apply(self, hwnd):
        # Shell's relaunch field has a bounded buffer. Use the short packaged
        # launcher rather than repeating the full installation path twice.
        command=subprocess.list2cmdline([os.environ.get('COMSPEC','cmd.exe'),'/c',str(self.install/'FireLapse.cmd')])
        properties(hwnd,{2:command,3:str(self.icon)+',0',4:'FireLapse',5:APP_ID})
        for kind,handle in enumerate(self.handles):
            result=C.c_size_t()
            if not self.user.SendMessageTimeoutW(hwnd,0x80,kind,handle,2,1000,C.byref(result)):
                raise C.WinError(C.get_last_error())

    def close(self):
        self.user.DestroyIcon.argtypes=(W.HICON,)
        for h in self.handles:self.user.DestroyIcon(h)
        self.handles=[]
