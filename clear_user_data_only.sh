#!/bin/bash

# Clear only user authentication data, preserve stock technical data
# This script provides granular control over user data cleanup

set -e

echo "🗑️  User Data Cleanup Script"
echo "============================"
echo ""
echo "This script will DELETE user authentication data but PRESERVE stock technical data."
echo ""
echo "Tables that will be CLEARED:"
echo "  - user_id_security"
echo "  - email_verification_tokens"
echo "  - password_reset_tokens"
echo ""
echo "Tables that will be PRESERVED:"
echo "  ✅ interval_1m_technical"
echo "  ✅ interval_5m_technical"
echo "  ✅ interval_15m_technical"
echo "  ✅ interval_30m_technical"
echo "  ✅ interval_60m_technical"
echo "  ✅ interval_1d_technical"
echo "  ✅ interval_1wk_technical"
echo "  ✅ interval_1mo_technical"
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Aborted."
    exit 0
fi

echo ""
echo "🔄 Connecting to PostgreSQL..."

# PostgreSQL connection details
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"
POSTGRES_DB="postgres"
POSTGRES_USER="admin"
POSTGRES_PASSWORD="password123"

# Export password to avoid prompts
export PGPASSWORD=$POSTGRES_PASSWORD

echo "🗑️  Truncating user authentication tables..."

# Truncate user tables with CASCADE to handle foreign key constraints
docker exec -i stock_postgresql psql -U $POSTGRES_USER -d $POSTGRES_DB << EOF
-- Truncate user authentication tables
-- CASCADE ensures that related tokens are also deleted
TRUNCATE TABLE user_id_security CASCADE;
TRUNCATE TABLE email_verification_tokens;
TRUNCATE TABLE password_reset_tokens;

-- Verify tables are empty
SELECT 'user_id_security' AS table_name, COUNT(*) AS row_count FROM user_id_security
UNION ALL
SELECT 'email_verification_tokens', COUNT(*) FROM email_verification_tokens
UNION ALL
SELECT 'password_reset_tokens', COUNT(*) FROM password_reset_tokens;

-- Verify stock tables are preserved (show first table as sample)
SELECT 'interval_1d_technical (sample)' AS table_name, COUNT(*) AS row_count FROM interval_1d_technical;
EOF

echo ""
echo "✅ User authentication data cleared successfully!"
echo ""
echo "📊 Summary:"
echo "  - User data: CLEARED ✅"
echo "  - Stock data: PRESERVED ✅"
echo ""
echo "📋 Next steps:"
echo "  1. Users need to re-register"
echo "  2. Stock data remains intact"
echo ""
