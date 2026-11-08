import sys

if len(sys.argv) < 2:
    print("Usage: python bin2c.py <file.dll>")
    sys.exit(1)

with open(sys.argv[1], "rb") as f:
    data = f.read()

print("unsigned char helper_dll_data[] = {")
print(", ".join("0x{:02x}".format(b) for b in data))
print("};")
print("unsigned int helper_dll_size = {};".format(len(data)))