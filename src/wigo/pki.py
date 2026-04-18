import datetime
import os
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

CA_DIR = "certs/ca"
CERT_DIR = "certs/agents"

class PKIManager:
    def __init__(self):
        os.makedirs(CA_DIR, exist_ok=True)
        os.makedirs(CERT_DIR, exist_ok=True)
        self.ca_key_path = os.path.join(CA_DIR, "rootCA.key")
        self.ca_cert_path = os.path.join(CA_DIR, "rootCA.pem")

    def ensure_ca(self):
        if not os.path.exists(self.ca_key_path) or not os.path.exists(self.ca_cert_path):
            self.generate_ca()

    def generate_ca(self):
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend()
        )
        with open(self.ca_key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IL"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Center"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "WIGO"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "WIGO AI"),
            x509.NameAttribute(NameOID.COMMON_NAME, "WIGO Root CA"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=3650)
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True,
        ).sign(key, hashes.SHA256(), default_backend())

        with open(self.ca_cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

    def sign_agent_csr(self, csr_pem: str, hostname: str):
        self.ensure_ca()
        
        with open(self.ca_key_path, "rb") as f:
            ca_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())
        with open(self.ca_cert_path, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())

        csr = x509.load_pem_x509_csr(csr_pem.encode(), default_backend())
        
        cert = x509.CertificateBuilder().subject_name(
            csr.subject
        ).issuer_name(
            ca_cert.subject
        ).public_key(
            csr.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).sign(ca_key, hashes.SHA256(), default_backend())

        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
        return cert_pem, cert.serial_number

pki = PKIManager()
