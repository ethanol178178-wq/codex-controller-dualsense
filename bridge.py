"""Local Windows HID bridge for the DualSense VibeCoding Hub USB path.

The bridge reads DualSense USB input reports, injects configured keyboard
shortcuts through SendInput, and owns status-light output. Bluetooth DualSense
packets use different report layouts and are deliberately not handled here.
"""

from __future__ import annotations

import ctypes
import json
import math
import os
import secrets
import socket
import struct
import threading
import time
import uuid
from ctypes import wintypes
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from approval_detection import has_escalated_shell_request

HOST = "127.0.0.1"
PORT = 37845
APP_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_PORT = 4173
RELEASE_VERSION = "0.2.4"
ALLOWED_WEB_ORIGINS = {"http://127.0.0.1:4173", "http://localhost:4173"}
POST_PATHS = {
    "/api/lighting", "/api/mapping", "/api/codex-lighting",
    "/api/codex-hook", "/api/haptics", "/api/triggers", "/api/key-capture", "/api/action",
}
BRIDGE_TOKEN_PATH = os.environ.get("DS5VIBEHUB_TOKEN_PATH", "").strip() or os.path.join(
    os.environ.get("LOCALAPPDATA", APP_DIR), "DS5VibeHub", "bridge.token"
)
MAPPING_CONFIG_PATH = os.environ.get("DS5VIBEHUB_MAPPING_CONFIG", "").strip() or os.path.join(
    os.environ.get("LOCALAPPDATA", APP_DIR), "DS5VibeHub", "mapping.json"
)
BRIDGE_AUTH_TOKEN = ""
SONY_VENDOR_ID = 0x054C
DS5_USB_REPORT_ID = 0x02
DS5_USB_OUTPUT_LENGTH = 48  # Includes the report ID byte.
DS5_VALID_FLAG0_COMPATIBLE_VIBRATION = 0x01
DS5_VALID_FLAG0_HAPTICS_SELECT = 0x02
DS5_VALID_FLAG0_RIGHT_TRIGGER = 0x04
DS5_VALID_FLAG0_LEFT_TRIGGER = 0x08
DS5_VALID_FLAG1_LIGHTBAR = 0x04
DS5_VALID_FLAG1_PLAYER_LEDS = 0x10
DS5_TRIGGER_EFFECT_OFF = 0x00
DS5_TRIGGER_EFFECT_FEEDBACK = 0x21
DS5_TRIGGER_EFFECT_WEAPON = 0x25
VIRTUAL_TOUCHPAD_VENDOR_ID = 0x1209
VIRTUAL_TOUCHPAD_PRODUCT_ID = 0xD505
VIRTUAL_TOUCHPAD_USAGE_PAGE = 0xFF00
VIRTUAL_TOUCHPAD_REPORT_ID = 0x09
VIRTUAL_TOUCHPAD_REPORT_LENGTH = 50
VIRTUAL_TOUCHPAD_CONTACTS = 4
VIRTUAL_TOUCHPAD_REPORT_SLOTS = 5
VIRTUAL_TOUCHPAD_FRAME_SECONDS = 0.007
VIRTUAL_TOUCHPAD_MOVE_STEPS = 10

DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
ERROR_NO_MORE_ITEMS = 259
ERROR_INSUFFICIENT_BUFFER = 122
HIDP_STATUS_SUCCESS = 0x00110000
FRAME_INTERVAL_SECONDS = 1 / 60
BLINK_PERIOD_SECONDS = (2.0, 1.6, 1.2, 0.8, 0.55)
BREATHE_PERIOD_SECONDS = (5.0, 4.0, 3.2, 2.4, 1.7)
HAPTIC_PULSE_END_SECONDS = 0.09
HAPTIC_SECOND_PULSE_START_SECONDS = 0.19
HAPTIC_SECOND_PULSE_END_SECONDS = 0.28
HAPTIC_SETTLE_END_SECONDS = 0.36
HAPTIC_RIGHT_MOTOR = 45
HAPTIC_LEFT_MOTOR = 20
RECOIL_STRIKE_END_SECONDS = 0.045
RECOIL_SETTLE_END_SECONDS = 0.075
RECOIL_PRIORITY_HOLDOFF_SECONDS = 0.6
RECOIL_RIGHT_MOTOR = 255
RECOIL_LEFT_MOTOR = 80
CODEX_HOOK_STALE_SECONDS = 30 * 60
# Do not infer turn completion from a quiet interval. Long-running tools and
# model reasoning can legitimately produce no records for minutes. Explicit
# Stop/task_complete events close turns; the stale-session limit is only a
# last-resort cleanup for abandoned sessions.
CODEX_SESSION_FALLBACK_ENABLED = True
CODEX_SESSION_ROOT = os.path.join(os.path.expanduser("~"), ".codex", "sessions")
CODEX_SESSION_POLL_SECONDS = 0.35
CODEX_MICRO_TRANSIENT_SECONDS = 6.0
CODEX_APP_SHELL_TARGET = r"shell:AppsFolder\OpenAI.Codex_2p2nqsd0c76g0!App"
SW_SHOWNORMAL = 1
# Session JSONL is only a compatibility source.  A synthetic approval must
# never outlive the short window in which the session can actually be waiting.
# A structured approval remains pending until its matching call output, Stop,
# or normal stale-session cleanup. Real approvals can legitimately wait much
# longer than a few seconds while the user reviews the request.
CODEX_FALLBACK_APPROVAL_MAX_SECONDS = CODEX_HOOK_STALE_SECONDS
CODEX_LIGHT_PROFILES = {
    "approval": {
        "lightbar": {"red": 255, "green": 196, "blue": 0, "brightness": 100},
        "playerLeds": 0x1F,
        "effect": "blink",
        "speed": 4,
    },
    "working": {
        "lightbar": {"red": 48, "green": 132, "blue": 255, "brightness": 100},
        "playerLeds": 0x04,
        "effect": "breathe",
        "speed": 3,
    },
    "complete": {
        "lightbar": {"red": 44, "green": 204, "blue": 113, "brightness": 100},
        "playerLeds": 0x1F,
        "effect": "static",
        "speed": 3,
    },
    "idle": {
        "lightbar": {"red": 230, "green": 237, "blue": 236, "brightness": 45},
        "playerLeds": 0x04,
        "effect": "static",
        "speed": 3,
    },
    "error": {
        "lightbar": {"red": 255, "green": 54, "blue": 67, "brightness": 100},
        "playerLeds": 0x1F,
        "effect": "blink",
        "speed": 4,
    },
}
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120
STICK_SCROLL_INITIAL_DELAY_SECONDS = 0.16
STICK_SCROLL_REPEAT_SECONDS = 0.075
SMART_DELETE_HOLD_SECONDS = 0.55
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_SCANCODE = 0x0008
MAPVK_VK_TO_VSC_EX = 4
WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
LLKHF_EXTENDED = 0x01
LLKHF_INJECTED = 0x10
KEY_CAPTURE_TIMEOUT_SECONDS = 15.0

DS5_BUTTONS = (
    "dpad_up", "dpad_right", "dpad_down", "dpad_left",
    "square", "cross", "circle", "triangle",
    "l1", "r1", "l2", "r2", "create", "options", "l3", "r3",
    "ps", "touchpad", "mute",
    "left_stick_up", "left_stick_right", "left_stick_down", "left_stick_left",
    "right_stick_up", "right_stick_right", "right_stick_down", "right_stick_left",
)

STICK_DIRECTION_INPUTS = frozenset(DS5_BUTTONS[-8:])
STICK_DIRECTION_ORDER = {
    "left": ("left_stick_up", "left_stick_right", "left_stick_down", "left_stick_left"),
    "right": ("right_stick_up", "right_stick_right", "right_stick_down", "right_stick_left"),
}
STICK_ACTIVATION_THRESHOLD = 0.68
STICK_RELEASE_THRESHOLD = 0.42

DEFAULT_TOUCHPAD_GESTURES = {
    "enabled": True,
    "threshold": 320,
    "muteOnSwitch": False,
}
TOUCHPAD_GESTURE_SHORTCUTS = {
    "left": ["MetaLeft", "ControlLeft", "ArrowLeft"],
    "right": ["MetaLeft", "ControlLeft", "ArrowRight"],
}

VK_CODES = {
    "Backspace": 0x08, "Tab": 0x09, "Enter": 0x0D, "ShiftLeft": 0xA0,
    "ShiftRight": 0xA1, "ControlLeft": 0xA2, "ControlRight": 0xA3,
    "AltLeft": 0xA4, "AltRight": 0xA5, "Pause": 0x13, "CapsLock": 0x14,
    "Escape": 0x1B, "Space": 0x20, "PageUp": 0x21, "PageDown": 0x22,
    "End": 0x23, "Home": 0x24, "ArrowLeft": 0x25, "ArrowUp": 0x26,
    "ArrowRight": 0x27, "ArrowDown": 0x28, "PrintScreen": 0x2C,
    "Insert": 0x2D, "Delete": 0x2E, "MetaLeft": 0x5B, "MetaRight": 0x5C,
    "ContextMenu": 0x5D, "NumLock": 0x90, "ScrollLock": 0x91,
    "Semicolon": 0xBA, "Equal": 0xBB, "Comma": 0xBC, "Minus": 0xBD,
    "Period": 0xBE, "Slash": 0xBF, "Backquote": 0xC0,
    "BracketLeft": 0xDB, "Backslash": 0xDC, "BracketRight": 0xDD,
    "Quote": 0xDE, "NumpadMultiply": 0x6A, "NumpadAdd": 0x6B,
    "NumpadSubtract": 0x6D, "NumpadDecimal": 0x6E, "NumpadDivide": 0x6F,
    "NumpadEnter": 0x0D, "VolumeMute": 0xAD,
}
MAPPING_ACTIONS = {
    "CodexFocus", "CodexModelNext", "CodexModelPrevious",
    "CodexDictation", "CodexSmartDelete", "MouseWheelUp", "MouseWheelDown",
}
CODEX_FOCUS_SHORTCUT_DELAY_SECONDS = 0.35
CODEX_DICTATION_CODES = ["ControlLeft", "ShiftLeft", "KeyD"]
CODEX_DICTATION_TAP_SECONDS = 0.08
VK_CODES.update({f"Key{letter}": ord(letter) for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"})
VK_CODES.update({f"Digit{digit}": ord(digit) for digit in "0123456789"})
VK_CODES.update({f"F{number}": 0x6F + number for number in range(1, 13)})
VK_CODES.update({f"Numpad{digit}": 0x60 + digit for digit in range(10)})

# NumpadEnter shares a VK with Enter; hook reports need the extended flag to
# tell them apart. Keep the ordinary key as the default reverse lookup.
HOOK_CODES_BY_VK = {value: key for key, value in VK_CODES.items() if key != "NumpadEnter"}
MODIFIER_KEY_ORDER = (
    "ControlLeft", "ControlRight", "ShiftLeft", "ShiftRight",
    "AltLeft", "AltRight", "MetaLeft", "MetaRight",
)
MODIFIER_KEY_CODES = frozenset(MODIFIER_KEY_ORDER)

EXTENDED_CODES = {
    "ControlRight", "AltRight", "MetaLeft", "MetaRight", "ContextMenu",
    "Insert", "Delete", "Home", "End", "PageUp", "PageDown",
    "ArrowLeft", "ArrowUp", "ArrowRight", "ArrowDown", "NumLock",
    "PrintScreen", "NumpadEnter", "NumpadDivide", "VolumeMute",
}

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
ole32 = ctypes.WinDLL("ole32", use_last_error=True)
setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.ULONG),
        ("VendorID", wintypes.WORD),
        ("ProductID", wintypes.WORD),
        ("VersionNumber", wintypes.WORD),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wintypes.WORD),
        ("UsagePage", wintypes.WORD),
        ("InputReportByteLength", wintypes.WORD),
        ("OutputReportByteLength", wintypes.WORD),
        ("FeatureReportByteLength", wintypes.WORD),
        ("Reserved", wintypes.WORD * 17),
        ("NumberLinkCollectionNodes", wintypes.WORD),
        ("NumberInputButtonCaps", wintypes.WORD),
        ("NumberInputValueCaps", wintypes.WORD),
        ("NumberInputDataIndices", wintypes.WORD),
        ("NumberOutputButtonCaps", wintypes.WORD),
        ("NumberOutputValueCaps", wintypes.WORD),
        ("NumberOutputDataIndices", wintypes.WORD),
        ("NumberFeatureButtonCaps", wintypes.WORD),
        ("NumberFeatureValueCaps", wintypes.WORD),
        ("NumberFeatureDataIndices", wintypes.WORD),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class TOUCH_POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class TOUCH_RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG), ("top", wintypes.LONG),
        ("right", wintypes.LONG), ("bottom", wintypes.LONG),
    ]


class POINTER_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerType", wintypes.DWORD), ("pointerId", wintypes.DWORD),
        ("frameId", wintypes.DWORD), ("pointerFlags", wintypes.DWORD),
        ("sourceDevice", wintypes.HANDLE), ("hwndTarget", wintypes.HWND),
        ("ptPixelLocation", TOUCH_POINT), ("ptHimetricLocation", TOUCH_POINT),
        ("ptPixelLocationRaw", TOUCH_POINT), ("ptHimetricLocationRaw", TOUCH_POINT),
        ("dwTime", wintypes.DWORD), ("historyCount", wintypes.DWORD),
        ("InputData", wintypes.LONG), ("dwKeyStates", wintypes.DWORD),
        ("PerformanceCount", ctypes.c_uint64), ("ButtonChangeType", wintypes.DWORD),
    ]


