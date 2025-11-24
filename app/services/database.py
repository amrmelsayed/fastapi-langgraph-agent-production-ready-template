"""Database service for MongoDB health checks."""

from pymongo import MongoClient

from app.core.config import settings
from app.core.logging import logger


class DatabaseService:
    """Minimal database service for MongoDB health checks."""

    def __init__(self):
        """Initialize database service."""
        self.client: MongoClient | None = None

    async def health_check(self) -> bool:
        """Check MongoDB connection health.

        Returns:
            bool: True if MongoDB is healthy, False otherwise
        """
        try:
            if not settings.MONGODB_URI:
                logger.warning("mongodb_health_check_skipped", reason="MONGODB_URI not configured")
                return False

            # Create a temporary client for health check
            if not self.client:
                self.client = MongoClient(
                    settings.MONGODB_URI,
                    serverSelectionTimeoutMS=5000,  # 5 second timeout
                )

            # Ping the database to verify connectivity
            self.client.admin.command("ping")
            logger.debug(
                "mongodb_health_check_success",
                mongodb_db_name=settings.MONGODB_DB_NAME
            )
            return True

        except Exception as e:
            logger.error(
                "mongodb_health_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    async def close(self):
        """Close database connection."""
        if self.client:
            self.client.close()
            self.client = None


# Global database service instance
database_service = DatabaseService()
