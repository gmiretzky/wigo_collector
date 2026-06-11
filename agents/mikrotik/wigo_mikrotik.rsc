# MikroTik WIGO Agent Script
# Configure these two variables before deploying to a device:
#   collectorUrl  - the WIGO controller telemetry endpoint
#   registrationToken - the per-agent token generated in the WIGO dashboard
#
# See DEPLOYMENT.md for full setup instructions.

:local collectorUrl "https://YOUR_CONTROLLER_HOST:8443/api/actions/telemetry"
:local registrationToken "YOUR_PER_AGENT_TOKEN_HERE"
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

# Build RFC3339-ish timestamp (RouterOS format: mmm/dd/yyyy HH:MM:SS → approximate only)
:local dateStr [/system clock get date]
:local timeStr [/system clock get time]
:local timestamp ($dateStr . "T" . $timeStr . "Z")

# Note: RouterOS scripting does not support HMAC-SHA256 natively.
# The HMAC signature field is left as a placeholder; the proxy-mikrotik
# Docker container (proxy_agent.py) is the recommended path for
# authenticated telemetry from MikroTik devices.
/tool fetch url=$collectorUrl http-method=post \
    http-header-field="Authorization: Bearer $registrationToken,Content-Type: application/json" \
    http-data=("{\"hostname\":\"" . $machineName . "\",\"data\":\"CPU: " . $cpuLoad . "%, RAM: " . $ramUsage . "%, Uptime: " . $uptime . "\",\"timestamp\":0,\"nonce\":\"routeros-no-hmac\",\"hmac_signature\":\"routeros-no-hmac\"}") \
    keep-result=no
