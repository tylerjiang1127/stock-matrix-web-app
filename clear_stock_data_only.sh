#!/bin/bash

# Clear only stock technical data tables, preserve user data
# This script provides granular control over database cleanup

set -e

echo "🗑️  Stock Data Cleanup Script"
echo "=============================="
echo ""
echo "This script will DELETE stock technical data but PRESERVE user authentication data."
echo ""
echo "Tables that will be CLEARED:"
echo "  - interval_1m_technical"
echo "  - interval_5m_technical"
echo "  - interval_15m_technical"
echo "  - interval_30m_technical"
echo "  - interval_60m_technical"
echo "  - interval_1d_technical"
echo "  - interval_1wk_technical"
echo "  - interval_1mo_technical"
echo ""
echo "Tables that will be PRESERVED:"
echo "  ✅ user_id_security"
echo "  ✅ email_verification_tokens"
echo "  ✅ password_reset_tokens"
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

echo "🗑️  Truncating stock technical data tables..."

# Truncate each interval table
docker exec -i stock_postgresql psql -U $POSTGRES_USER -d $POSTGRES_DB << EOF
-- Truncate all stock technical data tables
TRUNCATE TABLE interval_1m_technical;
TRUNCATE TABLE interval_5m_technical;
TRUNCATE TABLE interval_15m_technical;
TRUNCATE TABLE interval_30m_technical;
TRUNCATE TABLE interval_60m_technical;
TRUNCATE TABLE interval_1d_technical;
TRUNCATE TABLE interval_1wk_technical;
TRUNCATE TABLE interval_1mo_technical;

-- Verify tables are empty
SELECT 'interval_1m_technical' AS table_name, COUNT(*) AS row_count FROM interval_1m_technical
UNION ALL
SELECT 'interval_5m_technical', COUNT(*) FROM interval_5m_technical
UNION ALL
SELECT 'interval_15m_technical', COUNT(*) FROM interval_15m_technical
UNION ALL
SELECT 'interval_30m_technical', COUNT(*) FROM interval_30m_technical
UNION ALL
SELECT 'interval_60m_technical', COUNT(*) FROM interval_60m_technical
UNION ALL
SELECT 'interval_1d_technical', COUNT(*) FROM interval_1d_technical
UNION ALL
SELECT 'interval_1wk_technical', COUNT(*) FROM interval_1wk_technical
UNION ALL
SELECT 'interval_1mo_technical', COUNT(*) FROM interval_1mo_technical;

-- Verify user tables are preserved
SELECT 'user_id_security' AS table_name, COUNT(*) AS row_count FROM user_id_security;
EOF

echo ""
echo "✅ Stock technical data cleared successfully!"
echo ""
echo "📊 Summary:"
echo "  - Stock data: CLEARED ✅"
echo "  - User data: PRESERVED ✅"
echo ""
echo "📋 Next steps:"
echo "  1. Re-run stock database initialization"
echo "  2. User accounts remain intact"
echo ""