class POINTER_TOUCH_INFO(ctypes.Structure):
    _fields_ = [
        ("pointerInfo", POINTER_INFO), ("touchFlags", wintypes.DWORD),
        ("touchMask", wintypes.DWORD), ("rcContact", TOUCH_RECT),
        ("rcContactRaw", TOUCH_RECT), ("orientation", wintypes.DWORD),
        ("pressure", wintypes.DWORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", wintypes.DWORD), ("data", INPUT_UNION)]


setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [wintypes.HANDLE, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = wintypes.BOOL
hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_GetPreparsedData.restype = wintypes.BOOL
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidD_FreePreparsedData.restype = wintypes.BOOL
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = wintypes.LONG
kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
kernel32.WriteFile.restype = wintypes.BOOL
kernel32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
kernel32.ReadFile.restype = wintypes.BOOL
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
shell32.ShellExecuteW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int]
shell32.ShellExecuteW.restype = wintypes.HINSTANCE
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT
LowLevelKeyboardProc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, LowLevelKeyboardProc, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HANDLE
user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.InitializeTouchInjection.argtypes = [wintypes.UINT, wintypes.DWORD]
user32.InitializeTouchInjection.restype = wintypes.BOOL
user32.InjectTouchInput.argtypes = [wintypes.UINT, ctypes.POINTER(POINTER_TOUCH_INFO)]
user32.InjectTouchInput.restype = wintypes.BOOL
ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
ole32.CoInitializeEx.restype = ctypes.c_long
ole32.CoUninitialize.argtypes = []
ole32.CoUninitialize.restype = None
ole32.CoCreateInstance.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
ole32.CoCreateInstance.restype = ctypes.c_long

CLSCTX_ALL = 0x17
COINIT_APARTMENTTHREADED = 0x2
VIRTUAL_DESKTOP_LEFT = 3
VIRTUAL_DESKTOP_RIGHT = 4
POINTER_TYPE_TOUCH = 2
POINTER_FLAG_INRANGE = 0x00000002
POINTER_FLAG_INCONTACT = 0x00000004
POINTER_FLAG_PRIMARY = 0x00002000
POINTER_FLAG_DOWN = 0x00010000
POINTER_FLAG_UPDATE = 0x00020000
POINTER_FLAG_UP = 0x00040000
TOUCH_MASK_CONTACTAREA = 0x00000001
TOUCH_MASK_ORIENTATION = 0x00000002
TOUCH_MASK_PRESSURE = 0x00000004
TOUCH_FEEDBACK_NONE = 0x00000003
CLSID_IMMERSIVE_SHELL = "C2F03A33-21F5-47FA-B4BB-156362A2F239"
CLSID_VIRTUAL_DESKTOP_MANAGER_INTERNAL = "C5E0CDCA-7B6E-41B2-9FC4-D939CC6E4A48"
IID_SERVICE_PROVIDER = "6D5140C1-7436-11CE-8034-00AA006009FA"
IID_VIRTUAL_DESKTOP_MANAGER_INTERNAL = "AF8DA486-95BB-4460-B3B7-6E7A6B2962B5"


def clamp_byte(value: object) -> int:
    return max(0, min(255, int(value)))


def _guid(value: str) -> GUID:
    return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)


def _com_method(instance: ctypes.c_void_p, index: int, result_type: object, arg_types: list[object], *args: object) -> object:
    vtable = ctypes.cast(instance, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    address = vtable[index]
    if not address:
        raise RuntimeError(f"COM method {index} is unavailable")
    function = ctypes.WINFUNCTYPE(result_type, ctypes.c_void_p, *arg_types)(address)
    return function(instance, *args)


def _release_com(instance: ctypes.c_void_p | None) -> None:
    if instance and instance.value:
        try:
            _com_method(instance, 2, ctypes.c_long, [])
        except Exception:
            pass


def switch_virtual_desktop(direction: str) -> bool:
    """Switch desktops through Explorer's Shell service, outside the foreground app."""
    if direction not in {"left", "right"}:
        return False
    initialized = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    if initialized not in (0, 1, 0x80010106):  # S_OK, S_FALSE, RPC_E_CHANGED_MODE
        return False
    service_provider = ctypes.c_void_p()
    desktop_manager = ctypes.c_void_p()
    current_desktop = ctypes.c_void_p()
    adjacent_desktop = ctypes.c_void_p()
    try:
        if initialized == 0x80010106:
            return False
        result = ole32.CoCreateInstance(
            ctypes.byref(_guid(CLSID_IMMERSIVE_SHELL)), None, CLSCTX_ALL,
            ctypes.byref(_guid(IID_SERVICE_PROVIDER)), ctypes.byref(service_provider),
        )
        if result != 0:
            return False
        result = _com_method(
            service_provider, 3, ctypes.c_long,
            [ctypes.POINTER(GUID), ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)],
            ctypes.byref(_guid(CLSID_VIRTUAL_DESKTOP_MANAGER_INTERNAL)),
            ctypes.byref(_guid(IID_VIRTUAL_DESKTOP_MANAGER_INTERNAL)),
            ctypes.byref(desktop_manager),
        )
        if result != 0:
            return False
        result = _com_method(
            desktop_manager, 6, ctypes.c_long,
            [ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(current_desktop),
        )
        if result != 0:
            return False
        result = _com_method(
            desktop_manager, 8, ctypes.c_long,
            [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)],
            current_desktop, VIRTUAL_DESKTOP_LEFT if direction == "left" else VIRTUAL_DESKTOP_RIGHT,
            ctypes.byref(adjacent_desktop),
        )
        if result != 0:
            return False
        result = _com_method(
            desktop_manager, 9, ctypes.c_long,
            [ctypes.c_void_p], adjacent_desktop,
        )
        return result == 0
    except Exception:
        return False
    finally:
        _release_com(adjacent_desktop)
        _release_com(current_desktop)
        _release_com(desktop_manager)
        _release_com(service_provider)
        if initialized in (0, 1):
            ole32.CoUninitialize()


_touch_injection_lock = threading.Lock()
_touch_injection_initialized = False
_touch_injection_frame = 0


def _touch_point(
    pointer_id: int,
    frame_id: int,
    x: int,
    y: int,
    flags: int,
) -> POINTER_TOUCH_INFO:
    point = POINTER_TOUCH_INFO()
    point.pointerInfo.pointerType = POINTER_TYPE_TOUCH
    point.pointerInfo.pointerId = pointer_id
    point.pointerInfo.frameId = frame_id
    point.pointerInfo.pointerFlags = flags
    point.pointerInfo.ptPixelLocation = TOUCH_POINT(x, y)
    point.pointerInfo.ptPixelLocationRaw = TOUCH_POINT(x, y)
    point.touchFlags = 0
    point.touchMask = TOUCH_MASK_CONTACTAREA | TOUCH_MASK_ORIENTATION | TOUCH_MASK_PRESSURE
    point.rcContact = TOUCH_RECT(x - 18, y - 18, x + 18, y + 18)
    point.rcContactRaw = TOUCH_RECT(x - 18, y - 18, x + 18, y + 18)
    point.orientation = 90
    point.pressure = 32000
    return point


def inject_four_finger_swipe(direction: str) -> bool:
    """Inject four synchronized touch contacts so Windows Shell sees a swipe."""
    global _touch_injection_initialized, _touch_injection_frame
    if direction not in {"left", "right"}:
        return False
    with _touch_injection_lock:
        try:
            if not _touch_injection_initialized:
                if not user32.InitializeTouchInjection(4, TOUCH_FEEDBACK_NONE):
                    return False
                _touch_injection_initialized = True
            width = max(640, int(user32.GetSystemMetrics(0)))
            height = max(480, int(user32.GetSystemMetrics(1)))
            center_y = round(height * 0.54)
            spread = max(36, round(width * 0.035))
            start_x = round(width * (0.72 if direction == "left" else 0.28))
            end_x = round(width * (0.28 if direction == "left" else 0.72))
            ys = [center_y - spread * 1.5, center_y - spread * 0.5, center_y + spread * 0.5, center_y + spread * 1.5]
            _touch_injection_frame = (_touch_injection_frame + 1) & 0xFFFFFFFF
            frame = _touch_injection_frame
            down = (POINTER_TOUCH_INFO * 4)(*(
                _touch_point(index + 1, frame, start_x, round(y), POINTER_FLAG_DOWN | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT | (POINTER_FLAG_PRIMARY if index == 0 else 0))
                for index, y in enumerate(ys)
            ))
            if not user32.InjectTouchInput(4, down):
                return False
            steps = 6
            for step in range(1, steps + 1):
                frame = (frame + 1) & 0xFFFFFFFF
                x = round(start_x + (end_x - start_x) * step / steps)
                move = (POINTER_TOUCH_INFO * 4)(*(
                    _touch_point(index + 1, frame, x, round(y), POINTER_FLAG_UPDATE | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT | (POINTER_FLAG_PRIMARY if index == 0 else 0))
                    for index, y in enumerate(ys)
                ))
                if not user32.InjectTouchInput(4, move):
                    return False
                time.sleep(0.018)
            frame = (frame + 1) & 0xFFFFFFFF
            up = (POINTER_TOUCH_INFO * 4)(*(
                _touch_point(index + 1, frame, end_x, round(y), POINTER_FLAG_UP | (POINTER_FLAG_PRIMARY if index == 0 else 0))
                for index, y in enumerate(ys)
            ))
            return bool(user32.InjectTouchInput(4, up))
        except Exception:
            return False


def perform_touchpad_swipe(direction: str) -> str:
    """Submit a native four-contact gesture through the virtual HID driver."""
    if direction not in {"left", "right"}:
        raise ValueError("touchpad swipe direction must be left or right")
    try:
        send_virtual_touchpad_swipe(direction)
    except FileNotFoundError:
        return "driver-required"
    except OSError:
        return "unavailable"
    return "touch-injection"


_virtual_touchpad_lock = threading.Lock()
_virtual_touchpad_probe_lock = threading.Lock()
_virtual_touchpad_probe_at = 0.0
_virtual_touchpad_probe_result = False
_virtual_touchpad_path: str | None = None


def build_virtual_touchpad_report(
    contacts: list[tuple[int, int, bool]],
    scan_time: int,
    reported_contact_count: int | None = None,
) -> bytearray:
    """Build the vendor report that the driver converts to PTP report ID 5."""
    if len(contacts) != VIRTUAL_TOUCHPAD_CONTACTS:
        raise ValueError("virtual touchpad reports require exactly four contact slots")
    report = bytearray((VIRTUAL_TOUCHPAD_REPORT_ID,))
    active_count = 0
    for contact_id, (x, y, active) in enumerate(contacts):
        x = max(0, min(20000, int(x)))
        y = max(0, min(12000, int(y)))
        status = 0x01 | ((1 if active else 0) << 1)
        report.extend(struct.pack("<BIHH", status, contact_id, x, y))
        active_count += int(active)
    for _slot in range(VIRTUAL_TOUCHPAD_CONTACTS, VIRTUAL_TOUCHPAD_REPORT_SLOTS):
        report.extend(bytes(9))
    contact_count = active_count if reported_contact_count is None else int(reported_contact_count)
    if not 0 <= contact_count <= VIRTUAL_TOUCHPAD_CONTACTS:
        raise ValueError("reported touchpad contact count is out of range")
    report.extend(struct.pack("<HBB", scan_time & 0xFFFF, contact_count, 0))
    if len(report) != VIRTUAL_TOUCHPAD_REPORT_LENGTH:
        raise AssertionError(f"virtual touchpad report is {len(report)} bytes")
    return report


def find_virtual_touchpad() -> tuple[str, int] | None:
    """Find the vendor top-level collection exposed by the virtual driver."""
    global _virtual_touchpad_path
    if _virtual_touchpad_path:
        handle = open_handle(_virtual_touchpad_path, GENERIC_WRITE)
        if handle is not None:
            return _virtual_touchpad_path, handle
        _virtual_touchpad_path = None

    for path in device_paths():
        attributes = attributes_for(path)
        if not attributes or (
            attributes.VendorID != VIRTUAL_TOUCHPAD_VENDOR_ID
            or attributes.ProductID != VIRTUAL_TOUCHPAD_PRODUCT_ID
        ):
            continue
        handle = open_handle(path, GENERIC_WRITE)
        if handle is None:
            continue
        caps = caps_for(handle)
        if (
            caps
            and caps.UsagePage == VIRTUAL_TOUCHPAD_USAGE_PAGE
            and caps.OutputReportByteLength == VIRTUAL_TOUCHPAD_REPORT_LENGTH
        ):
            _virtual_touchpad_path = path
            return path, handle
        kernel32.CloseHandle(handle)
    return None


def virtual_touchpad_available(force: bool = False) -> bool:
    """Probe the virtual HID collection with a short cache for status polling."""
    global _virtual_touchpad_probe_at, _virtual_touchpad_probe_result
    with _virtual_touchpad_probe_lock:
        now = time.monotonic()
        if not force and now - _virtual_touchpad_probe_at < 2.0:
            return _virtual_touchpad_probe_result
        device = find_virtual_touchpad()
        if device is not None:
            _path, handle = device
            kernel32.CloseHandle(handle)
        _virtual_touchpad_probe_result = device is not None
        _virtual_touchpad_probe_at = now
        return _virtual_touchpad_probe_result


def send_virtual_touchpad_swipe(direction: str) -> None:
    """Send a complete four-finger horizontal gesture to HIDClass."""
    with _virtual_touchpad_lock:
        device = find_virtual_touchpad()
        if device is None:
            raise FileNotFoundError("DS5 virtual Precision Touchpad is not installed")
        _path, handle = device
        global _virtual_touchpad_probe_at, _virtual_touchpad_probe_result
        with _virtual_touchpad_probe_lock:
            _virtual_touchpad_probe_at = time.monotonic()
            _virtual_touchpad_probe_result = True
        try:
            start_x, end_x = (16500, 3500) if direction == "left" else (3500, 16500)
            x_offsets = (-750, -250, 250, 750)
            y_positions = (3500, 5200, 6900, 8600)
            scan_time = int(time.monotonic() * 10000) & 0xFFFF

            def contacts_at(x: int, active: bool) -> list[tuple[int, int, bool]]:
                return [
                    (x + x_offset, y, active)
                    for x_offset, y in zip(x_offsets, y_positions, strict=True)
                ]

            write_report(handle, build_virtual_touchpad_report(contacts_at(start_x, True), scan_time))
            time.sleep(VIRTUAL_TOUCHPAD_FRAME_SECONDS)
            steps = VIRTUAL_TOUCHPAD_MOVE_STEPS
            scan_step = round(VIRTUAL_TOUCHPAD_FRAME_SECONDS * 10000)
            for step in range(1, steps + 1):
                x = round(start_x + (end_x - start_x) * step / steps)
                scan_time = (scan_time + scan_step) & 0xFFFF
                write_report(handle, build_virtual_touchpad_report(contacts_at(x, True), scan_time))
                time.sleep(VIRTUAL_TOUCHPAD_FRAME_SECONDS)
            scan_time = (scan_time + scan_step) & 0xFFFF
            write_report(handle, build_virtual_touchpad_report(
                contacts_at(end_x, False),
                scan_time,
                reported_contact_count=VIRTUAL_TOUCHPAD_CONTACTS,
            ))
            time.sleep(VIRTUAL_TOUCHPAD_FRAME_SECONDS)
            scan_time = (scan_time + scan_step) & 0xFFFF
            write_report(handle, build_virtual_touchpad_report(contacts_at(end_x, False), scan_time))
        finally:
            kernel32.CloseHandle(handle)


def load_or_create_bridge_token(path: str = BRIDGE_TOKEN_PATH) -> str:
    try:
        with open(path, "r", encoding="ascii") as stream:
            token = stream.read(256).strip()
        if len(token) >= 32:
            return token
        raise RuntimeError("Bridge token file is invalid")
    except FileNotFoundError:
        pass

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    token = secrets.token_urlsafe(32)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return load_or_create_bridge_token(path)
    with os.fdopen(descriptor, "w", encoding="ascii") as stream:
        stream.write(token)
    return token


def validate_post_request(
    path: str,
    origin: str,
    content_type: str,
    hook_token: str,
    expected_hook_token: str,
) -> tuple[HTTPStatus, str] | None:
    if origin and origin not in ALLOWED_WEB_ORIGINS:
        return HTTPStatus.FORBIDDEN, "origin is not allowed"
    if content_type.lower() != "application/json":
        return HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "application/json is required"
    if path == "/api/codex-hook" and (
        not expected_hook_token
        or not secrets.compare_digest(hook_token, expected_hook_token)
    ):
        return HTTPStatus.UNAUTHORIZED, "invalid bridge token"
    return None


def device_paths() -> list[str]:
    hid_guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(hid_guid))
    info_set = setupapi.SetupDiGetClassDevsW(ctypes.byref(hid_guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if info_set == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())

    paths: list[str] = []
    try:
        index = 0
        while True:
            interface = SP_DEVICE_INTERFACE_DATA(cbSize=ctypes.sizeof(SP_DEVICE_INTERFACE_DATA))
            if not setupapi.SetupDiEnumDeviceInterfaces(info_set, None, ctypes.byref(hid_guid), index, ctypes.byref(interface)):
                if ctypes.get_last_error() == ERROR_NO_MORE_ITEMS:
                    break
                raise ctypes.WinError(ctypes.get_last_error())

            required = wintypes.DWORD()
            setupapi.SetupDiGetDeviceInterfaceDetailW(info_set, ctypes.byref(interface), None, 0, ctypes.byref(required), None)
            if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER:
                raise ctypes.WinError(ctypes.get_last_error())

            detail = ctypes.create_string_buffer(required.value)
            # This ABI uses 8 on 64-bit Windows and 6 on 32-bit Windows.
            ctypes.cast(detail, ctypes.POINTER(wintypes.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(info_set, ctypes.byref(interface), detail, required.value, None, None):
                raise ctypes.WinError(ctypes.get_last_error())
            paths.append(ctypes.wstring_at(ctypes.addressof(detail) + ctypes.sizeof(wintypes.DWORD)))
            index += 1
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(info_set)
    return paths


def open_handle(path: str, access: int) -> int | None:
    handle = kernel32.CreateFileW(path, access, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    return None if handle == INVALID_HANDLE_VALUE else handle


def attributes_for(path: str) -> HIDD_ATTRIBUTES | None:
    handle = open_handle(path, 0)
    if handle is None:
        return None
    try:
        attributes = HIDD_ATTRIBUTES(Size=ctypes.sizeof(HIDD_ATTRIBUTES))
        return attributes if hid.HidD_GetAttributes(handle, ctypes.byref(attributes)) else None
    finally:
        kernel32.CloseHandle(handle)


def caps_for(handle: int) -> HIDP_CAPS | None:
    preparsed = ctypes.c_void_p()
    if not hid.HidD_GetPreparsedData(handle, ctypes.byref(preparsed)):
        return None
    try:
        caps = HIDP_CAPS()
        status = ctypes.c_ulong(hid.HidP_GetCaps(preparsed, ctypes.byref(caps))).value
        return caps if status == HIDP_STATUS_SUCCESS else None
    finally:
        hid.HidD_FreePreparsedData(preparsed)


def find_dualsense_usb() -> tuple[str, int] | None:
    for path in device_paths():
        attributes = attributes_for(path)
        if not attributes or attributes.VendorID != SONY_VENDOR_ID:
            continue
        handle = open_handle(path, GENERIC_READ | GENERIC_WRITE)
        if handle is None:
            continue
        try:
            caps = caps_for(handle)
            if caps and caps.OutputReportByteLength == DS5_USB_OUTPUT_LENGTH and caps.InputReportByteLength >= 11:
                return path, attributes.ProductID
        finally:
            kernel32.CloseHandle(handle)
    return None


def normalize_lighting(payload: dict[str, object]) -> dict[str, int | str]:
    lightbar = payload.get("lightbar")
    if not isinstance(lightbar, dict):
        raise ValueError("lightbar object is required")
    effect = str(payload.get("effect", "static"))
    if effect not in {"static", "blink", "breathe"}:
        raise ValueError("effect must be static, blink, or breathe")
    speed = max(1, min(5, int(payload.get("speed", 3))))
    return {
        "red": clamp_byte(lightbar.get("red", 0)),
        "green": clamp_byte(lightbar.get("green", 0)),
        "blue": clamp_byte(lightbar.get("blue", 0)),
        "brightness": max(0, min(100, int(lightbar.get("brightness", 100)))),
        "playerLeds": max(0, min(0x1F, int(payload.get("playerLeds", 0)))),
        "effect": effect,
        "speed": speed,
    }


def normalize_trigger(trigger: object) -> dict[str, int | str]:
    if not isinstance(trigger, dict):
        raise ValueError("trigger configuration must be an object")
    mode = str(trigger.get("mode", "off")).strip().lower()
    if mode not in {"off", "feedback", "weapon"}:
        raise ValueError("trigger mode must be off, feedback, or weapon")
    start = max(0, min(9, int(trigger.get("start", 3))))
    strength = max(1, min(8, int(trigger.get("strength", 5))))
    requested_end = max(1, min(9, int(trigger.get("end", max(start + 1, 6)))))
    end = min(9, max(start + 1, requested_end))
    if mode == "weapon" and not 2 <= start <= 7:
        raise ValueError("weapon trigger start must be between 2 and 7")
    if mode == "weapon" and not start < end <= 8:
        raise ValueError("weapon trigger end must be after start and no greater than 8")
    return {"mode": mode, "start": start, "end": end, "strength": strength}


def normalize_triggers(payload: dict[str, object]) -> dict[str, dict[str, int | str]]:
    return {
        "left": normalize_trigger(payload.get("left", {})),
        "right": normalize_trigger(payload.get("right", {})),
    }


def build_trigger_effect(config: dict[str, int | str]) -> bytes:
    """Encode one adaptive trigger using the DualSense common output block."""
    effect = bytearray(11)
    mode = str(config["mode"])
    if mode == "off":
        effect[0] = DS5_TRIGGER_EFFECT_OFF
    elif mode == "weapon":
        start = int(config["start"])
        end = int(config["end"])
        breakpoints = (1 << start) | (1 << end)
        effect[0] = DS5_TRIGGER_EFFECT_WEAPON
        effect[1:3] = breakpoints.to_bytes(2, "little")
        effect[3] = int(config["strength"]) - 1
    else:
        # Feedback divides the travel into ten zones. The first 16-bit value
        # selects active zones and the following 32 bits store 3-bit forces.
        start = int(config["start"])
        strength = int(config["strength"]) - 1
        active_zones = ((1 << (10 - start)) - 1) << start
        force_zones = sum(strength << (zone * 3) for zone in range(start, 10))
        effect[0] = DS5_TRIGGER_EFFECT_FEEDBACK
        effect[1:3] = active_zones.to_bytes(2, "little")
        effect[3:7] = force_zones.to_bytes(4, "little")
    return bytes(effect)


def normalize_touchpad_gestures(payload: object) -> dict[str, int | bool]:
    if payload is None:
        return dict(DEFAULT_TOUCHPAD_GESTURES)
    if not isinstance(payload, dict):
        raise ValueError("touchpadGestures must be an object")
    threshold = int(payload.get("threshold", DEFAULT_TOUCHPAD_GESTURES["threshold"]))
    if not 160 <= threshold <= 800:
        raise ValueError("touchpad gesture threshold must be between 160 and 800")
    return {
        "enabled": bool(payload.get("enabled", DEFAULT_TOUCHPAD_GESTURES["enabled"])),
        "threshold": threshold,
        "muteOnSwitch": bool(payload.get("muteOnSwitch", DEFAULT_TOUCHPAD_GESTURES["muteOnSwitch"])),
    }


def normalize_mapping(
    payload: dict[str, object],
) -> tuple[bool, dict[str, list[str]], dict[str, int | bool]]:
    enabled = bool(payload.get("enabled", False))
    raw_mappings = payload.get("mappings", {})
    if not isinstance(raw_mappings, dict):
        raise ValueError("mappings must be an object")
    mappings: dict[str, list[str]] = {}
    for button, shortcut in raw_mappings.items():
        if button not in DS5_BUTTONS:
            raise ValueError(f"unknown controller button: {button}")
        if not isinstance(shortcut, list) or not 1 <= len(shortcut) <= 5:
            raise ValueError(f"mapping for {button} must contain 1 to 5 keyboard codes")
        codes = [str(code) for code in shortcut]
        unknown = [code for code in codes if code not in VK_CODES and code not in MAPPING_ACTIONS]
        if unknown:
            raise ValueError(f"unsupported keyboard code: {unknown[0]}")
        if any(code in MAPPING_ACTIONS for code in codes) and len(codes) != 1:
            raise ValueError("controller actions cannot be combined with keyboard codes")
        mappings[button] = codes
    gestures = normalize_touchpad_gestures(payload.get("touchpadGestures"))
    return enabled, mappings, gestures


def load_mapping_config(path: str) -> tuple[bool, dict[str, list[str]], dict[str, int | bool]]:
    try:
        with open(path, "r", encoding="utf-8") as stream:
            payload = json.load(stream)
    except FileNotFoundError:
        return False, {}, dict(DEFAULT_TOUCHPAD_GESTURES)
    if not isinstance(payload, dict):
        raise ValueError("saved mapping configuration must be an object")
    return normalize_mapping(payload)


def save_mapping_config(
    path: str,
    enabled: bool,
    mappings: dict[str, list[str]],
    gestures: dict[str, int | bool],
) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temporary = f"{path}.{os.getpid()}.tmp"
    payload = {
        "version": 1,
        "enabled": enabled,
        "mappings": mappings,
        "touchpadGestures": gestures,
    }
    try:
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.remove(temporary)
        except FileNotFoundError:
            pass


def parse_dualsense_usb_input(report: bytes) -> tuple[set[str], dict[str, object]]:
    if len(report) < 11 or report[0] != 0x01:
        raise ValueError("unsupported DualSense USB input report")

    first = report[8]
    second = report[9]
    third = report[10]
    dpad = first & 0x0F
    pressed: set[str] = set()
    if dpad in {0, 1, 7}:
        pressed.add("dpad_up")
    if dpad in {1, 2, 3}:
        pressed.add("dpad_right")
    if dpad in {3, 4, 5}:
        pressed.add("dpad_down")
    if dpad in {5, 6, 7}:
        pressed.add("dpad_left")

    for bit, name in enumerate(("square", "cross", "circle", "triangle"), start=4):
        if first & (1 << bit):
            pressed.add(name)
    for bit, name in enumerate(("l1", "r1", "l2", "r2", "create", "options", "l3", "r3")):
        if second & (1 << bit):
            pressed.add(name)
    for bit, name in enumerate(("ps", "touchpad", "mute")):
        if third & (1 << bit):
            pressed.add(name)

    def axis(value: int) -> float:
        return round((value - 127.5) / 127.5, 3)

    touch_active = False
    touch_id: int | None = None
    touch_x: int | None = None
    touch_y: int | None = None
    # USB report 0x01 stores two four-byte touch points at 33..40. Bit 7
    # marks an inactive point; X is 12-bit (0..1919) and Y is 12-bit
    # (0..1079). Prefer the first active point for single-finger gestures.
    for offset in (33, 37):
        if len(report) < offset + 4 or report[offset] & 0x80:
            continue
        touch_active = True
        touch_id = report[offset] & 0x7F
        touch_x = report[offset + 1] | ((report[offset + 2] & 0x0F) << 8)
        touch_y = (report[offset + 2] >> 4) | (report[offset + 3] << 4)
        break

    axes: dict[str, object] = {
        "leftX": axis(report[1]), "leftY": axis(report[2]),
        "rightX": axis(report[3]), "rightY": axis(report[4]),
        "leftTrigger": round(report[5] / 255, 3),
        "rightTrigger": round(report[6] / 255, 3),
        "leftTriggerEffectStatus": (report[43] >> 4) & 0x0F if len(report) > 43 else 0,
        "rightTriggerEffectStatus": (report[42] >> 4) & 0x0F if len(report) > 42 else 0,
        "touchActive": touch_active,
        "touchId": touch_id,
        "touchX": touch_x,
        "touchY": touch_y,
    }
    return pressed, axes


def resolve_stick_directions(
    axes: dict[str, object],
    active: set[str] | None = None,
) -> set[str]:
    """Convert both analog sticks into one hysteretic cardinal input each."""
    previous = (active or set()) & STICK_DIRECTION_INPUTS
    resolved: set[str] = set()
    for side, directions in STICK_DIRECTION_ORDER.items():
        x = max(-1.0, min(1.0, float(axes.get(f"{side}X", 0.0))))
        y = max(-1.0, min(1.0, float(axes.get(f"{side}Y", 0.0))))
        components = {
            directions[0]: -y,
            directions[1]: x,
            directions[2]: y,
            directions[3]: -x,
        }
        current = next((direction for direction in directions if direction in previous), None)
        if current is not None:
            perpendicular = abs(x) if current in {directions[0], directions[2]} else abs(y)
            if components[current] >= STICK_RELEASE_THRESHOLD and components[current] >= perpendicular * 0.8:
                resolved.add(current)
                continue

        candidate = max(directions, key=components.__getitem__)
        if components[candidate] >= STICK_ACTIVATION_THRESHOLD:
            resolved.add(candidate)
    return resolved


def keyboard_event(code: str, key_up: bool) -> INPUT:
    virtual_key = VK_CODES[code]
    scan_code = user32.MapVirtualKeyW(virtual_key, MAPVK_VK_TO_VSC_EX)
    flags = KEYEVENTF_KEYUP if key_up else 0
    if code in EXTENDED_CODES:
        flags |= KEYEVENTF_EXTENDEDKEY
    if scan_code:
        flags |= KEYEVENTF_SCANCODE
        return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wScan=scan_code & 0xFF, dwFlags=flags))
    return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=virtual_key, dwFlags=flags))


