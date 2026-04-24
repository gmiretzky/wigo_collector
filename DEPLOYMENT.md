# WIGO Deployment & Certificate Management

WIGO uses standard TLS for server validation and HMAC-based authentication for agents. This removes the need for managing a private CA and individual agent certificates.

## 1. Server Certificates
The WIGO Controller should be configured with a valid, trusted certificate (e.g., from Let's Encrypt or your own trusted domain).

1. **Upload Certificates**: Place your `fullchain.pem` and `privkey.pem` in a secure directory.
2. **Configure Environment**:
   ```bash
   export WIGO_SERVER_CERT=/path/to/fullchain.pem
   export WIGO_SERVER_KEY=/path/to/privkey.pem
   ```
3. **Restart Controller**: The agent interface (Port 8443) will now serve this certificate.

## 2. Agent Authentication (HMAC Handshake)
Instead of mTLS, agents use a symmetric `registration_token` to sign every request.

1. **Get Token**: From the Management Dashboard, click "Add Agent" to generate a token for a specific Hostname/IP.
2. **Handshake**: The agent uses the token to generate an HMAC-SHA256 signature of the payload and timestamp.
3. **Verification**: The server validates the signature and timestamp to ensure the request is legit and fresh.

## 3. Ubuntu Agent Deployment
1. Install requirements: `pip install httpx psutil pyyaml`
2. Configure `/etc/wigo/config.yaml` with the `registration_token` and `agent_api_url`.
3. Run the agent: `python3 wigo-agent.py`

## 4. MikroTik Integration
For MikroTik devices, the token is sent in an `Authorization` header. Ensure you are connecting over HTTPS to keep the token secure.

```routeros
/tool fetch url="https://wigo.example.com:8443/api/actions/telemetry" \
    http-method=post \
    http-header-field="Authorization: Bearer YOUR_TOKEN_HERE,Content-Type: application/json" \
    http-data="..."
```

## 5. Security Note
- Always use HTTPS for the agent API to protect the `registration_token` and telemetry data.
- Tokens can be revoked by deleting the agent or regenerating the token in the database.
