Param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$AdminUser = "admin",
  [string]$AdminPass = "Admin123!"
)

function JsonPost {
  param($Url, $Obj, $Headers)
  $json = $Obj | ConvertTo-Json -Depth 12 -Compress
  return Invoke-RestMethod -Method Post -Uri $Url -Headers $Headers -ContentType 'application/json' -Body $json
}

function JsonGet {
  param($Url, $Headers)
  return Invoke-RestMethod -Method Get -Uri $Url -Headers $Headers
}

Write-Host "=== [1] 获取 Token ==="
$tokenResp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/users/token" -ContentType "application/x-www-form-urlencoded" -Body "username=$AdminUser&password=$AdminPass"
$H = @{ Authorization = "Bearer $($tokenResp.access_token)" }

Write-Host "=== [2] 创建设备 ==="
# 先创建一个拥有者（如果 owner_id 不是 1，需要改成你已有用户的 id；admin 自己一般是 id=1）
$device = JsonPost -Url "$BaseUrl/devices/" -Obj @{ name="smoke-dev-1"; type="camera"; owner_id=1 } -Headers $H
$deviceId = $device.id
Write-Host "设备ID:" $deviceId

Write-Host "=== [3] 写入批量事件 ==="
$events = @{
  events = @(
    @{ event_type="auth_fail"; payload=@{} },
    @{ event_type="auth_fail"; payload=@{} },
    @{ event_type="auth_fail"; payload=@{} },
    @{ event_type="auth_success"; payload=@{} },
    @{ event_type="auth_success"; payload=@{} },
    @{ event_type="policy_violation"; payload=@{ rule="block-telnet" } },
    @{ event_type="net_flow"; payload=@{ bytes_out=18000; protocol="mqtt" } },
    @{ event_type="net_flow"; payload=@{ bytes_out=25000; protocol="mqtt" } },
    @{ event_type="command"; payload=@{ cmd="reboot" } },
    @{ event_type="command"; payload=@{ cmd="factory_reset" } }
  )
}
$respEvents = JsonPost -Url "$BaseUrl/devices/$deviceId/events" -Obj $events -Headers $H
Write-Host "已写入事件条数:" $respEvents.Count

Write-Host "=== [4] 手动风险评估 ==="
$eval = Invoke-RestMethod -Method Post -Uri "$BaseUrl/risk/evaluate/$deviceId" -Headers $H
$eval | ConvertTo-Json -Depth 8

Write-Host "=== [5] 启动调度器 (20 秒间隔) ==="
JsonPost -Url "$BaseUrl/risk/scheduler/start" -Obj @{ interval_seconds = 20 } -Headers $H | Out-Null

Write-Host "等待 25 秒（让调度执行一轮）..."
Start-Sleep -Seconds 25

Write-Host "=== [6] 调度状态 ==="
$status = JsonGet -Url "$BaseUrl/risk/scheduler/status" -Headers $H
$status | ConvertTo-Json -Depth 6

Write-Host "=== [7] 风险历史（最近几条） ==="
$history = JsonGet -Url "$BaseUrl/risk/history/$deviceId" -Headers $H
$history | ConvertTo-Json -Depth 6

Write-Host "=== [8] 停止调度器 ==="
Invoke-RestMethod -Method Post -Uri "$BaseUrl/risk/scheduler/stop" -Headers $H | Out-Null

Write-Host "=== [完成] 冒烟测试完成 ==="