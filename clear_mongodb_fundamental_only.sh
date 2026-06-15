#!/bin/bash

# Clear only MongoDB stock fundamental data (metadata)
# This script removes company overview and financial statements data

set -e

echo "🗑️  MongoDB Stock Fundamental Data Cleanup Script"
echo "================================================="
echo ""
echo "This script will DELETE stock fundamental data from MongoDB."
echo ""
echo "Collections that will be CLEARED:"
echo "  - stock_metadata (company overview, financial statements)"
echo ""
echo "Collections that will be PRESERVED:"
echo "  ✅ stock_list (if exists)"
echo ""
echo "Other databases:"
echo "  ✅ PostgreSQL stock technical data (PRESERVED)"
echo "  ✅ PostgreSQL user data (PRESERVED)"
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Aborted."
    exit 0
fi

echo ""
echo "🔄 Connecting to MongoDB..."

# MongoDB connection details
MONGODB_HOST="localhost"
MONGODB_PORT="27017"
MONGODB_DB="stock_data"
MONGODB_USER="admin"
MONGODB_PASSWORD="password123"

echo "🗑️  Clearing stock_metadata collection..."

# Clear stock_metadata collection
docker exec -i stock_mongodb mongosh \
    --host $MONGODB_HOST \
    --port $MONGODB_PORT \
    --username $MONGODB_USER \
    --password $MONGODB_PASSWORD \
    --authenticationDatabase admin \
    $MONGODB_DB << EOF

// Delete all documents from stock_metadata collection
const result = db.stock_metadata.deleteMany({});
print("Deleted " + result.deletedCount + " documents from stock_metadata");

// Verify collection is empty
const count = db.stock_metadata.countDocuments({});
print("Remaining documents in stock_metadata: " + count);

// Show stats
print("");
print("📊 MongoDB Collection Stats:");
print("  stock_metadata: " + db.stock_metadata.countDocuments({}) + " documents");

// Check if stock_list exists and show its count
if (db.getCollectionNames().includes('stock_list')) {
    print("  stock_list: " + db.stock_list.countDocuments({}) + " documents (PRESERVED)");
}

EOF

echo ""
echo "✅ MongoDB stock fundamental data cleared successfully!"
echo ""
echo "📊 Summary:"
echo "  - MongoDB stock_metadata: CLEARED ✅"
echo "  - PostgreSQL stock data: PRESERVED ✅"
echo "  - PostgreSQL user data: PRESERVED ✅"
echo ""
echo "📋 Next steps:"
echo "  1. Re-fetch fundamental data via API calls"
echo "  2. Or wait for on-demand fetching when users search stocks"
echo ""
