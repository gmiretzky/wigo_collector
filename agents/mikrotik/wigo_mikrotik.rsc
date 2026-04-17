# MikroTik WIGO Agent Script
:local collectorUrl "http://YOUR_COLLECTOR_IP:5000/api/agents/report"
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
# (Simplified log gathering as RouterOS script string manipulation is limited)

:local timestamp [/system clock get date]
:set timestamp ($timestamp . "T" . [/system clock get time] . "Z")

:local json "{\"machine_name\":\"$machineName\",\"timestamp\":\"$timestamp\",\"metrics\":[{\"object\":\"CPU\",\"value\":$cpuLoad,\"unit\":\"%\",\"status\":\"ok\"},{\"object\":\"RAM\",\"value\":$ramUsage,\"unit\":\"%\",\"status\":\"ok\"}],\"logs\":[]}"

/tool fetch url=$collectorUrl http-method=post http-header-field="Content-Type: application/json" http-data=$json keep-result=no
