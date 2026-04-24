# MikroTik WIGO Agent Script
:local collectorUrl "https://wigo.gmiretzky.com:8443/api/actions/telemetry"
:local registrationToken "YOUR_TOKEN_HERE"
:local machineName [/system identity get name]

# Get Metrics
:local cpuLoad [/system resource get cpu-load]
:local freeMem [/system resource get free-memory]
:local totalMem [/system resource get total-memory]
:local ramUsage (100 - (($freeMem * 100) / $totalMem))
:local uptime [/system resource get uptime]

# Get Logs (last 5 entries)
:local logs ""
:foreach i in=[/log find] do={
    :set logs ($logs . "," . [/log get $i message])
}

:local timestamp [/system clock get date]
:set timestamp ($timestamp . "T" . [/system clock get time] . "Z")

# Report to Controller
/tool fetch url=$collectorUrl http-method=post http-header-field="Authorization: Bearer $registrationToken,Content-Type: application/json" http-data="{\"hostname\":\"$machineName\",\"data\":\"CPU: $cpuLoad%, RAM: $ramUsage%\",\"timestamp\":0,\"hmac_signature\":\"mikrotik-static-token\"}" keep-result=no
