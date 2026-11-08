$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$network = Get-Content -LiteralPath (Join-Path $taskRoot '.env.local-https\config.json') -Raw | ConvertFrom-Json
$ruleName = 'Three Tube Scanner local HTTPS'
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow `
        -Protocol TCP -LocalPort 8443,8081 -LocalAddress $network.ip `
        -RemoteAddress LocalSubnet -Profile Any | Out-Null
}
Get-NetFirewallRule -DisplayName $ruleName | Get-NetFirewallAddressFilter |
    Set-NetFirewallAddressFilter -LocalAddress $network.ip -RemoteAddress LocalSubnet
Get-NetFirewallRule -DisplayName $ruleName | Select-Object DisplayName,Enabled |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRoot 'tmp\automatic-scanner\firewall-status.json')
