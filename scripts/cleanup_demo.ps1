Param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$Username = "admin",
  [string]$Password = "Admin123!",
  [int[]]$DeviceIds
)

function Fail($msg) { Write-Error $msg; exit 1 }

if (-not $DeviceIds -or $DeviceIds.Count -eq 0) {
  Write-Error "请通过 -DeviceIds 传入要删除的设备 ID 列表，例如: -DeviceIds 18,19,20"
  exit 1
}

Write-Host "== Getting token =="
try {
  $tokenResp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/users/token" -ContentType "application/x-www-form-urlencoded" -Body ("username={0}&password={1}" -f $Username,$Password)
} catch { Fail "Token request failed: $($_.Exception.Message)" }
if (-not $tokenResp.access_token) { Fail "No access_token in token response." }
$H = @{ Authorization = "Bearer " + $tokenResp.access_token }

foreach ($id in $DeviceIds) {
  Write-Host ("== Deleting device {0} ==" -f $id)
  try {
    $resp = Invoke-RestMethod -Method Delete -Uri ("{0}/devices/{1}" -f $BaseUrl,$id) -Headers $H
    Write-Host ("Deleted device {0}: {1}" -f $id, ($resp | ConvertTo-Json -Depth 5))
  } catch {
    Write-Warning ("Delete {0} failed: {1}" -f $id, $_.Exception.Message)
  }
}

Write-Host "Done."