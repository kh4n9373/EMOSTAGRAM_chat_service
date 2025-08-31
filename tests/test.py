from core.database.mongodb_client import MongoManager

client = MongoManager(db="EMOSTAGRAM")

client.find(collection_name="messages")