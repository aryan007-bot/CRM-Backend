from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.errors import FeatureNotConfiguredException


class DeploymentProvider(ABC):
    """Abstract interface for deployment provider operations."""

    @abstractmethod
    def get_status(self, environment_name: str) -> Dict[str, Any]:
        """Returns provider-level deployment status for the environment."""
        pass

    @abstractmethod
    def deploy(self, environment_name: str, version: str, commit_sha: str) -> Dict[str, Any]:
        """Triggers deployment of the given version/commit."""
        pass

    @abstractmethod
    def rollback(self, environment_name: str, target_version: Optional[str] = None) -> Dict[str, Any]:
        """Triggers rollback to previous or targeted version."""
        pass


class MockDeploymentProvider(DeploymentProvider):
    """Development/staging mock deployment provider for deterministic testing."""

    def get_status(self, environment_name: str) -> Dict[str, Any]:
        return {
            "provider": "mock",
            "environment": environment_name,
            "status": "HEALTHY",
            "active_version": "1.0.0",
        }

    def deploy(self, environment_name: str, version: str, commit_sha: str) -> Dict[str, Any]:
        return {
            "provider": "mock",
            "environment": environment_name,
            "version": version,
            "commit_sha": commit_sha,
            "status": "SUCCESS",
            "message": f"Successfully deployed {version} to {environment_name}",
        }

    def rollback(self, environment_name: str, target_version: Optional[str] = None) -> Dict[str, Any]:
        rollback_ver = target_version or "1.0.0"
        return {
            "provider": "mock",
            "environment": environment_name,
            "target_version": rollback_ver,
            "status": "ROLLED_BACK",
            "message": f"Successfully rolled back to {rollback_ver} in {environment_name}",
        }


class UnconfiguredDeploymentProvider(DeploymentProvider):
    """Fallback deployment provider when external provider is not configured."""

    def get_status(self, environment_name: str) -> Dict[str, Any]:
        raise FeatureNotConfiguredException("Deployment provider is not configured")

    def deploy(self, environment_name: str, version: str, commit_sha: str) -> Dict[str, Any]:
        raise FeatureNotConfiguredException("Deployment provider is not configured")

    def rollback(self, environment_name: str, target_version: Optional[str] = None) -> Dict[str, Any]:
        raise FeatureNotConfiguredException("Deployment provider is not configured")


def get_deployment_provider() -> DeploymentProvider:
    provider_type = (settings.DEPLOYMENT_PROVIDER or "").lower()
    if provider_type in ("mock", "local", "test", "docker"):
        return MockDeploymentProvider()
    return UnconfiguredDeploymentProvider()