def send_keyboard_codes(codes: list[str], key_up: bool) -> None:
    if not codes:
        return
    events = (INPUT * len(codes))(*(keyboard_event(code, key_up) for code in codes))
    inserted = user32.SendInput(len(events), events, ctypes.sizeof(INPUT))
    if inserted == len(events):
        return
    error_code = ctypes.get_last_error()
    if not key_up and inserted:
        cleanup_codes = list(reversed(codes[:inserted]))
        cleanup = (INPUT * len(cleanup_codes))(*(keyboard_event(code, True) for code in cleanup_codes))
        user32.SendInput(len(cleanup), cleanup, ctypes.sizeof(INPUT))
    if error_code:
        raise ctypes.WinError(error_code)
    raise RuntimeError(
        f"SendInput inserted {inserted} of {len(events)} events; "
        "the target may run at a higher Windows integrity level"
    )


def send_keyboard_code(code: str, key_up: bool) -> None:
    send_keyboard_codes([code], key_up)


def send_mouse_wheel(delta: int) -> None:
    event = INPUT(
        type=INPUT_MOUSE,
        mi=MOUSEINPUT(mouseData=delta & 0xFFFFFFFF, dwFlags=MOUSEEVENTF_WHEEL),
    )
    inserted = user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))
    if inserted == 1:
        return
    error_code = ctypes.get_last_error()
    if error_code:
        raise ctypes.WinError(error_code)
    raise RuntimeError("SendInput could not inject the mouse wheel event")


