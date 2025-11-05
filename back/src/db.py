from pymongo import MongoClient
import os
from dotenv import load_dotenv
import ssl

# Load environment variables from .env file
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

# Configure MongoDB connection with SSL settings
try:
    client = MongoClient(
        MONGO_URI,
        ssl_cert_reqs=ssl.CERT_NONE,
        serverSelectionTimeoutMS=30000,
        connectTimeoutMS=30000,
        socketTimeoutMS=30000
    )
    # Test connection
    client.admin.command('ping')
    print("MongoDB connection successful!")
except Exception as e:
    print(f"MongoDB connection failed: {e}")
    # Fallback connection without SSL verification
    client = MongoClient(MONGO_URI)

db = client["exchange_dashboard"]  # имя базы данных
