from pymongo import MongoClient
import os
from dotenv import load_dotenv
import ssl

# Load environment variables from .env file
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

# Configure MongoDB connection with SSL settings for Render compatibility
try:
    client = MongoClient(
        MONGO_URI,
        tls=True,
        tlsAllowInvalidCertificates=True,
        tlsAllowInvalidHostnames=True,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=10000,
        socketTimeoutMS=10000,
        maxPoolSize=10
    )
    # Test connection
    client.admin.command('ping')
    print("MongoDB connection successful!")
except Exception as e:
    print(f"Primary MongoDB connection failed: {e}")
    try:
        # Fallback with simplified TLS settings
        client = MongoClient(
            MONGO_URI,
            tls=True,
            tlsAllowInvalidCertificates=True,
            serverSelectionTimeoutMS=5000
        )
        client.admin.command('ping')
        print("MongoDB fallback connection successful!")
    except Exception as e2:
        print(f"Fallback MongoDB connection failed: {e2}")
        try:
            # Last attempt with minimal settings
            client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=5000
            )
            client.admin.command('ping')
            print("MongoDB minimal connection successful!")
        except Exception as e3:
            print(f"All MongoDB connection attempts failed: {e3}")
            # Create client anyway for graceful degradation
            client = MongoClient(MONGO_URI)
            print("Using basic MongoDB connection (may not work)...")

db = client["exchange_dashboard"]  # имя базы данных
