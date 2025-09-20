Param(
  [string]$Username = "admin",
  [string]$Password = "Admin123!",
  [string]$Host = "127.0.0.1",
  [int]$Port = 8000
)

$base = "http://$Host`:$Port"
Write-Host "Base URL: $base"

# 0. Token
$tokenResp = Invoke-RestMethod -Method Post -Uri "$base/users/token" -ContentType "application/x-www-form-urlencoded" -Body "username=$Username&password=$Password"
$H = @{ Authorization = "Bearer " + $tokenResp.access_token }

# 1. 确认配置
$config = Invoke-RestMethod -Method Get -Uri "$base/risk/config" -Headers $H
Write-Host "cooldown_seconds:" $config.auto_response.restore.cooldown_seconds

# 2. 创建设备
$dev = Invoke-RestMethod -Method Post -Uri "$base/devices/" -Headers $H -ContentType "application/json" -Body '{"name":"e2e-risk-demo","type":"camera","owner_id":3}'
$deviceId = [int](("$($dev.id)") -replace '[^\d]','')
Write-Host "DeviceID = $deviceId"

# 3. 注入高风险事件（5 fail + violation + net_flow + command）
Invoke-RestMethod -Method Post -Uri "$base/devices/$deviceId/events" -Headers $H -ContentType "application/json" -Body '{"events":[
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"policy_violation","payload":{"rule":"block-telnet"}},
 {"event_type":"net_flow","payload":{"bytes_out":30000,"protocol":"mqtt"}},
 {"event_type":"command","payload":{"cmd":"factory_reset"}}
]}'

# 4. 高风险评估（应 high）
$evalHighUrl = "$base/risk/evaluate/$deviceId?window=5"
$high = Invoke-RestMethod -Method Post -Uri $evalHighUrl -Headers $H
Write-Host "High score:" $high.score " level:" $high.level

# 5. 查看动作（应 isolate）
$acts1 = Invoke-RestMethod -Method Get -Uri "$base/risk/actions/$deviceId" -Headers $H
Write-Host "Actions after high:" ($acts1 | ConvertTo-Json -Depth 6)

# 6. 等待 70s（冷却10 + 事件老化60）
Start-Sleep -Seconds 70

# 7. 两次低风险评估（应 low）
$lowUrl = "$base/risk/evaluate/$deviceId?window=1"
$low1 = Invoke-RestMethod -Method Post -Uri $lowUrl -Headers $H
$low2 = Invoke-RestMethod -Method Post -Uri $lowUrl -Headers $H
Write-Host "Low1:" ($low1 | ConvertTo-Json -Depth 6)
Write-Host "Low2:" ($low2 | ConvertTo-Json -Depth 6)

# 8. 查看动作（应 restore）
$acts2 = Invoke-RestMethod -Method Get -Uri "$base/risk/actions/$deviceId" -Headers $H
Write-Host "Actions after restore:" ($acts2 | ConvertTo-Json -Depth 7)

# 9. 查看日志
$logs = Invoke-RestMethod -Method Get -Uri "$base/logs/devices/$deviceId" -Headers $H
Write-Host "Logs:" ($logs | ConvertTo-Json -Depth 6)