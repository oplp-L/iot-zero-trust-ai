Param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$AdminUser = "admin",
  [string]$AdminPass = "Passw0rd!"
)

function Ensure-Success($resp, $msg) {
  if (-not $resp) { throw $msg }
}

Write-Host "===> 1) Create/Reset admin user"
$adminBody = @{ username=$AdminUser; password=$AdminPass; role="admin" } | ConvertTo-Json
$u = Invoke-RestMethod -Uri "$BaseUrl/users/" -Method Post -Body $adminBody -ContentType "application/json"
Ensure-Success $u "Fail to create admin user"
$u | ConvertTo-Json

Write-Host "===> 2) Login to get JWT"
$login = Invoke-RestMethod -Uri "$BaseUrl/users/token" -Method Post -ContentType "application/x-www-form-urlencoded" -Body "username=$AdminUser&password=$AdminPass"
$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }
$token | Out-Host

Write-Host "===> 3) Create device"
$devBody = @{ name="cam-01"; type="camera"; owner_id=$null } | ConvertTo-Json
$dev = Invoke-RestMethod -Uri "$BaseUrl/devices/" -Method Post -Headers $headers -Body $devBody -ContentType "application/json"
Ensure-Success $dev "Fail to create device"
$dev | ConvertTo-Json

Write-Host "===> 4) Ingest 5 auth_fail events (to trigger high risk)"
$eventsBody = @{
  events = @(
    @{ event_type="auth_fail"; payload=@{ src="10.0.0.2" } },
    @{ event_type="auth_fail"; payload=@{ src="10.0.0.2" } },
    @{ event_type="auth_fail"; payload=@{ src="10.0.0.2" } },
    @{ event_type="auth_fail"; payload=@{ src="10.0.0.2" } },
    @{ event_type="auth_fail"; payload=@{ src="10.0.0.2" } }
  )
} | ConvertTo-Json -Depth 5
$_ = Invoke-RestMethod -Uri "$BaseUrl/devices/$($dev.id)/events" -Method Post -Headers $headers -Body $eventsBody -ContentType "application/json"

Write-Host "===> 5) Evaluate risk"
$risk = Invoke-RestMethod -Uri "$BaseUrl/risk/evaluate/$($dev.id)?window=5" -Method Post -Headers $headers
$risk | ConvertTo-Json

Write-Host "===> 6) List actions"
$acts = Invoke-RestMethod -Uri "$BaseUrl/risk/actions/$($dev.id)" -Method Get -Headers $headers
$acts | ConvertTo-Json

Write-Host "===> Demo finished"