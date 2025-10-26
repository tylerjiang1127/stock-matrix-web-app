// create database and user
db = db.getSiblingDB('stock_data');

// create user
db.createUser({
  user: 'stock_user',
  pwd: 'stock_password',
  roles: [
    {
      role: 'readWrite',
      db: 'stock_data'
    }
  ]
});

// create collection and index
db.createCollection('stocks');

// create index
db.stocks.createIndex({ "ticker": 1, "interval": 1 }, { unique: true });
db.stocks.createIndex({ "last_updated": 1 });

print('MongoDB initialization completed!');