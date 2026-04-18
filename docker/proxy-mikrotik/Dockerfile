FROM python:3.11-slim

WORKDIR /app

RUN pip install requests netmiko cryptography

COPY proxy_agent.py .

CMD ["python", "proxy_agent.py"]
