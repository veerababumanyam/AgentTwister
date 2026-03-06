"""
Cryptographic Signature Service

Provides SHA-256 cryptographic signing and verification for evidence bundles.
Ensures immutability and tamper detection for regulatory compliance.
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend

from app.models.evidence_bundle import (
    EvidenceBundle,
    CryptographicSignature,
    BundleStatus,
)


class SignatureService:
    """
    Service for creating and verifying cryptographic signatures on evidence bundles.
    
    Uses SHA-256 for content hashing and optionally RSA for digital signatures.
    """

    def __init__(
        self,
        enable_asymmetric: bool = False,
        private_key_pem: Optional[str] = None,
        public_key_pem: Optional[str] = None,
    ):
        """
        Initialize the signature service.
        
        Args:
            enable_asymmetric: If True, use RSA keys for digital signatures
            private_key_pem: PEM-encoded private key for signing
            public_key_pem: PEM-encoded public key for verification
        """
        self.enable_asymmetric = enable_asymmetric
        
        if enable_asymmetric:
            if private_key_pem:
                self.private_key = serialization.load_pem_private_key(
                    private_key_pem.encode(),
                    password=None,
                    backend=default_backend()
                )
            else:
                # Generate a new RSA key pair
                self.private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=2048,
                    backend=default_backend()
                )
            
            self.public_key = self.private_key.public_key()
            
            if public_key_pem:
                self.public_key = serialization.load_pem_public_key(
                    public_key_pem.encode(),
                    backend=default_backend()
                )
        else:
            self.private_key = None
            self.public_key = None

    def compute_content_hash(self, content: Dict[str, Any]) -> str:
        """
        Compute SHA-256 hash of content for integrity verification.
        
        Args:
            content: Dictionary of content to hash
            
        Returns:
            Hex-encoded SHA-256 hash
        """
        # Serialize content with stable ordering
        normalized = json.dumps(content, sort_keys=True, default=self._json_serializer)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def compute_bundle_hash(self, bundle: EvidenceBundle) -> str:
        """
        Compute SHA-256 hash of an evidence bundle's content.
        
        The hash excludes the signature fields themselves to allow
        verification against the stored hash.
        
        Args:
            bundle: The evidence bundle to hash
            
        Returns:
            Hex-encoded SHA-256 hash
        """
        content = {
            "bundle_id": bundle.bundle_id,
            "campaign_id": bundle.campaign_id,
            "campaign_name": bundle.campaign_name,
            "attestation": bundle.attestation.model_dump(),
            "agent_invocations": [inv.model_dump() for inv in bundle.agent_invocations],
            "payloads_used": [p.model_dump() for p in bundle.payloads_used],
            "artifacts": [a.model_dump() for a in bundle.artifacts],
            "framework_mappings": bundle.framework_mappings,
            "total_tokens_used": bundle.total_tokens_used,
            "created_at": bundle.created_at.isoformat(),
        }
        return self.compute_content_hash(content)

    def sign_bundle(
        self,
        bundle: EvidenceBundle,
        signed_by: str,
        signer_role: str = "evidence_service"
    ) -> CryptographicSignature:
        """
        Create a cryptographic signature for an evidence bundle.
        
        Args:
            bundle: The evidence bundle to sign
            signed_by: User ID or service account creating the signature
            signer_role: Role of the signer
            
        Returns:
            CryptographicSignature object
        """
        content_hash = self.compute_bundle_hash(bundle)
        
        signature = CryptographicSignature(
            content_hash=content_hash,
            signed_by=signed_by,
            signer_role=signer_role,
            signed_at=datetime.utcnow()
        )
        
        if self.enable_asymmetric and self.private_key:
            # Create digital signature using RSA
            message = content_hash.encode()
            signature.digital_signature = self.private_key.sign(
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            # Store public key fingerprint
            pub_pem = self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            signature.public_key_fingerprint = hashlib.sha256(pub_pem).hexdigest()
        
        return signature

    def verify_signature(
        self,
        bundle: EvidenceBundle,
        stored_hash: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify the cryptographic signature of an evidence bundle.
        
        Args:
            bundle: The evidence bundle to verify
            stored_hash: Optional pre-computed hash to compare against
            
        Returns:
            Tuple of (is_valid, verification_details)
        """
        details: Dict[str, Any] = {
            "verified_at": datetime.utcnow().isoformat(),
            "algorithm": "SHA-256",
        }
        
        if not bundle.signature:
            details["error"] = "No signature present on bundle"
            return False, details
        
        # Compute current hash of bundle content
        current_hash = self.compute_bundle_hash(bundle)
        details["computed_hash"] = current_hash
        details["stored_hash"] = bundle.signature.content_hash
        
        # Verify content hash matches
        hash_match = current_hash == bundle.signature.content_hash
        
        if stored_hash:
            hash_match = hash_match and (current_hash == stored_hash)
            details["provided_hash"] = stored_hash
        
        # Verify digital signature if present
        signature_valid = True
        if bundle.signature.digital_signature and self.enable_asymmetric:
            try:
                message = bundle.signature.content_hash.encode()
                self.public_key.verify(
                    bundle.signature.digital_signature,
                    message,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                details["digital_signature_verified"] = True
            except Exception as e:
                signature_valid = False
                details["digital_signature_error"] = str(e)
        
        details["hash_match"] = hash_match
        details["signature_valid"] = signature_valid
        
        is_valid = hash_match and signature_valid
        details["overall_valid"] = is_valid
        
        return is_valid, details

    def seal_bundle(
        self,
        bundle: EvidenceBundle,
        signed_by: str
    ) -> EvidenceBundle:
        """
        Seal an evidence bundle with a cryptographic signature.
        
        After sealing, the bundle becomes immutable. Any modifications
        will cause verification to fail.
        
        Args:
            bundle: The evidence bundle to seal
            signed_by: User ID or service account sealing the bundle
            
        Returns:
            The sealed evidence bundle
        """
        if bundle.status != BundleStatus.DRAFT:
            raise ValueError(f"Cannot seal bundle in status: {bundle.status}")
        
        # Create and attach signature
        signature = self.sign_bundle(bundle, signed_by)
        bundle.signature = signature
        
        # Update bundle status
        bundle.status = BundleStatus.SEALED
        bundle.sealed_at = datetime.utcnow()
        
        # Set verification status
        bundle.verification_status = "verified"
        bundle.verification_timestamp = datetime.utcnow()
        bundle.verification_details = {
            "sealed_at": bundle.sealed_at.isoformat(),
            "content_hash": signature.content_hash,
            "signature_algorithm": signature.signature_algorithm,
        }
        
        return bundle

    def verify_bundle_integrity(
        self,
        bundle: EvidenceBundle,
        provided_hash: Optional[str] = None
    ) -> bool:
        """
        Verify that an evidence bundle has not been tampered with.
        
        This is a convenience method that updates the bundle's
        verification status fields.
        
        Args:
            bundle: The evidence bundle to verify
            provided_hash: Optional hash from external source
            
        Returns:
            True if bundle is intact and verified
        """
        is_valid, details = self.verify_signature(bundle, provided_hash)
        
        bundle.verification_status = "verified" if is_valid else "failed"
        bundle.verification_timestamp = datetime.utcnow()
        bundle.verification_details = details
        
        return is_valid

    def generate_artifact_hash(self, artifact_content: bytes) -> str:
        """
        Generate SHA-256 hash for an individual artifact.
        
        Args:
            artifact_content: Raw bytes of the artifact
            
        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(artifact_content).hexdigest()

    def verify_artifact_hash(self, artifact_content: bytes, expected_hash: str) -> bool:
        """
        Verify an artifact's content against its expected hash.
        
        Args:
            artifact_content: Raw bytes of the artifact
            expected_hash: Expected SHA-256 hash
            
        Returns:
            True if hash matches
        """
        actual_hash = self.generate_artifact_hash(artifact_content)
        return actual_hash.lower() == expected_hash.lower()

    def get_public_key_pem(self) -> Optional[str]:
        """
        Export the public key in PEM format.
        
        Returns:
            PEM-encoded public key string, or None if asymmetric not enabled
        """
        if not self.public_key:
            return None
        
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode()

    def get_public_key_fingerprint(self) -> Optional[str]:
        """
        Get the fingerprint of the public key.
        
        Returns:
            SHA-256 hash of the public key PEM, or None
        """
        pem = self.get_public_key_pem()
        if not pem:
            return None
        return hashlib.sha256(pem.encode()).hexdigest()

    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """Custom JSON serializer for datetime and other non-serializable objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, "model_dump"):
            return obj.model_dump()
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        else:
            return str(obj)


class AttestationSigner:
    """
    Service for signing scope attestations.
    
    Attestations are legal documents that must be cryptographically bound
    to the evidence bundle to prevent post-hoc modifications.
    """

    def __init__(self, signature_service: SignatureService):
        """
        Initialize attestation signer.
        
        Args:
            signature_service: Signature service for cryptographic operations
        """
        self.signature_service = signature_service

    def create_attestation_hash(
        self,
        attestation_data: Dict[str, Any]
    ) -> str:
        """
        Create hash of attestation data for binding to evidence bundle.
        
        Args:
            attestation_data: Attestation dictionary
            
        Returns:
            SHA-256 hash
        """
        return self.signature_service.compute_content_hash(attestation_data)

    def verify_attestation_integrity(
        self,
        attestation_data: Dict[str, Any],
        expected_hash: str
    ) -> bool:
        """
        Verify that attestation data has not been modified.
        
        Args:
            attestation_data: Current attestation data
            expected_hash: Expected hash from bundle signature
            
        Returns:
            True if attestation is intact
        """
        actual_hash = self.create_attestation_hash(attestation_data)
        return actual_hash.lower() == expected_hash.lower()