def focus_or_launch_codex() -> None:
    result = int(shell32.ShellExecuteW(None, "open", CODEX_APP_SHELL_TARGET, None, None, SW_SHOWNORMAL))
    if result <= 32:
        raise RuntimeError(f"Windows could not open Codex (ShellExecute result {result})")


class InputMappingEngine:
    def __init__(
        self,
        trigger_observer: Callable[[dict[str, object]], dict[str, bool]] | None = None,
        touchpad_swipe_handler: Callable[[str], str] | None = None,
        config_path: str | None = None,
    ) -> None:
        self._config_path = config_path
        self._config_error: str | None = None
        try:
            initial_enabled, initial_mappings, initial_gestures = (
                load_mapping_config(config_path)
                if config_path
                else (False, {}, dict(DEFAULT_TOUCHPAD_GESTURES))
            )
        except Exception as error:
            initial_enabled, initial_mappings, initial_gestures = False, {}, dict(DEFAULT_TOUCHPAD_GESTURES)
            self._config_error = str(error)
        self._lock = threading.RLock()
        self._enabled = initial_enabled
        self._capture_suspended = False
        self._mappings = initial_mappings
        self._touchpad_gestures = initial_gestures
        self._pressed: set[str] = set()
        self._mapping_pressed: set[str] = set()
        self._stick_directions: set[str] = set()
        self._active_bindings: dict[str, list[str]] = {}
        self._key_counts: dict[str, int] = {}
        self._axes = {
            "leftX": 0.0, "leftY": 0.0, "rightX": 0.0, "rightY": 0.0,
            "leftTrigger": 0.0, "rightTrigger": 0.0,
            "touchActive": False, "touchId": None, "touchX": None, "touchY": None,
        }
        self._connected = False
        self._product_id: int | None = None
        self._reports = 0
        self._last_report_at: float | None = None
        self._last_error: str | None = None
        self._dispatch_count = 0
        self._last_dispatched_button: str | None = None
        self._last_shortcut: list[str] = []
        self._last_dispatch_at: float | None = None
        self._last_injection_error: str | None = None
        self._gesture_tracking = False
        self._gesture_fired = False
        self._gesture_touch_id: int | None = None
        self._gesture_start_x: int | None = None
        self._gesture_start_y: int | None = None
        self._gesture_last_x: int | None = None
        self._gesture_last_y: int | None = None
        self._touchpad_button_was_pressed = False
        self._touchpad_click_suppressed = False
        self._smart_delete_started: dict[str, float] = {}
        self._smart_delete_long_fired: set[str] = set()
        self._repeat_action_next: dict[str, float] = {}
        self._last_gesture: str | None = None
        self._last_gesture_at: float | None = None
        self._last_touchpad_switch_mode: str | None = None
        self._last_touchpad_switch_error: str | None = None
        self._mute_count = 0
        self._last_mute_at: float | None = None
        self._trigger_observer = trigger_observer
        self._touchpad_swipe_handler = touchpad_swipe_handler
        self._thread = threading.Thread(target=self._run, name="ds5-input-mapper", daemon=True)
        self._codex_model_index = 0

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def configure(self, payload: dict[str, object]) -> dict[str, object]:
        enabled, mappings, gestures = normalize_mapping(payload)
        if self._config_path:
            save_mapping_config(self._config_path, enabled, mappings, gestures)
        with self._lock:
            self._release_all_locked()
            self._mappings = mappings
            self._touchpad_gestures = gestures
            self._enabled = enabled
            self._mapping_pressed.clear()
            self._stick_directions.clear()
            self._reset_gesture_locked()
            self._touchpad_button_was_pressed = False
            self._touchpad_click_suppressed = False
            self._smart_delete_started.clear()
            self._smart_delete_long_fired.clear()
            self._repeat_action_next.clear()
            self._last_injection_error = None
            self._last_touchpad_switch_mode = None
            self._last_touchpad_switch_error = None
            self._config_error = None
            return self._status_locked()

    def status(self) -> dict[str, object]:
        with self._lock:
            return self._status_locked()

    def set_capture_suspended(self, suspended: bool) -> None:
        """Prevent controller mappings from leaking while a keyboard chord is recorded."""
        with self._lock:
            if self._capture_suspended == suspended:
                return
            self._release_all_locked()
            self._capture_suspended = suspended

    def _status_locked(self) -> dict[str, object]:
        age_ms = None if self._last_report_at is None else round((time.monotonic() - self._last_report_at) * 1000)
        return {
            "connected": self._connected,
            "enabled": self._enabled,
            "captureSuspended": self._capture_suspended,
            "productId": None if self._product_id is None else f"{self._product_id:04X}",
            "pressed": sorted(self._pressed),
            "axes": dict(self._axes),
            "stickDirections": {
                "active": sorted(self._stick_directions),
                "activationThreshold": STICK_ACTIVATION_THRESHOLD,
                "releaseThreshold": STICK_RELEASE_THRESHOLD,
            },
            "mappings": {button: list(codes) for button, codes in self._mappings.items()},
            "touchpadGestures": {
                **self._touchpad_gestures,
                "backend": "virtual-hid",
                "driverAvailable": virtual_touchpad_available(),
                "active": self._gesture_tracking,
                "fired": self._gesture_fired,
                "startX": self._gesture_start_x,
                "startY": self._gesture_start_y,
                "currentX": self._gesture_last_x,
                "currentY": self._gesture_last_y,
                "lastGesture": self._last_gesture,
                "lastGestureAt": self._last_gesture_at,
                "muteCount": self._mute_count,
                "lastMuteAt": self._last_mute_at,
                "switchMode": self._last_touchpad_switch_mode,
                "switchError": self._last_touchpad_switch_error,
            },
            "reports": self._reports,
            "reportAgeMs": age_ms,
            "lastError": self._last_error,
            "dispatchCount": self._dispatch_count,
            "lastDispatchedButton": self._last_dispatched_button,
            "lastShortcut": list(self._last_shortcut),
            "lastDispatchAt": self._last_dispatch_at,
            "lastInjectionError": self._last_injection_error,
            "configPath": self._config_path,
            "configError": self._config_error,
            "injectionMode": "scan-code-batch",
        }

    def _press_binding_locked(self, button: str) -> None:
        codes = self._mappings.get(button)
        if not codes:
            return
        if len(codes) == 1 and codes[0] in MAPPING_ACTIONS:
            if codes[0] == "CodexDictation":
                focus_or_launch_codex()
                time.sleep(CODEX_FOCUS_SHORTCUT_DELAY_SECONDS)
                down_codes = [code for code in CODEX_DICTATION_CODES if self._key_counts.get(code, 0) == 0]
                send_keyboard_codes(down_codes, False)
                for code in CODEX_DICTATION_CODES:
                    self._key_counts[code] = self._key_counts.get(code, 0) + 1
                self._active_bindings[button] = list(CODEX_DICTATION_CODES)
                self._record_dispatch_locked(button, codes)
                return
            if codes[0] == "CodexSmartDelete":
                self._smart_delete_started[button] = time.monotonic()
                self._smart_delete_long_fired.discard(button)
                return
            self._run_mapping_action_locked(codes[0])
            if codes[0] in {"MouseWheelUp", "MouseWheelDown"}:
                self._repeat_action_next[button] = time.monotonic() + STICK_SCROLL_INITIAL_DELAY_SECONDS
            self._record_dispatch_locked(button, codes)
            return
        down_codes = [code for code in codes if self._key_counts.get(code, 0) == 0]
        send_keyboard_codes(down_codes, False)
        for code in codes:
            self._key_counts[code] = self._key_counts.get(code, 0) + 1
        self._active_bindings[button] = list(codes)
        self._dispatch_count += 1
        self._last_dispatched_button = button
        self._last_shortcut = list(codes)
        self._last_dispatch_at = time.time()
        self._last_injection_error = None

    def _run_mapping_action_locked(self, action: str) -> None:
        if action == "CodexFocus":
            focus_or_launch_codex()
            return
        if action == "CodexDictation":
            focus_or_launch_codex()
            time.sleep(CODEX_FOCUS_SHORTCUT_DELAY_SECONDS)
            self._tap_codes_locked(CODEX_DICTATION_CODES, CODEX_DICTATION_TAP_SECONDS)
            return
        if action == "MouseWheelUp":
            send_mouse_wheel(WHEEL_DELTA)
            return
        if action == "MouseWheelDown":
            send_mouse_wheel(-WHEEL_DELTA)
            return
        if action == "CodexModelNext":
            self._codex_model_index = (self._codex_model_index + 1) % 3
        elif action == "CodexModelPrevious":
            self._codex_model_index = (self._codex_model_index - 1) % 3
        else:
            raise ValueError(f"unknown mapping action: {action}")

        self._tap_codes_locked(["ControlLeft", "ShiftLeft", "KeyM"])
        time.sleep(0.08)
        self._tap_codes_locked(["Home"])
        for _ in range(self._codex_model_index):
            self._tap_codes_locked(["ArrowDown"])
        time.sleep(0.04)
        self._tap_codes_locked(["Enter"])

    def _release_binding_locked(self, button: str) -> None:
        mapped_codes = self._mappings.get(button, [])
        if mapped_codes == ["CodexSmartDelete"]:
            started = self._smart_delete_started.pop(button, None)
            long_fired = button in self._smart_delete_long_fired
            self._smart_delete_long_fired.discard(button)
            if started is not None and not long_fired:
                self._tap_codes_locked(["Backspace"])
                self._record_dispatch_locked(button, ["Backspace"])
            return
        self._repeat_action_next.pop(button, None)
        codes = list(reversed(self._active_bindings.pop(button, [])))
        up_codes = [code for code in codes if self._key_counts.get(code, 0) <= 1]
        try:
            send_keyboard_codes(up_codes, True)
        finally:
            for code in codes:
                count = self._key_counts.get(code, 0)
                if count <= 1:
                    self._key_counts.pop(code, None)
                else:
                    self._key_counts[code] = count - 1

    def _release_all_locked(self) -> None:
        for button in list(self._active_bindings):
            try:
                self._release_binding_locked(button)
            except Exception as error:
                self._last_injection_error = str(error)
        self._active_bindings.clear()
        self._key_counts.clear()
        self._smart_delete_started.clear()
        self._smart_delete_long_fired.clear()
        self._repeat_action_next.clear()

    def _process_smart_delete_locked(self, mapping_pressed: set[str]) -> None:
        now = time.monotonic()
        for button, started in list(self._smart_delete_started.items()):
            if button not in mapping_pressed or button in self._smart_delete_long_fired:
                continue
            if now - started < SMART_DELETE_HOLD_SECONDS:
                continue
            self._tap_codes_locked(["ControlLeft", "KeyA"])
            self._tap_codes_locked(["Backspace"])
            self._smart_delete_long_fired.add(button)
            self._record_dispatch_locked(button, ["CodexClearInput"])

    def _process_repeat_actions_locked(self, mapping_pressed: set[str]) -> None:
        now = time.monotonic()
        for button, next_at in list(self._repeat_action_next.items()):
            if button not in mapping_pressed:
                self._repeat_action_next.pop(button, None)
                continue
            if now < next_at:
                continue
            codes = self._mappings.get(button, [])
            if len(codes) != 1 or codes[0] not in {"MouseWheelUp", "MouseWheelDown"}:
                self._repeat_action_next.pop(button, None)
                continue
            self._run_mapping_action_locked(codes[0])
            self._record_dispatch_locked(button, codes)
            self._repeat_action_next[button] = now + STICK_SCROLL_REPEAT_SECONDS

    def _reset_gesture_locked(self) -> None:
        self._gesture_tracking = False
        self._gesture_fired = False
        self._gesture_touch_id = None
        self._gesture_start_x = None
        self._gesture_start_y = None
        self._gesture_last_x = None
        self._gesture_last_y = None

    def _tap_codes_locked(self, codes: list[str], hold_seconds: float = 0.0) -> None:
        down_codes = [code for code in codes if self._key_counts.get(code, 0) == 0]
        send_keyboard_codes(down_codes, False)
        if hold_seconds > 0:
            time.sleep(hold_seconds)
        send_keyboard_codes(list(reversed(down_codes)), True)

    def _tap_shortcut_locked(self, action: str, codes: list[str]) -> None:
        if len(codes) == 1 and codes[0] in MAPPING_ACTIONS:
            if codes[0] == "CodexSmartDelete":
                self._tap_codes_locked(["Backspace"])
                self._record_dispatch_locked(action, ["Backspace"])
                return
            self._run_mapping_action_locked(codes[0])
            self._record_dispatch_locked(action, codes)
            return
        self._tap_codes_locked(codes)
        self._record_dispatch_locked(action, codes)

    def _record_dispatch_locked(self, action: str, codes: list[str]) -> None:
        self._dispatch_count += 1
        self._last_dispatched_button = action
        self._last_shortcut = list(codes)
        self._last_dispatch_at = time.time()
        self._last_injection_error = None

    def _process_touchpad_gesture_locked(
        self,
        pressed: set[str],
        axes: dict[str, object],
    ) -> None:
        if not self._enabled or not self._touchpad_gestures["enabled"]:
            self._reset_gesture_locked()
            return
        if not axes.get("touchActive"):
            self._reset_gesture_locked()
            return
        if self._gesture_fired:
            return

        touch_id = int(axes["touchId"])
        touch_x = int(axes["touchX"])
        touch_y = int(axes["touchY"])
        if not self._gesture_tracking or touch_id != self._gesture_touch_id:
            self._gesture_tracking = True
            self._gesture_touch_id = touch_id
            self._gesture_start_x = touch_x
            self._gesture_start_y = touch_y
            self._gesture_last_x = touch_x
            self._gesture_last_y = touch_y
            return

        self._gesture_last_x = touch_x
        self._gesture_last_y = touch_y
        delta_x = touch_x - int(self._gesture_start_x)
        delta_y = touch_y - int(self._gesture_start_y)
        threshold = int(self._touchpad_gestures["threshold"])
        if abs(delta_x) < threshold or abs(delta_x) < abs(delta_y) * 1.2:
            return

        direction = "right" if delta_x > 0 else "left"
        action = f"touchpad_swipe_{direction}"
        codes = TOUCHPAD_GESTURE_SHORTCUTS[direction]
        switch_mode = None
        if self._touchpad_swipe_handler is not None:
            try:
                switch_mode = self._touchpad_swipe_handler(direction)
            except Exception:
                switch_mode = None
        if switch_mode == "touch-injection":
            self._record_dispatch_locked(action, codes)
            self._last_touchpad_switch_error = None
        elif switch_mode == "driver-required":
            self._last_touchpad_switch_error = (
                "Native Precision Touchpad gestures require a virtual HID touchpad driver; "
                "touchscreen and keyboard fallbacks are disabled"
            )
        else:
            switch_mode = "unavailable"
            self._last_touchpad_switch_error = "Windows touch injection unavailable; keyboard fallback disabled"
        self._last_touchpad_switch_mode = switch_mode
        if switch_mode == "touch-injection" and self._touchpad_gestures["muteOnSwitch"]:
            self._tap_codes_locked(["VolumeMute"])
            self._mute_count += 1
            self._last_mute_at = time.time()
        self._gesture_fired = True
        self._last_gesture = direction
        self._last_gesture_at = time.time()

    def _process_report(self, report: bytes) -> None:
        pressed, axes = parse_dualsense_usb_input(report)
        if self._trigger_observer is not None:
            trigger_overrides = self._trigger_observer(axes)
            for button, is_pressed in trigger_overrides.items():
                pressed.discard(button)
                if is_pressed:
                    pressed.add(button)
        with self._lock:
            self._stick_directions = resolve_stick_directions(axes, self._stick_directions)
            pressed.update(self._stick_directions)
            mapping_pressed = set(pressed)
            touchpad_button_pressed = "touchpad" in pressed
            if self._touchpad_gestures["enabled"]:
                mapping_pressed.discard("touchpad")
            released = self._mapping_pressed - mapping_pressed
            newly_pressed = mapping_pressed - self._mapping_pressed
            if self._enabled and not self._capture_suspended:
                for button in released:
                    try:
                        self._release_binding_locked(button)
                    except Exception as error:
                        self._last_injection_error = str(error)
                for button in newly_pressed:
                    try:
                        self._press_binding_locked(button)
                    except Exception as error:
                        self._last_injection_error = str(error)
                try:
                    self._process_smart_delete_locked(mapping_pressed)
                    self._process_repeat_actions_locked(mapping_pressed)
                except Exception as error:
                    self._last_injection_error = str(error)
                try:
                    self._process_touchpad_gesture_locked(pressed, axes)
                except Exception as error:
                    self._last_injection_error = str(error)
                if self._touchpad_gestures["enabled"]:
                    if touchpad_button_pressed and not self._touchpad_button_was_pressed:
                        self._touchpad_click_suppressed = False
                    if touchpad_button_pressed and self._gesture_fired:
                        self._touchpad_click_suppressed = True
                    if not touchpad_button_pressed and self._touchpad_button_was_pressed:
                        codes = self._mappings.get("touchpad", [])
                        if codes and not self._touchpad_click_suppressed:
                            try:
                                self._tap_shortcut_locked("touchpad", codes)
                            except Exception as error:
                                self._last_injection_error = str(error)
                        self._touchpad_click_suppressed = False
                    self._touchpad_button_was_pressed = touchpad_button_pressed
                else:
                    self._touchpad_button_was_pressed = False
                    self._touchpad_click_suppressed = False
            else:
                self._reset_gesture_locked()
            self._pressed = pressed
            self._mapping_pressed = mapping_pressed
            self._axes = axes
            self._reports += 1
            self._last_report_at = time.monotonic()
            self._last_error = None

    def _set_disconnected(self, error: str | None = None) -> None:
        with self._lock:
            self._release_all_locked()
            self._pressed.clear()
            self._mapping_pressed.clear()
            self._stick_directions.clear()
            self._reset_gesture_locked()
            self._connected = False
            self._product_id = None
            self._last_error = error

    def _run(self) -> None:
        while True:
            handle: int | None = None
            try:
                device = find_dualsense_usb()
                if device is None:
                    self._set_disconnected(None)
                    time.sleep(1)
                    continue
                path, product_id = device
                handle = open_handle(path, GENERIC_READ)
                if handle is None:
                    raise RuntimeError("DualSense input interface is held by another application")
                caps = caps_for(handle)
                if caps is None or caps.InputReportByteLength < 11:
                    raise RuntimeError("DualSense input report is unavailable")
                report_length = caps.InputReportByteLength
                with self._lock:
                    self._connected = True
                    self._product_id = product_id
                    self._last_error = None
                while True:
                    buffer = (ctypes.c_ubyte * report_length)()
                    read = wintypes.DWORD()
                    if not kernel32.ReadFile(handle, buffer, report_length, ctypes.byref(read), None):
                        raise ctypes.WinError(ctypes.get_last_error())
                    if read.value:
                        self._process_report(bytes(buffer[:read.value]))
            except Exception as error:
                self._set_disconnected(str(error))
                time.sleep(1)
            finally:
                if handle is not None:
                    kernel32.CloseHandle(handle)


