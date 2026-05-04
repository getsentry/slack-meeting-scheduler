"""Google service account authentication."""

import json
import logging
from typing import Optional

import google.auth
from google.oauth2 import service_account
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)


class GoogleAuth:
    """Handles Google service account authentication."""

    # Required scopes for Calendar API
    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
    ]

    def __init__(self, service_account_json: Optional[str] = None):
        """Initialize Google authentication.

        Args:
            service_account_json: Service account credentials as JSON string.
                                 If None, uses Application Default Credentials (Cloud Run).
        """
        self._credentials = None
        self._service_account_info = (
            json.loads(service_account_json) if service_account_json else None
        )
        self._use_adc = service_account_json is None

        if self._use_adc:
            logger.info(
                "Google authentication initialized with Application Default Credentials"
            )
        else:
            logger.info("Google authentication initialized with service account JSON")

    def get_credentials(self):
        """Get or create credentials.

        Returns:
            Credentials (either service account or Application Default Credentials)
        """
        if self._credentials is None or not self._credentials.valid:
            if self._use_adc:
                # Use Application Default Credentials (Cloud Run service account)
                logger.debug(
                    "Creating credentials from Application Default Credentials"
                )
                credentials, project = google.auth.default(scopes=self.SCOPES)
                self._credentials = credentials
                logger.info(
                    f"Using Application Default Credentials for project: {project}"
                )
            else:
                # Use service account JSON
                logger.debug("Creating new service account credentials")
                self._credentials = (
                    service_account.Credentials.from_service_account_info(
                        self._service_account_info, scopes=self.SCOPES
                    )
                )

            # Refresh if needed
            if self._credentials.expired:
                logger.debug("Refreshing expired credentials")
                self._credentials.refresh(Request())

        return self._credentials
