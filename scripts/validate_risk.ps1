Param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$Username = "admin",
  [string]$Password = "Admin123!"
)

function Fail($msg) { Write-Error $msg; exit 1 }

Write-Host "== Getting token =="
try {
  $tokenResp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/users/token" -ContentType "application/x-www-form-urlencoded" -Body ("username={0}&password={1}" -f $Username,$Password)
} catch { Fail "Token request failed: $($_.Exception.Message)" }
if (-not $tokenResp.access_token) { Fail "No access_token in token response." }
$H = @{ Authorization = "Bearer " + $tokenResp.access_token }

# Unique device name
$devName = "auto-restore-validate-{0:yyyyMMdd-HHmmss}" -f (Get-Date)

Write-Host "== Creating device =="
try {
  $dev = Invoke-RestMethod -Method Post -Uri "$BaseUrl/devices/" -Headers $H -ContentType "application/json" -Body ("{{""name"":""{0}"",""type"":""camera"",""owner_id"":3}}" -f $devName)
} catch { Fail "Create device failed: $($_.Exception.Message)" }
$deviceId = [int](("$($dev.id)") -replace '[^\d]','')
if (-not $deviceId) { Fail "Invalid device id." }
Write-Host ("DeviceID = {0}" -f $deviceId)

Write-Host "== Injecting events =="
$eventsBody = @'
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
try {
  Invoke-RestMethod -Method Post -Uri ("{0}/devices/{1}/events" -f $BaseUrl,$deviceId) -Headers $H -ContentType "application/json" -Body $eventsBody | Out-Null
} catch { Fail "Inject events failed: $($_.Exception.Message)" }

Write-Host "== Evaluate window=5 (expect HIGH) =="
$highUrl = "{0}/risk/evaluate/{1}?window=5" -f $BaseUrl,$deviceId
try {
  $highResp = Invoke-RestMethod -Method Post -Uri $highUrl -Headers $H
} catch { Fail "High evaluate failed: $($_.Exception.Message)" }
$highResp | ConvertTo-Json -Depth 6
if ($highResp.level -ne "high") { Fail ("Expected level=high, got: {0}" -f $highResp.level) }

Write-Host "== Check actions (expect isolate) =="
$acts1 = Invoke-RestMethod -Method Get -Uri ("{0}/risk/actions/{1}" -f $BaseUrl,$deviceId) -Headers $H
$acts1 | ConvertTo-Json -Depth 7

Write-Host "== Wait 70 seconds (cooldown + window aging) =="
Start-Sleep -Seconds 70

Write-Host "== Two low evaluations (window=1) =="
$lowUrl = "{0}/risk/evaluate/{1}?window=1" -f $BaseUrl,$deviceId
$low1 = Invoke-RestMethod -Method Post -Uri $lowUrl -Headers $H
$low1 | ConvertTo-Json -Depth 6
Start-Sleep -Seconds 2
$low2 = Invoke-RestMethod -Method Post -Uri $lowUrl -Headers $H
$low2 | ConvertTo-Json -Depth 6

Write-Host "== Check actions (expect restore) =="
$acts2 = Invoke-RestMethod -Method Get -Uri ("{0}/risk/actions/{1}" -f $BaseUrl,$deviceId) -Headers $H
$acts2 | ConvertTo-Json -Depth 7

Write-Host "== Device logs =="
$logs = Invoke-RestMethod -Method Get -Uri ("{0}/logs/devices/{1}" -f $BaseUrl,$deviceId) -Headers $H
$logs | ConvertTo-Json -Depth 6

Write-Host "OK: Validation finished."