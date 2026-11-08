# embed_dll.py
import zlib
with open("stealth_injector.dll", "rb") as f:
    data = f.read()

compressed = zlib.compress(data, level=9)

print("COMPRESSED_DLL = b'", end='')
print("".join(f"\\x{b:02x}" for b in compressed), end='')
print("'")