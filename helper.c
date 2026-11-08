#include <windows.h>

__declspec(dllexport) const unsigned char* GetEncryptionKey(unsigned int* out_len) {
    static const unsigned char key[] = { 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0x00 };
    *out_len = sizeof(key);
    return key;
}

__declspec(dllexport) void DummyExport() {
    volatile int x = 42;
}
