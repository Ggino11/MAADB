
from pymongo import MongoClient
from neo4j import GraphDatabase

def test_mongodb():
    print("Test connessione MongoDB...")
    try:
        # La stringa di connessione usa le credenziali dal docker-compose
        client = MongoClient("mongodb://root:password@localhost:27017/")
        # Eseguiamo un comando semplice per verificare che risponda
        client.admin.command('ping')
        print("[OK] Connessione a MongoDB Riuscita!")
    except Exception as e:
        print(f"[ERRORE] Errore di connessione a MongoDB: {e}")

def test_neo4j():
    print("\nTest connessione Neo4j...")
    try:
        # Usiamo il protocollo bolt sulla porta 7687 esposta dal docker-compose
        URI = "bolt://localhost:7687"
        AUTH = ("neo4j", "password1234")
        
        driver = GraphDatabase.driver(URI, auth=AUTH)
        driver.verify_connectivity()
        print("[OK] Connessione a Neo4j Riuscita!")
        driver.close()
    except Exception as e:
        print(f"[ERRORE] Errore di connessione a Neo4j: {e}")

if __name__ == "__main__":
    test_mongodb()
    test_neo4j()
