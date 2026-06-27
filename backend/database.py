from pymongo import MongoClient
from neo4j import GraphDatabase

# Configurazioni
MONGO_URI = "mongodb://root:password@localhost:27017/"
MONGO_DB_NAME = "maadb"

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "password1234")

class Database:
    def __init__(self):
        self.mongo_client = None
        self.mongo_db = None
        self.neo4j_driver = None

    def connect(self):
        # Connessione MongoDB
        print("Connessione a MongoDB in corso...")
        self.mongo_client = MongoClient(MONGO_URI)
        self.mongo_db = self.mongo_client[MONGO_DB_NAME]
        print("Connesso a MongoDB.")

        # Connessione Neo4j
        print("Connessione a Neo4j in corso...")
        self.neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
        self.neo4j_driver.verify_connectivity()
        print("Connesso a Neo4j.")

    def disconnect(self):
        if self.mongo_client:
            self.mongo_client.close()
            print("Disconnesso da MongoDB.")
        if self.neo4j_driver:
            self.neo4j_driver.close()
            print("Disconnesso da Neo4j.")

# Istanza globale
db = Database()
