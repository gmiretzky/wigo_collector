import socketserver
import threading
import logging
from datetime import datetime
from src.collector.database import SessionLocal, LogEntry, Machine, SyslogMapping

logger = logging.getLogger(__name__)

class SyslogHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            if isinstance(self.request, tuple):
                # UDP
                data = self.request[0].strip().decode('utf-8', errors='ignore')
                socket = self.request[1]
            else:
                # TCP
                data = self.request.recv(1024).strip().decode('utf-8', errors='ignore')
            
            source_ip = self.client_address[0]
            self.process_log(source_ip, data)
        except Exception as e:
            logger.error(f"Error handling syslog message: {e}")

    def process_log(self, source_ip, message):
        db = SessionLocal()
        try:
            # Resolve machine name from mapping
            mapping = db.query(SyslogMapping).filter(SyslogMapping.ip_address == source_ip).first()
            machine_name = mapping.machine_name if mapping else f"Syslog-{source_ip}"
            
            # Get or create machine
            machine = db.query(Machine).filter(Machine.name == machine_name).first()
            if not machine:
                machine = Machine(name=machine_name)
                db.add(machine)
                db.commit()
                db.refresh(machine)
            
            # Create log entry
            log_entry = LogEntry(
                machine_id=machine.id,
                message=message,
                source="syslog",
                timestamp=datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.error(f"Error processing syslog from {source_ip}: {e}")
        finally:
            db.close()

class UDPSyslogServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    pass

class TCPSyslogServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

def start_syslog_server(port=514):
    try:
        udp_server = UDPSyslogServer(("0.0.0.0", port), SyslogHandler)
        threading.Thread(target=udp_server.serve_forever, daemon=True).start()
        
        tcp_server = TCPSyslogServer(("0.0.0.0", port), SyslogHandler)
        threading.Thread(target=tcp_server.serve_forever, daemon=True).start()
        
        logger.info(f"Syslog server started on port {port} (UDP & TCP)")
    except Exception as e:
        logger.error(f"Failed to start syslog server: {e}")
