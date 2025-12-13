#!/usr/bin/env python3
"""
Database Connection Test Script for Victor Springs
Run this to diagnose database connectivity issues
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_database_connection():
    """Test database connection and provide diagnostics"""
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import OperationalError

        DATABASE_URL = os.getenv("DATABASE_URL")
        if not DATABASE_URL:
            print("❌ ERROR: DATABASE_URL not found in .env file")
            return False

        print(
            f"🔍 Testing connection to: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'database'}"
        )

        # Create engine with connection pooling
        engine = create_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,
            max_overflow=10,
            connect_args={
                "connect_timeout": 10,
                # Removed statement_timeout for Neon compatibility
            },
        )

        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Connected successfully!")
            print(f"📊 PostgreSQL Version: {version.split(' ')[1]}")

            # Test basic queries
            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.fetchone()[0]
            print(f"👥 Users in database: {user_count}")

            result = conn.execute(text("SELECT COUNT(*) FROM properties"))
            prop_count = result.fetchone()[0]
            print(f"🏠 Properties in database: {prop_count}")

            result = conn.execute(text("SELECT COUNT(*) FROM vacancy_alerts"))
            alert_count = result.fetchone()[0]
            print(f"💝 Property interests: {alert_count}")

        engine.dispose()
        return True

    except OperationalError as e:
        print(f"❌ Database connection failed: {e}")
        print("\n🔧 Troubleshooting steps:")
        print("1. Check if PostgreSQL is running: sudo systemctl status postgresql")
        print("2. Verify DATABASE_URL in .env file")
        print("3. Test manual connection: psql -d victor_springs -c 'SELECT 1'")
        print(
            "4. Check PostgreSQL logs: sudo tail -f /var/log/postgresql/postgresql-*.log"
        )
        return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Victor Springs Database Connection Test")
    print("=" * 50)

    success = test_database_connection()

    if success:
        print("\n🎉 Database connection is working!")
        print("Your Victor Springs backend should work correctly now.")
    else:
        print("\n💥 Database connection failed!")
        print("Please fix the issues above before running the backend.")

    sys.exit(0 if success else 1)
