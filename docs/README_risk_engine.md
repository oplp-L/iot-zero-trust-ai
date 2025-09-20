# Risk Engine & Auto Response Guide

This document explains how the risk scoring engine works, how to configure it, and how to run a quick end-to-end validation (High → isolate → cooldown → restore).

See also: [docs/risk_model.md](./risk_model.md)

## 1. Overview

- Event-driven risk scoring with configurable weights and thresholds.
- Levels: low / medium / high (from score_levels).
- Auto isolate when level=high (if enabled).
- Auto restore after:
  - cooldown_seconds elapsed since last isolate
  - consecutive non-high scores (min_consecutive_non_high)
  - results within lookback_scores window and in allow_levels

## 2. Key API Endpoints

- POST /users/token
- POST /devices/
- POST /devices/{id}/events
- POST /risk/evaluate/{id}?window={minutes}
- GET  /risk/actions/{id}
- GET  /risk/config
- POST /risk/config/reload
- GET  /logs/devices/{id}

FastAPI docs are available at /docs when the server is running.

## 3. Configuration

Edit risk_config.json (or use env to point a custom path) and reload:

```
POST /risk/config/reload
GET  /risk/config
```

Template: see risk_config.example.json (copy to risk_config.json for local runs; keep risk_config.json out of git).

## 4. Quick E2E Validation (PowerShell)

1) Get token:
```powershell
$tokenResp = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/users/token" -ContentType "application/x-www-form-urlencoded" -Body "username=admin&password=Admin123!"
$H = @{ Authorization = "Bearer " + $tokenResp.access_token }
```

2) Create a fresh device:
```powershell
$dev = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/devices/" -Headers $H -ContentType "application/json" -Body '{"name":"risk-demo","type":"camera","owner_id":3}'
$deviceId = [int](("$($dev.id)") -replace '[^\d]','')
```

3) Inject high-risk events (same minute):
```powershell
Invoke-RestMethod -Method Post -Uri ("http://127.0.0.1:8000/devices/{0}/events" -f $deviceId) -Headers $H -ContentType "application/json" -Body '{"events":[
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"auth_fail","payload":{}},
 {"event_type":"policy_violation","payload":{"rule":"block-telnet"}},
 {"event_type":"net_flow","payload":{"bytes_out":30000,"protocol":"mqtt"}},
 {"event_type":"command","payload":{"cmd":"factory_reset"}}
]}'
```

4) Evaluate with window=5 → expect level=high and isolate:
```powershell
$highUrl = "http://127.0.0.1:8000/risk/evaluate/{0}?window=5" -f $deviceId
$high = Invoke-RestMethod -Method Post -Uri $highUrl -Headers $H
$high | ConvertTo-Json -Depth 6
Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:8000/risk/actions/{0}" -f $deviceId) -Headers $H | ConvertTo-Json -Depth 6
```

5) Wait 70s (cooldown 10s + window aging):
```powershell
Start-Sleep -Seconds 70
```

6) Two low evaluations (window=1) → restore appears:
```powershell
$lowUrl = "http://127.0.0.1:8000/risk/evaluate/{0}?window=1" -f $deviceId
$low1 = Invoke-RestMethod -Method Post -Uri $lowUrl -Headers $H
$low2 = Invoke-RestMethod -Method Post -Uri $lowUrl -Headers $H
Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:8000/risk/actions/{0}" -f $deviceId) -Headers $H | ConvertTo-Json -Depth 7
Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:8000/logs/devices/{0}" -f $deviceId) -Headers $H | ConvertTo-Json -Depth 6
```

## 5. Tuning Cheatsheet

- Fewer false isolates: raise high, lower some weights, increase auth_fail_min_total.
- More sensitive: lower high, lower flow_spike_ratio, raise weights.
- Faster restore: lower cooldown_seconds or min_consecutive_non_high.
- Less flapping: raise min_consecutive_non_high; adjust thresholds.