def open_dualsense_output() -> tuple[int, int]:
    device = find_dualsense_usb()
    if device is None:
        raise RuntimeError("No writable DualSense USB HID output interface was found")
    path, product_id = device
    handle = open_handle(path, GENERIC_READ | GENERIC_WRITE)
    if handle is None:
        raise RuntimeError("DualSense is currently held by another application")
    return handle, product_id


def build_lighting_report(
    config: dict[str, int | str],
    intensity: float = 1.0,
    *,
    triggers: dict[str, dict[str, int | str]] | None = None,
    haptics_active: bool = False,
    motor_right: int = 0,
    motor_left: int = 0,
) -> bytearray:
    intensity = max(0.0, min(1.0, intensity))
    brightness = int(config["brightness"])
    player_leds = int(config["playerLeds"])
    report = bytearray(DS5_USB_OUTPUT_LENGTH)
    report[0] = DS5_USB_REPORT_ID
    # Full USB report includes ID 0x02 at byte 0. The rest is the 47-byte
    # DualSense common output block, whose RGB values are at bytes 45..47.
    if haptics_active:
        report[1] |= DS5_VALID_FLAG0_COMPATIBLE_VIBRATION | DS5_VALID_FLAG0_HAPTICS_SELECT
        report[3] = clamp_byte(motor_right)
        report[4] = clamp_byte(motor_left)
    if triggers is not None:
        report[1] |= DS5_VALID_FLAG0_RIGHT_TRIGGER | DS5_VALID_FLAG0_LEFT_TRIGGER
        report[11:22] = build_trigger_effect(triggers["right"])
        report[22:33] = build_trigger_effect(triggers["left"])
    report[2] = DS5_VALID_FLAG1_LIGHTBAR | DS5_VALID_FLAG1_PLAYER_LEDS
    report[43] = 0 if brightness == 0 else 1 if brightness < 34 else 2 if brightness < 67 else 3
    report[44] = player_leds
    report[45:48] = bytes((round(int(config[channel]) * intensity) for channel in ("red", "green", "blue")))
    return report


def build_shutdown_report(config: dict[str, int | str]) -> bytearray:
    """Release adaptive triggers and motors before closing the HID handle."""
    return build_lighting_report(
        config,
        triggers=normalize_triggers({}),
        haptics_active=True,
        motor_right=0,
        motor_left=0,
    )


def write_report(handle: int, report: bytearray) -> None:
    written = wintypes.DWORD()
    raw_report = (ctypes.c_ubyte * len(report)).from_buffer(report)
    if not kernel32.WriteFile(handle, raw_report, len(report), ctypes.byref(written), None):
        raise ctypes.WinError(ctypes.get_last_error())
    if written.value != len(report):
        raise RuntimeError(f"Only wrote {written.value} of {len(report)} bytes")


class LightEffectEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop_event: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._product_id: int | None = None
        self._config = normalize_lighting(CODEX_LIGHT_PROFILES["idle"])
        self._config_started_at = time.monotonic()
        self._last_error: str | None = None
        self._haptic_started_at: float | None = None
        self._recoil_started_at: float | None = None
        self._recoil_strength = 8
        self._last_recoil_side: str | None = None
        self._last_recoil_at: float | None = None
        self._last_recoil_monotonic_at: float | None = None
        self._suppressed_status_pulses = 0
        self._last_suppressed_status_pulse_at: float | None = None
        self._trigger_armed = {"left": True, "right": True}
        self._triggers = normalize_triggers({})

    def apply(self, payload: dict[str, object]) -> dict[str, int | str | bool]:
        config = normalize_lighting(payload)
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                self._config = config
                self._config_started_at = time.monotonic()
                self._last_error = None
                return {**config, "productId": self._product_id, "running": True}
        self.stop()
        handle, product_id = open_dualsense_output()
        stop_event = threading.Event()
        thread = threading.Thread(target=self._run, args=(handle, stop_event), name="ds5-light-effect", daemon=True)
        with self._lock:
            self._stop_event = stop_event
            self._thread = thread
            self._product_id = product_id
            self._config = config
            self._config_started_at = time.monotonic()
            self._last_error = None
            self._haptic_started_at = None
            self._recoil_started_at = None
        thread.start()
        return {**config, "productId": product_id, "running": True}

    def stop(self) -> None:
        with self._lock:
            stop_event = self._stop_event
            thread = self._thread
            self._stop_event = None
            self._thread = None
            self._product_id = None
            self._haptic_started_at = None
            self._recoil_started_at = None
        if stop_event is not None:
            stop_event.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1)

    def last_error(self) -> str | None:
        with self._lock:
            return self._last_error

    def trigger_status(self) -> dict[str, object]:
        with self._lock:
            return {
                "left": dict(self._triggers["left"]),
                "right": dict(self._triggers["right"]),
                "available": self._thread is not None and self._thread.is_alive(),
                "lastError": self._last_error,
                "recoil": {
                    "enabled": True,
                    "active": self._recoil_started_at is not None,
                    "lastSide": self._last_recoil_side,
                    "lastAt": self._last_recoil_at,
                    "priority": "high",
                    "priorityHoldoffMs": round(RECOIL_PRIORITY_HOLDOFF_SECONDS * 1000),
                    "suppressedStatusPulses": self._suppressed_status_pulses,
                    "lastSuppressedAt": self._last_suppressed_status_pulse_at,
                },
                "mappingGate": "weapon-end-breakpoint",
            }

    def configure_triggers(self, payload: dict[str, object]) -> dict[str, object]:
        triggers = normalize_triggers(payload)
        with self._lock:
            self._triggers = triggers
            self._trigger_armed = {"left": True, "right": True}
            running = self._thread is not None and self._thread.is_alive()
        if not running:
            self.apply(CODEX_LIGHT_PROFILES["idle"])
        return self.trigger_status()

    def trigger_double_pulse(self) -> bool:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                raise RuntimeError("No active DualSense output stream")
            now = time.monotonic()
            if (
                self._last_recoil_monotonic_at is not None
                and now - self._last_recoil_monotonic_at < RECOIL_PRIORITY_HOLDOFF_SECONDS
            ):
                self._suppressed_status_pulses += 1
                self._last_suppressed_status_pulse_at = time.time()
                return False
            self._haptic_started_at = now
            return True

    def observe_trigger_axes(self, axes: dict[str, float]) -> dict[str, bool]:
        now = time.monotonic()
        trigger_overrides: dict[str, bool] = {}
        with self._lock:
            for side, axis_name, status_name in (
                ("left", "leftTrigger", "leftTriggerEffectStatus"),
                ("right", "rightTrigger", "rightTriggerEffectStatus"),
            ):
                config = self._triggers[side]
                if config["mode"] != "weapon":
                    self._trigger_armed[side] = True
                    continue
                button = "l2" if side == "left" else "r2"
                position = max(0.0, min(1.0, float(axes.get(axis_name, 0.0))))
                start_threshold = int(config["start"]) / 10
                effect_status = int(axes.get(status_name, 0))
                if not self._trigger_armed[side]:
                    if position <= max(0.0, start_threshold - 0.03):
                        self._trigger_armed[side] = True
                        trigger_overrides[button] = False
                    else:
                        trigger_overrides[button] = True
                    continue
                # Weapon status: 0 before the resistance section, 1 while in
                # it, and 2 after the physical breakpoint has been crossed.
                if effect_status < 2:
                    trigger_overrides[button] = False
                    continue
                self._trigger_armed[side] = False
                trigger_overrides[button] = True
                self._recoil_started_at = now
                self._recoil_strength = int(config["strength"])
                self._last_recoil_side = side
                self._last_recoil_at = time.time()
                self._last_recoil_monotonic_at = now
                # Recoil owns the motors. A lower-priority status pulse already
                # in progress is discarded instead of resuming after the shot.
                self._haptic_started_at = None
        return trigger_overrides

    def _intensity(self, config: dict[str, int | str], elapsed: float) -> float:
        if config["effect"] == "static":
            return 1.0
        speed = int(config["speed"]) - 1
        if config["effect"] == "blink":
            return 1.0 if elapsed % BLINK_PERIOD_SECONDS[speed] < BLINK_PERIOD_SECONDS[speed] / 2 else 0.0
        phase = elapsed / BREATHE_PERIOD_SECONDS[speed] * math.tau - math.pi / 2
        return 0.06 + 0.94 * (math.sin(phase) + 1) / 2

    def _haptic_frame(self, now: float) -> tuple[bool, int, int]:
        with self._lock:
            started_at = self._haptic_started_at
            recoil_started_at = self._recoil_started_at
            recoil_strength = self._recoil_strength
        if recoil_started_at is not None:
            recoil_elapsed = now - recoil_started_at
            scale = max(1, min(8, recoil_strength)) / 8
            if recoil_elapsed < RECOIL_STRIKE_END_SECONDS:
                return True, round(RECOIL_RIGHT_MOTOR * scale), round(RECOIL_LEFT_MOTOR * scale)
            if recoil_elapsed < RECOIL_SETTLE_END_SECONDS:
                return True, 0, 0
            with self._lock:
                if self._recoil_started_at == recoil_started_at:
                    self._recoil_started_at = None
        if started_at is None:
            return False, 0, 0
        elapsed = now - started_at
        if elapsed < HAPTIC_PULSE_END_SECONDS:
            return True, HAPTIC_RIGHT_MOTOR, HAPTIC_LEFT_MOTOR
        if elapsed < HAPTIC_SECOND_PULSE_START_SECONDS:
            return True, 0, 0
        if elapsed < HAPTIC_SECOND_PULSE_END_SECONDS:
            return True, HAPTIC_RIGHT_MOTOR, HAPTIC_LEFT_MOTOR
        if elapsed < HAPTIC_SETTLE_END_SECONDS:
            return True, 0, 0
        with self._lock:
            if self._haptic_started_at == started_at:
                self._haptic_started_at = None
        return False, 0, 0

    def _run(self, handle: int, stop_event: threading.Event) -> None:
        config = normalize_lighting(CODEX_LIGHT_PROFILES["idle"])
        try:
            while not stop_event.is_set():
                now = time.monotonic()
                haptics_active, motor_right, motor_left = self._haptic_frame(now)
                with self._lock:
                    config = dict(self._config)
                    config_started_at = self._config_started_at
                    triggers = {
                        "left": dict(self._triggers["left"]),
                        "right": dict(self._triggers["right"]),
                    }
                write_report(handle, build_lighting_report(
                    config,
                    self._intensity(config, now - config_started_at),
                    triggers=triggers,
                    haptics_active=haptics_active,
                    motor_right=motor_right,
                    motor_left=motor_left,
                ))
                stop_event.wait(FRAME_INTERVAL_SECONDS)
        except Exception as error:
            with self._lock:
                self._last_error = str(error)
        finally:
            try:
                write_report(handle, build_shutdown_report(config))
            except Exception:
                pass
            kernel32.CloseHandle(handle)


class KeyboardCaptureEngine:
    """Capture a shortcut globally while preventing it from reaching Windows apps."""

    def __init__(self, suspend_mapping: Callable[[bool], None]) -> None:
        self._lock = threading.RLock()
        self._suspend_mapping = suspend_mapping
        self._active = False
        self._blocking = False
        self._pressed: set[str] = set()
        self._codes: list[str] = []
        self._result: list[str] | None = None
        self._last_error: str | None = None
        self._deadline: float | None = None
        self._timer: threading.Timer | None = None
        self._hook: int | None = None
        self._thread_id: int | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._callback = LowLevelKeyboardProc(self._hook_proc)

    def start(self) -> None:
        with self._lock:
            if self._thread is not None:
                return
            self._thread = threading.Thread(target=self._run, name="keyboard-shortcut-capture", daemon=True)
            self._thread.start()
        if not self._ready.wait(2):
            raise RuntimeError("keyboard capture hook did not start")
        with self._lock:
            if self._last_error:
                raise RuntimeError(self._last_error)

    def stop(self) -> None:
        with self._lock:
            self._clear_timer_locked()
            hook = self._hook
            thread_id = self._thread_id
            self._hook = None
            self._thread_id = None
            self._active = False
            self._blocking = False
            self._pressed.clear()
            self._result = None
        self._suspend_mapping(False)
        if hook:
            user32.UnhookWindowsHookEx(hook)
        if thread_id:
            user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)
        self._stopped.wait(2)

    def begin(self) -> dict[str, object]:
        with self._lock:
            if not self._hook:
                raise RuntimeError(self._last_error or "keyboard capture hook is unavailable")
            self._clear_timer_locked()
            self._active = True
            self._blocking = True
            self._pressed.clear()
            self._codes = []
            self._result = None
            self._last_error = None
            self._deadline = time.monotonic() + KEY_CAPTURE_TIMEOUT_SECONDS
            self._timer = threading.Timer(KEY_CAPTURE_TIMEOUT_SECONDS, self._timeout)
            self._timer.daemon = True
            self._timer.start()
        self._suspend_mapping(True)
        return self.status()

    def cancel(self) -> dict[str, object]:
        with self._lock:
            self._clear_timer_locked()
            self._active = False
            self._blocking = False
            self._pressed.clear()
            self._codes = []
            self._result = None
            self._deadline = None
        self._suspend_mapping(False)
        return self.status()

    def consume(self) -> dict[str, object]:
        with self._lock:
            result = None if self._result is None else list(self._result)
            if result is not None:
                self._clear_timer_locked()
                self._result = None
                self._deadline = None
        if result is not None:
            self._suspend_mapping(False)
        return {**self.status(), "result": result}

    def status(self) -> dict[str, object]:
        with self._lock:
            remaining = None if self._deadline is None else max(0, round((self._deadline - time.monotonic()) * 1000))
            return {
                "available": bool(self._hook),
                "active": self._active,
                "blocking": self._blocking,
                "codes": list(self._codes),
                "ready": self._result is not None,
                "remainingMs": remaining,
                "lastError": self._last_error,
            }

    def process_event(self, code: str | None, key_down: bool, injected: bool = False) -> bool:
        """Return whether the keyboard message must be swallowed (also unit-testable)."""
        with self._lock:
            if not self._blocking:
                return False
            if injected:
                return True
            if code is None:
                return True
            if key_down:
                if code in self._pressed:
                    return True
                self._pressed.add(code)
                if self._active:
                    if code not in self._codes:
                        self._codes.append(code)
                    if code not in MODIFIER_KEY_CODES:
                        modifiers = [item for item in MODIFIER_KEY_ORDER if item in self._codes]
                        self._result = [*modifiers[:4], code]
                        self._active = False
            else:
                self._pressed.discard(code)
                if self._active and self._codes and all(item in MODIFIER_KEY_CODES for item in self._codes):
                    self._result = [item for item in MODIFIER_KEY_ORDER if item in self._codes][:5]
                    self._active = False
                if not self._active and not self._pressed:
                    self._blocking = False
            return True

    def _timeout(self) -> None:
        with self._lock:
            if not self._active and self._result is None:
                return
            self._active = False
            self._blocking = False
            self._pressed.clear()
            self._codes = []
            self._result = None
            self._deadline = None
            self._timer = None
            self._last_error = "keyboard capture timed out"
        self._suspend_mapping(False)

    def _clear_timer_locked(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _hook_proc(self, code: int, w_param: int, l_param: int) -> int:
        if code != HC_ACTION:
            return user32.CallNextHookEx(self._hook, code, w_param, l_param)
        message = int(w_param)
        if message not in {WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP}:
            return user32.CallNextHookEx(self._hook, code, w_param, l_param)
        data = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        key_code = self._code_from_hook(data)
        swallowed = self.process_event(
            key_code,
            message in {WM_KEYDOWN, WM_SYSKEYDOWN},
            bool(data.flags & LLKHF_INJECTED),
        )
        return 1 if swallowed else user32.CallNextHookEx(self._hook, code, w_param, l_param)

    @staticmethod
    def _code_from_hook(data: KBDLLHOOKSTRUCT) -> str | None:
        if data.vkCode == VK_CODES["Enter"] and data.flags & LLKHF_EXTENDED:
            return "NumpadEnter"
        return HOOK_CODES_BY_VK.get(int(data.vkCode))

    def _run(self) -> None:
        message = wintypes.MSG()
        try:
            with self._lock:
                self._thread_id = int(kernel32.GetCurrentThreadId())
                self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._callback, None, 0)
                if not self._hook:
                    self._last_error = f"SetWindowsHookExW failed: {ctypes.get_last_error()}"
                self._ready.set()
            if not self._hook:
                return
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                pass
        finally:
            with self._lock:
                hook = self._hook
                self._hook = None
                self._thread_id = None
                self._ready.set()
            if hook:
                user32.UnhookWindowsHookEx(hook)
            self._stopped.set()


