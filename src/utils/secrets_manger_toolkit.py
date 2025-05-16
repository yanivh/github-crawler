import json
import boto3
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from typing import Any, Dict

class SecretsManager:
    """
    A class to manage secrets using AWS Secrets Manager.
    """

    def __init__(self) -> None:
        """
        Initialize the SecretsManager object.

        Args:
            None
        """
        self.client = boto3.client('secretsmanager')

    def get_secret(self, secret_name: str) -> Dict[str, Any]:
        """
        Retrieve a secret from AWS Secrets Manager.

        Args:
            secret_name: The name of the secret to retrieve.

        Returns:
            The secret information.
        """
        print(f"Secret is: {secret_name}")
        secret = self.client.get_secret_value(SecretId=secret_name)
        return secret

    def get_rsa_key(self, rsa_key: str) -> bytes:
        """
        Retrieve an RSA private key from AWS Secrets Manager.

        Args:
            rsa_key: The name of the RSA private key secret.

        Returns:
            The RSA private key bytes.
        """
        private_key = self.get_secret(rsa_key)
        p_key = serialization.load_pem_private_key(
            bytes(private_key['SecretString'], "utf-8"),
            password=None,
            backend=default_backend()
        )
        pkb = p_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return pkb

    def load_secret(self, secret_name: str) -> Dict[str, Any]:
        """
        Load a secret from AWS Secrets Manager and parse it as JSON.

        Args:
            secret_name: The name of the secret to load.

        Returns:
            The secret content as a JSON object.
        """
        secret_content = self.get_secret(secret_name)
        secret_content_json = json.loads(secret_content['SecretString'])
        return secret_content_json
