Param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$Username = "admin",
  [string]$Password = "Admin123!",
  [int]$Devices = 3
)

function Fail($msg) { Write-Error $msg; exit 1 }

Write-Host "== Getting token =="
try {
  $tokenResp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/users/token" -ContentType "application/x-www-form-urlencoded" -Body ("username={0}&password={1}" -f $Username,$Password)
} catch { Fail "Token request failed: $($_.Exception.Message)" }
if (-not $tokenResp.access_token) { Fail "No access_token in token response." }
$H = @{ Authorization = "Bearer " + $tokenResp.access_token }

$created = @()

for ($i=1; $i -le $Devices; $i++) {
  $name = "demo-{0}-{1:yyyyMMdd-HHmmss}" -f $i,(Get-Date)
  Write-Host ("== Creating device: {0}" -f $name)
  try {
    $dev = Invoke-RestMethod -Method Post -Uri "$BaseUrl/devices/" -Headers $H -ContentType "application/json" -Body ("{{""name"":""{0}"",""type"":""sensor"",""owner_id"":3}}" -f $name)
  } catch { Fail "Create device failed: $($_.Exception.Message)" }
  $id = [int](("$($dev.id)") -replace '[^\d]','')
  $created += $id

  # 为每个设备注入不同强度事件：第一个高风险，其它低/中
  if ($i -eq 1) {
    $events = @'
{"events":[
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"policy_violation","payload":{"rule":"block-telnet"}},
 {"event_type":"net_flow","payload":{"bytes_out":30000,"protocol":"mqtt"}},
 {"event_type":"command","payload":{"cmd":"factory_reset"}}
]}
'@
  } elseif ($i -eq 2) {
    $events = @'
{"events":[
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"net_flow","payload":{"bytes_out":6000,"protocol":"http"}}
]}
'@
  } else {
    $events = @'
{"events":[
 {"event_type":"net_flow","payload":{"bytes_out":2000,"protocol":"http"}}
]}
'@
  }

  Write-Host ("== Posting events to device {0}" -f $id)
  Invoke-RestMethod -Method Post -Uri ("{0}/devices/{1}/events" -f $BaseUrl,$id) -Headers $H -ContentType "application/json" -Body $events | Out-Null
}

Write-Host "== Evaluate all devices, window=5 =="
foreach ($id in $created) {
  $eval = Invoke-RestMethod -Method Post -Uri ("{0}/risk/evaluate/{1}?window=5" -f $BaseUrl,$id) -Headers $H
  $line = "id={0} score={1} level={2}" -f $id,$eval.score,$eval.level
  Write-Host $line
}

Write-Host "Done. Created device IDs: $($created -join ', ')"