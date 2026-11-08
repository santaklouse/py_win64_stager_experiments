with open("shellcode.bin", "rb") as f:
    data = f.read()

print("shellcode = (")
for i in range(0, len(data), 16):
    chunk = data[i:i+16]
    print('    b"' + ''.join(f'\\x{b:02x}' for b in chunk) + '"')
print(")")