effect_engine = LightEffectEngine()
mapping_engine = InputMappingEngine(
    effect_engine.observe_trigger_axes,
    perform_touchpad_swipe,
    config_path=MAPPING_CONFIG_PATH,
)
keyboard_capture = KeyboardCaptureEngine(mapping_engine.set_capture_suspended)


class CodexStatusLightEngine:
    """Maps native Codex hook events to fixed-priority light profiles."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._enabled = True
        self._state = "idle"
        self._available = False
        self._pending_requests = 0
        self._inflight_turns = 0
        self._sessions: dict[str, dict[str, object]] = {}
        self._hook_count = 0
        self._last_hook_event: str | None = None
        self._last_hook_at: float | None = None
        self._last_hook_latency_ms: int | None = None
        self._last_hook_origin: str | None = None
        self._last_hook_pid: int | None = None
        self._last_hook_argv_event: str | None = None
        self._transient_state: str | None = None
        self._transient_until = 0.0
        self._last_applied_state: str | None = None
        self._last_applied_at: float | None = None
        self._last_error: str | None = None
        self._apply_lock = threading.Lock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="codex-status-light", daemon=True)
        self._fallback_stop = threading.Event()
        self._fallback_thread: threading.Thread | None = None
        self._fallback_offsets: dict[str, int] = {}
        self._fallback_last_native_at = 0.0

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()
        if CODEX_SESSION_FALLBACK_ENABLED and (self._fallback_thread is None or not self._fallback_thread.is_alive()):
            self._fallback_thread = threading.Thread(target=self._run_session_fallback, name="codex-session-fallback", daemon=True)
            self._fallback_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._fallback_stop.set()
        self._wake_event.set()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.5)

    def _run_session_fallback(self) -> None:
        while not self._fallback_stop.is_set():
            try:
                files = []
                if os.path.isdir(CODEX_SESSION_ROOT):
                    for root, _dirs, names in os.walk(CODEX_SESSION_ROOT):
                        files.extend(os.path.join(root, name) for name in names if name.endswith(".jsonl"))
                files.sort(key=lambda path: os.path.getmtime(path), reverse=True)
                for path in files[:8]:
                    self._consume_session_file(path)
                self._expire_fallback_approvals()
            except OSError:
                pass
            self._fallback_stop.wait(CODEX_SESSION_POLL_SECONDS)

    def _expire_fallback_approvals(self) -> None:
        """Drop only synthetic approvals that were not followed by tool use."""
        now = time.time()
        expired: list[tuple[str, str]] = []
        with self._lock:
            for session_id, session in self._sessions.items():
                pending = session.get("pending", set())
                pending_meta = session.get("pendingMeta", {})
                if not isinstance(pending, set) or not isinstance(pending_meta, dict):
                    continue
                for key in list(pending):
                    metadata = pending_meta.get(str(key))
                    if not isinstance(metadata, dict) or metadata.get("origin") != "codex-session-fallback":
                        continue
                    try:
                        created_at = float(metadata.get("createdAt", session.get("updatedAt", now)))
                    except (TypeError, ValueError):
                        created_at = now
                    if now - created_at >= CODEX_FALLBACK_APPROVAL_MAX_SECONDS:
                        expired.append((session_id, str(key)))
        for session_id, key in expired:
            self.ingest({
                "event": "PostToolUse",
                "origin": "codex-session-fallback",
                "sessionId": session_id,
                "requestKey": key,
            })

    def _consume_session_file(self, path: str) -> None:
        try:
            size = os.path.getsize(path)
        except OSError:
            return
        offset = self._fallback_offsets.setdefault(path, size)
        if size < offset:
            offset = 0
        if size == offset:
            return
        try:
            with open(path, "rb") as stream:
                stream.seek(offset)
                chunk = stream.read(size - offset)
        except OSError:
            return
        # Codex can expose a growing JSONL record before its final newline is
        # written. Keep an incomplete tail for the next poll instead of
        # advancing past a record that cannot be parsed yet.
        complete_through = chunk.rfind(b"\n")
        if complete_through < 0:
            return
        chunk = chunk[:complete_through + 1]
        self._fallback_offsets[path] = offset + complete_through + 1
        session_id = os.path.basename(path)[:128]
        for raw_line in chunk.splitlines():
            try:
                record = json.loads(raw_line.decode("utf-8", errors="replace"))
            except (TypeError, ValueError):
                continue
            payload = record.get("payload") if isinstance(record, dict) else None
            event_type = str(payload.get("type", "")) if isinstance(payload, dict) else ""
            record_type = str(record.get("type", "")) if isinstance(record, dict) else ""
            call_id = str(payload.get("call_id", "")).strip() if isinstance(payload, dict) else ""
            tool_name = str(payload.get("name", "")).strip() if isinstance(payload, dict) else ""
            tool_input = str(payload.get("input", "")) if isinstance(payload, dict) else ""
            # Do not scan arbitrary transcript text.  Assistant reasoning,
            # tool arguments and patch contents routinely mention approvals.
            # Only an explicit structured record is eligible for fallback.
            structured_event = str(
                record.get("event")
                or record.get("eventType")
                or (payload.get("event") if isinstance(payload, dict) else "")
                or (payload.get("eventType") if isinstance(payload, dict) else "")
                or ""
            ).strip().lower().replace("-", "_")
            requires_approval = (
                event_type == "custom_tool_call"
                and tool_name == "exec"
                and has_escalated_shell_request(tool_input)
            )
            if requires_approval:
                self.ingest({
                    "event": "PermissionRequest",
                    "origin": "codex-session-fallback",
                    "sessionId": session_id,
                    "requestKey": call_id or f"fallback:{path}:{self._fallback_offsets[path]}",
                    "toolName": tool_name,
                })
            elif event_type == "custom_tool_call_output" and call_id:
                # A result is appended only after the approval prompt has
                # resolved and the tool has started (or was rejected). Clear
                # the matching yellow request and resume working blue.
                with self._lock:
                    pending = self._sessions.get(session_id, {}).get("pending", set())
                    has_matching_pending = isinstance(pending, set) and call_id in pending
                if has_matching_pending:
                    self.ingest({
                        "event": "PreToolUse",
                        "origin": "codex-session-fallback",
                        "sessionId": session_id,
                        "requestKey": call_id,
                        "toolName": tool_name,
                    })
                else:
                    self.ingest({
                        "event": "UserPromptSubmit",
                        "origin": "codex-session-fallback",
                        "sessionId": session_id,
                    })
            elif structured_event in {
                "permission_request", "permissionrequest", "approval_request",
                "approvalrequest", "command_execution_request_approval",
                "exec_command_approval", "request_permissions",
            }:
                self.ingest({"event": "PermissionRequest", "origin": "codex-session-fallback", "sessionId": session_id, "requestKey": f"fallback:{path}"})
            elif event_type in {"task_complete", "turn_complete"}:
                self.ingest({"event": "Stop", "origin": "codex-session-fallback", "sessionId": session_id})
            elif event_type in {"task_failed", "turn_aborted"}:
                self.ingest({"event": "Error", "origin": "codex-session-fallback", "sessionId": session_id})
            elif (
                event_type in {
                    "task_started", "response_item", "turn_context", "custom_tool_call",
                    "agent_reasoning", "token_count", "user_message", "thread_settings_applied",
                }
                or record_type in {"task_started", "turn_context", "user_message"}
            ):
                with self._lock:
                    native_recent = time.time() - self._fallback_last_native_at < 3.0
                    has_pending = bool(self._sessions.get(session_id, {}).get("pending"))
                if not native_recent:
                    # The first record after an approval is the compatibility
                    # equivalent of PreToolUse. It must resolve the yellow
                    # request before the normal working/blue state is applied.
                    event = "PreToolUse" if has_pending else "UserPromptSubmit"
                    self.ingest({"event": event, "origin": "codex-session-fallback", "sessionId": session_id})

    def configure(self, payload: dict[str, object]) -> dict[str, object]:
        if "enabled" not in payload:
            raise ValueError("enabled is required")
        with self._lock:
            self._enabled = bool(payload["enabled"])
            self._last_applied_state = None
            self._last_error = None
        self._wake_event.set()
        return self.status()

    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def status(self) -> dict[str, object]:
        with self._lock:
            profile = CODEX_LIGHT_PROFILES[self._state]
            return {
                "enabled": self._enabled,
                "available": self._available,
                "state": self._state,
                "pendingRequests": self._pending_requests,
                "inflightTurns": self._inflight_turns,
                "hookCount": self._hook_count,
                "lastHookEvent": self._last_hook_event,
                "lastHookAt": self._last_hook_at,
                "hookLatencyMs": self._last_hook_latency_ms,
                "lastAppliedState": self._last_applied_state,
                "lastAppliedAt": self._last_applied_at,
                "lastError": self._last_error,
                "lastHookOrigin": self._last_hook_origin,
                "lastHookPid": self._last_hook_pid,
                "lastHookArgvEvent": self._last_hook_argv_event,
                "transientRemainingMs": max(0, round((self._transient_until - time.time()) * 1000)),
                "transitionHaptics": "double-soft",
                "profile": profile,
                "source": (
                    "codex-session-fallback"
                    if self._last_hook_origin == "codex-session-fallback"
                    else "codex-native-hooks"
                ),
            }

    def ingest(self, payload: dict[str, object]) -> dict[str, object]:
        raw_event = str(payload.get("event", "")).strip()
        event_key = "".join(character.lower() for character in raw_event if character.isalnum())
        event = {
            "userpromptsubmit": "UserPromptSubmit",
            "pretooluse": "PreToolUse",
            "permissionrequest": "PermissionRequest",
            "posttooluse": "PostToolUse",
            "precompact": "PreCompact",
            "postcompact": "PostCompact",
            "stop": "Stop",
            "sessionend": "SessionEnd",
            "subagentstart": "SubagentStart",
            "subagentstop": "SubagentStop",
            "aftertooluse": "PostToolUse",
            "toolcompleted": "PostToolUse",
            "turncomplete": "Stop",
            "taskcomplete": "Stop",
            "responsecomplete": "Stop",
            "assistantcomplete": "Stop",
            "taskfailed": "Error",
            "turnaborted": "Error",
            "responsefailed": "Error",
        }.get(event_key, raw_event)
        session_id = str(payload.get("sessionId", "")).strip()
        if event not in {
            "UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse",
            "PreCompact", "PostCompact", "Stop", "Error", "SessionEnd", "SubagentStart", "SubagentStop",
        }:
            raise ValueError("unsupported Codex hook event")
        if not session_id or len(session_id) > 128:
            raise ValueError("valid sessionId is required")

        received_at = time.time()
        try:
            sent_at = float(payload.get("sentAt", received_at))
        except (TypeError, ValueError):
            sent_at = received_at
        origin = str(payload.get("origin") or "manual-api").strip()[:64] or "manual-api"
        if origin not in {"codex-session-fallback", "diagnostic-live"}:
            with self._lock:
                self._fallback_last_native_at = received_at
        argv_event = str(
            payload.get("argvEvent")
            or payload.get("argv_event")
            or payload.get("hookArgvEvent")
            or ""
        ).strip()[:64] or None
        try:
            hook_pid = int(payload.get("processId") or payload.get("pid"))
            if hook_pid < 1:
                hook_pid = None
        except (TypeError, ValueError):
            hook_pid = None
        identity = self._event_identity(payload)
        request_key = self._request_key(identity)
        with self._lock:
            previous_state = self._state
            previous_available = self._available
            self._available = True
            self._hook_count += 1
            self._last_hook_event = event
            self._last_hook_at = received_at
            self._last_hook_latency_ms = max(0, round((received_at - sent_at) * 1000))
            self._last_hook_origin = origin
            self._last_hook_pid = hook_pid
            self._last_hook_argv_event = argv_event
            if event not in {"Stop", "Error", "SessionEnd"}:
                self._transient_state = None
                self._transient_until = 0.0
            if event == "SessionEnd":
                self._sessions.pop(session_id, None)
            elif event == "Stop":
                # Yellow is reserved for an actual PermissionRequest. Natural
                # language in a completed response is not a reliable approval
                # signal and previously left sessions stuck in yellow.
                self._sessions.pop(session_id, None)
                self._transient_state = "complete"
                self._transient_until = received_at + CODEX_MICRO_TRANSIENT_SECONDS
            elif event == "Error":
                self._sessions.pop(session_id, None)
                self._transient_state = "error"
                self._transient_until = received_at + CODEX_MICRO_TRANSIENT_SECONDS
            elif event == "SubagentStop":
                # A subagent can finish while its parent turn is still
                # running.  Do not clear the parent session's working state.
                session = self._sessions.get(session_id)
                if session is not None:
                    session["updatedAt"] = received_at
            else:
                session = self._sessions.setdefault(session_id, {
                    "working": False,
                    "pending": set(),
                    "pendingMeta": {},
                    "updatedAt": received_at,
                })
                session["updatedAt"] = received_at
                pending = session.setdefault("pending", set())
                if not isinstance(pending, set):
                    pending = set()
                    session["pending"] = pending
                pending_meta = session.setdefault("pendingMeta", {})
                if not isinstance(pending_meta, dict):
                    pending_meta = {}
                    session["pendingMeta"] = pending_meta
                if event == "PermissionRequest":
                    request_key = self._allocate_pending_key(pending, pending_meta, request_key, identity)
                    pending.add(request_key)
                    metadata = dict(identity)
                    metadata["origin"] = origin
                    metadata["createdAt"] = received_at
                    pending_meta[request_key] = metadata
                    session["working"] = True
                elif event == "PreToolUse":
                    # Approval is pending while Codex waits for the user. Once
                    # the approved tool actually starts, resolve only the
                    # matching request so concurrent approvals remain yellow.
                    self._resolve_pending_for_event(pending, pending_meta, identity)
                    session["working"] = True
                elif event == "PostToolUse":
                    # Resolve only the completed request. Other concurrent
                    # approvals in this session must continue to hold yellow.
                    self._resolve_pending_for_event(pending, pending_meta, identity)
                    # A completed tool is not a completed turn. Codex can
                    # spend several seconds reasoning before it starts the
                    # next tool, so dropping to idle here makes the light
                    # flash green between calls. Keep working until Stop or
                    # the JSONL task_complete fallback closes the turn. Only
                    # abandoned sessions reach the 30-minute stale cleanup.
                    session["working"] = True
                elif event in {"UserPromptSubmit", "PreToolUse", "PreCompact", "PostCompact", "SubagentStart"}:
                    if event == "UserPromptSubmit":
                        # Clean up the marker created by bridge builds that
                        # inferred approval from assistant response text.
                        pending.discard("stop-waiting")
                        pending_meta.pop("stop-waiting", None)
                    session["working"] = True
            self._recompute_locked()
            state = self._state
        self._apply_if_needed(previous_state, previous_available, state)
        return self.status()

    @staticmethod
    def _value(payload: dict[str, object], *names: str) -> str:
        for name in names:
            value = payload.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()[:256]
        return ""

    @classmethod
    def _event_identity(cls, payload: dict[str, object]) -> dict[str, str]:
        return {
            "requestKey": cls._value(payload, "requestKey", "request_key"),
            "permissionRequestId": cls._value(
                payload, "permissionRequestId", "permission_request_id", "requestId", "request_id"
            ),
            "toolUseId": cls._value(payload, "toolUseId", "tool_use_id"),
            "turnId": cls._value(payload, "turnId", "turn_id"),
            "runId": cls._value(payload, "runId", "run_id", "runIdSuffix", "run_id_suffix"),
            "toolName": cls._value(payload, "toolName", "tool_name"),
        }

    @staticmethod
    def _request_key(identity: dict[str, str]) -> str:
        return str(
            identity.get("requestKey")
            or identity.get("permissionRequestId")
            or identity.get("toolUseId")
            or identity.get("runId")
            or identity.get("turnId")
            or identity.get("toolName")
            or "default"
        )[:256]

    @staticmethod
    def _allocate_pending_key(
        pending: set[object],
        pending_meta: dict[str, object],
        base_key: str,
        identity: dict[str, str],
    ) -> str:
        """Keep duplicate fallback keys distinct while deduplicating retries."""
        if base_key not in pending:
            return base_key
        existing = pending_meta.get(base_key)
        if isinstance(existing, dict) and all(
            str(existing.get(field) or "") == str(value or "")
            for field, value in identity.items()
        ):
            return base_key
        suffix = 2
        while f"{base_key}#{suffix}" in pending:
            suffix += 1
        return f"{base_key}#{suffix}"[:256]

    @staticmethod
    def _resolve_pending_for_event(
        pending: set[object],
        pending_meta: dict[str, object],
        identity: dict[str, str],
    ) -> None:
        if not pending:
            return
        # Prefer identifiers that are normally unique per request. A shared
        # turn/run id must not resolve multiple concurrent approvals, so a
        # field is used only when it yields exactly one candidate.
        strong_fields = ("permissionRequestId", "requestKey", "toolUseId", "runId", "turnId")
        matches: list[object] = []
        for field in strong_fields:
            value = identity.get(field, "")
            if not value:
                continue
            candidates: list[object] = []
            for key in pending:
                metadata = pending_meta.get(str(key))
                if isinstance(metadata, dict):
                    if str(metadata.get(field) or "") == value:
                        candidates.append(key)
                elif str(key) == value:
                    candidates.append(key)
            if len(candidates) == 1:
                matches = candidates
                break
        if not matches and len(pending) == 1:
            # Some Codex versions use different identifiers for the approval
            # callback and the subsequent tool callback. With only one pending
            # request in a session, resolving that lone request is safer than
            # leaving the indicator yellow forever. Multiple pending requests
            # require an actual shared identifier and remain untouched here.
            only = next(iter(pending))
            metadata = pending_meta.get(str(only))
            conflicting_field = any(
                isinstance(metadata, dict)
                and str(metadata.get(field) or "")
                and identity.get(field, "")
                and str(metadata.get(field) or "") != identity[field]
                for field in strong_fields
            )
            # Different identifier kinds can legitimately be used by the
            # approval and tool callbacks. A conflicting value in the same
            # field, however, proves that this is a different request.
            if not conflicting_field:
                matches.append(only)
        for key in matches:
            pending.discard(key)
            pending_meta.pop(str(key), None)

    def _recompute_locked(self, now: float | None = None) -> None:
        self._pending_requests = sum(
            len(session.get("pending", set()))
            for session in self._sessions.values()
        )
        self._inflight_turns = sum(
            1 for session in self._sessions.values() if session.get("working")
        )
        if self._pending_requests:
            self._state = "approval"
        elif self._inflight_turns:
            self._state = "working"
        elif self._transient_state and (now or time.time()) < self._transient_until:
            self._state = self._transient_state
        else:
            self._transient_state = None
            self._transient_until = 0.0
            self._state = "idle"

    def _apply_if_needed(self, previous_state: str, previous_available: bool, state: str) -> None:
        # HTTP hooks can arrive concurrently. Serialize HID stream replacement
        # and re-read the state after acquiring the lock so an older event
        # cannot overwrite a newer profile that was ingested meanwhile.
        with self._apply_lock:
            with self._lock:
                state = self._state
                enabled = self._enabled
                should_apply = enabled and (
                    self._last_applied_state != state or effect_engine.last_error() is not None
                )
                should_pulse = enabled and previous_available and previous_state != state
            if not should_apply:
                return
            try:
                effect_engine.apply(CODEX_LIGHT_PROFILES[state])
                if should_pulse:
                    effect_engine.trigger_double_pulse()
                with self._lock:
                    self._last_applied_state = state
                    self._last_applied_at = time.time()
                    self._last_error = None
            except Exception as error:
                with self._lock:
                    self._last_applied_state = None
                    self._last_error = str(error)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            now = time.time()
            with self._lock:
                previous_state = self._state
                previous_available = self._available
                stale = [
                    session_id for session_id, session in self._sessions.items()
                    if now - float(session.get("updatedAt", now)) > CODEX_HOOK_STALE_SECONDS
                ]
                for session_id in stale:
                    self._sessions.pop(session_id, None)
                transient_expired = bool(self._transient_state and now >= self._transient_until)
                if stale or transient_expired:
                    self._recompute_locked(now)
                state = self._state
            self._apply_if_needed(previous_state, previous_available, state)
            self._wake_event.wait(1.0 if self._last_error is None else 2.0)
            self._wake_event.clear()


codex_light_engine = CodexStatusLightEngine()


class ExclusiveThreadingHTTPServer(ThreadingHTTPServer):
    """Prevent two bridge processes from sharing the API port on Windows.

    ``HTTPServer`` enables ``SO_REUSEADDR`` by default.  On Windows that can
    leave an old elevated bridge and a newly started bridge listening on the
    same port, which makes state requests and hook callbacks land in different
    in-memory state machines.  Request an exclusive address before binding and
    disable address reuse so a duplicate process fails fast.
    """

    allow_reuse_address = False

    def server_bind(self) -> None:
        exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", 0x0004)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, exclusive, 1)
        except OSError:
            # Non-Windows platforms may not expose this option.  The disabled
            # ``allow_reuse_address`` still provides a single-bind guarantee.
            pass
        super().server_bind()


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "DualSenseVibeHub/2.0"
    build_id = "codex-micro-control-center-v29"
    protocol_version = "HTTP/1.1"

    def end_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_WEB_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-DS5VibeHub-Token")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        if self.headers.get("Origin", "") not in ALLOWED_WEB_ORIGINS:
            self.send_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "origin is not allowed"})
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self.send_response(HTTPStatus.TEMPORARY_REDIRECT)
            self.send_header("Location", "http://127.0.0.1:4173/")
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
            return
        # Keep the API port useful when the separate dev/static server is down.
        # The normal UI remains on :data:`WEB_PORT` for backwards compatibility.
        if self.path in {"/ui", "/ui/"}:
            self.send_response(HTTPStatus.TEMPORARY_REDIRECT)
            self.send_header("Location", f"http://{HOST}:{WEB_PORT}/")
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
            return
        if self.path == "/api/status":
            self.send_json(HTTPStatus.OK, {
                "ok": True,
                "version": RELEASE_VERSION,
                "build": self.build_id,
                "input": mapping_engine.status(),
                "keyCapture": keyboard_capture.status(),
                "codex": codex_light_engine.status(),
                "triggers": effect_engine.trigger_status(),
            })
            return
        if self.path != "/health":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        device = find_dualsense_usb()
        if device is None:
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "ready": False,
                "error": "No writable DS5 USB interface",
                "input": mapping_engine.status(),
                "codex": codex_light_engine.status(),
            })
            return
        self.send_json(HTTPStatus.OK, {
            "ready": True,
            "productId": f"{device[1]:04X}",
            "transport": "usb",
            "input": mapping_engine.status(),
            "codex": codex_light_engine.status(),
            "triggers": effect_engine.trigger_status(),
        })

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in POST_PATHS:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        validation_error = validate_post_request(
            self.path,
            self.headers.get("Origin", ""),
            self.headers.get_content_type(),
            self.headers.get("X-DS5VibeHub-Token", ""),
            BRIDGE_AUTH_TOKEN,
        )
        if validation_error is not None:
            status, message = validation_error
            self.send_json(status, {"ok": False, "error": message})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 2 <= length <= 4096:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            if self.path == "/api/lighting":
                if codex_light_engine.enabled():
                    self.send_json(HTTPStatus.CONFLICT, {
                        "ok": False,
                        "error": "Disable Codex status lighting before applying manual lighting",
                    })
                    return
                result = effect_engine.apply(payload)
                self.send_json(HTTPStatus.OK, {"ok": True, "applied": result})
            elif self.path == "/api/codex-lighting":
                result = codex_light_engine.configure(payload)
                self.send_json(HTTPStatus.OK, {"ok": True, "codex": result})
            elif self.path == "/api/codex-hook":
                result = codex_light_engine.ingest(payload)
                self.send_json(HTTPStatus.OK, {"ok": True, "codex": result})
            elif self.path == "/api/haptics":
                pattern = str(payload.get("pattern", "double-soft"))
                if pattern != "double-soft":
                    raise ValueError("unsupported haptic pattern")
                played = effect_engine.trigger_double_pulse()
                self.send_json(HTTPStatus.OK, {
                    "ok": True,
                    "pattern": pattern,
                    "played": played,
                    "suppressed": not played,
                    "reason": None if played else "recoil-priority",
                })
            elif self.path == "/api/triggers":
                result = effect_engine.configure_triggers(payload)
                self.send_json(HTTPStatus.OK, {"ok": True, "triggers": result})
            elif self.path == "/api/key-capture":
                action = str(payload.get("action", ""))
                if action == "start":
                    result = keyboard_capture.begin()
                elif action == "poll":
                    result = keyboard_capture.consume()
                elif action == "cancel":
                    result = keyboard_capture.cancel()
                else:
                    raise ValueError("key capture action must be start, poll, or cancel")
                self.send_json(HTTPStatus.OK, {"ok": True, "keyCapture": result})
            elif self.path == "/api/action":
                action = str(payload.get("action", "")).strip()
                if action != "focus-codex":
                    raise ValueError("unsupported control-center action")
                focus_or_launch_codex()
                self.send_json(HTTPStatus.OK, {"ok": True, "action": action})
            else:
                result = mapping_engine.configure(payload)
                self.send_json(HTTPStatus.OK, {"ok": True, "input": result})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(error)})
        except Exception as error:  # The message is intentionally surfaced to the local UI.
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": str(error)})

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main(stop_event: threading.Event | None = None) -> None:
    global BRIDGE_AUTH_TOKEN
    BRIDGE_AUTH_TOKEN = load_or_create_bridge_token()
    mapping_engine.start()
    keyboard_capture.start()
    codex_light_engine.start()
    server = ExclusiveThreadingHTTPServer((HOST, PORT), BridgeHandler)
    print(f"DualSense VibeCoding Hub listening on http://{HOST}:{PORT} (pid={os.getpid()})")
    try:
        if stop_event is None:
            server.serve_forever()
        else:
            server.timeout = 0.25
            while not stop_event.is_set():
                server.handle_request()
    finally:
        server.server_close()
        codex_light_engine.stop()
        keyboard_capture.stop()
        effect_engine.stop()
        mapping_engine.configure({"enabled": False, "mappings": {}})


if __name__ == "__main__":
    main()
