import heapq

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from database import db

# App

app = FastAPI(
    title="MAADB Polyglot API",
    description="API per query poliglotte su MongoDB e Neo4j"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    db.connect()


@app.on_event("shutdown")
async def shutdown_event():
    db.disconnect()


@app.get("/")
def read_root():
    return {"message": "MAADB API is running!"}


# Categoria 1 — Query di Lookup

# L1 — (MongoDB) Anagrafica persona
@app.get("/api/lookup/person/{person_id}")
def get_person(person_id: int):
    """Restituisce i dati anagrafici di una persona dalla collezione MongoDB 'person'.
    Utilizzata dalla pagina /person (PersonLookup).
    """
    person = db.mongo_db.person.find_one(
        {"id": person_id}, {"_id": 0}
    )
    if not person:
        raise HTTPException(status_code=404, detail="Persona non trovata")
    return person


# L2 — (Neo4j) Catena di trasferimenti di un conto
@app.get("/api/lookup/account/{account_id}/transfers")
def get_account_transfers(
    account_id: int,
    hops: int = Query(2, ge=1, le=5, description="Profondità massima della catena di trasferimenti")
):
    """Esplora la rete di trasferimenti in uscita da un conto fino a N salti,
    con una visita a strati (BFS): ogni conto viene espanso una volta sola.
    Restituisce il sottografo (nodi + archi distinti) raggiungibile, pronto per
    essere disegnato dal frontend (GraphViewer).
    Utilizzata dalla pagina /transfers (TransferChain).
    """

    visited = {account_id}
    frontier = [account_id]
    edges = []

    with db.neo4j_driver.session() as session:
        for _ in range(hops):
            if not frontier:
                break  # nessun conto nuovo da esplorare: ci fermiamo prima del limite

            level_query = """
            UNWIND $frontier AS fid
            MATCH (a:Account {id: fid})-[:TRANSFERS]->(b:Account)
            RETURN a.id AS source, b.id AS target
            """
            rows = session.run(level_query, frontier=frontier)

            # Un conto va nel prossimo giro solo se non l'abbiamo già visitato
            
            next_frontier = []
            for r in rows:
                #prendo i nodi
                src, tgt = r["source"], r["target"]
                #aggiungo archi
                edges.append({"source": str(src), "target": str(tgt)})
                #se il nodo non è stato visitato lo aggiungo alla frontiera
                if tgt not in visited:
                    visited.add(tgt)
                    next_frontier.append(tgt)
            frontier = next_frontier

    if not edges:
        with db.neo4j_driver.session() as session:
            if not session.run(
                "MATCH (a:Account {id: $id}) RETURN a LIMIT 1", id=account_id
            ).single():
                raise HTTPException(status_code=404, detail="Account non trovato")

    return {
        "account_id": account_id,
        "hops": hops,
        "nodes": [str(i) for i in visited],
        "edges": edges
    }


# L3 — (Cross-DB) Portafoglio aziendale
@app.get("/api/lookup/company/{company_id}/portfolio")
def get_company_portfolio(company_id: int):
    """Query in due passi:
      1. Neo4j : trova gli account posseduti dall'azienda (relazione OWNS).
      2. MongoDB > recupera i dettagli di quegli account dalla collezione 'account'.
    Utilizzata dalla pagina /company (CompanyPortfolio).
    """
    # Step 1: grafo Neo4j — restituisce gli id degli account come stringhe
    with db.neo4j_driver.session() as session:
        result = session.run(
            "MATCH (c:Company {id: $cid})-[:OWNS]->(a:Account) RETURN a.id AS account_id",
            cid=company_id
        )
        # Neo4j memorizza gli id come interi
        account_ids = [r["account_id"] for r in result]

    if not account_ids:
        if not db.mongo_db.company.find_one({"id": company_id}):
            raise HTTPException(status_code=404, detail="Azienda non trovata")
        return {"company_id": company_id, "accounts": [], "message": "Nessun conto associato"}

    # Step 2: documenti MongoDB — i account_ids sono già interi
    accounts_details = list(
        db.mongo_db.account.find({"id": {"$in": account_ids}}, {"_id": 0})
    )
    return {
        "company_id": company_id,
        "total_accounts": len(accounts_details),
        "accounts": accounts_details
    }


# Endpoint di supporto — Home & Suggestions

@app.get("/api/search/{entity_type}")
def search_entity(
    entity_type: str,
    q: str = Query("", description="Testo da cercare")
):
    """Ricerca asincrona leggera per popolare le dropdown del frontend."""
    if len(q) < 2:
        return []

    limit = 20

    if entity_type == "person":
        results = db.mongo_db.person.find(
            {"name": {"$regex": q, "$options": "i"}}, #option i attiva case insensitive
            {"_id": 0, "id": 1, "name": 1, "country": 1}#con uno indico sonlo i campi da trovre
        ).limit(limit)
        # Convertiamo l'ID in stringa prima di inviarlo al frontend per evitare
        # la perdita di precisione di JavaScript con i numeri a 64-bit (> Number.MAX_SAFE_INTEGER).
        return [ #costruisco oggetto con attributi che ni servono
            {"id": str(p["id"]), "label": p.get("name") or f"ID: {p['id']}"}
            for p in results
        ]

    elif entity_type == "company":
        results = db.mongo_db.company.find(
            {"name": {"$regex": q, "$options": "i"}},
            {"_id": 0, "id": 1, "name": 1, "country": 1}
        ).limit(limit)
        # Come sopra, proteggiamo l'ID 64-bit trasformandolo in stringa per il JSON
        return [ 
            {"id": str(c["id"]), "label": c.get("name") or f"ID: {c['id']}"}
            for c in results
        ]

    elif entity_type == "account":
        # Per gli account, cerchiamo il proprietario (persona o azienda) in MongoDB,
        # poi troviamo i loro account in Neo4j.
        
        # 1. Trova le persone il cui nome matcha con q
        owners = list(db.mongo_db.person.find(
            {"name": {"$regex": q, "$options": "i"}},
            {"_id": 0, "id": 1, "name": 1}
        ).limit(limit))
        
        companies = list(db.mongo_db.company.find(
            {"name": {"$regex": q, "$options": "i"}},
            {"_id": 0, "id": 1, "name": 1}
        ).limit(limit))
        
        # Usiamo stringhe come chiavi della mappa per consistenza,
        # e per proteggere gli ID a 64-bit quando verranno inseriti nel JSON finale
        owner_map = {str(p["id"]): p.get("name") for p in owners} #mappa con id->nome
        owner_map.update({str(c["id"]): c.get("name") for c in companies})
        
        owner_ids = [int(k) for k in owner_map.keys()] #predno le chiavi e le riconverto in int
        if not owner_ids:
            return []
            
        # 2. Trova account di questi proprietari, per ogni if  trova accaunt con relazione owns 
        #unwind serve a trasformare una lista in più righe, così da poter fare il match con ogni owner_id come "in" in python
        query = """
        UNWIND $owner_ids AS oid
        MATCH (owner {id: oid})-[:OWNS]->(a:Account)
        RETURN a.id AS account_id, owner.id AS owner_id
        LIMIT $limit
        """
        with db.neo4j_driver.session() as session:
            result = session.run(query, owner_ids=owner_ids, limit=limit)
            accounts = []
            for r in result:
                # Cast a stringa per evitare che Javascript sul frontend 
                # arrotondi l'ID distruggendone il valore (es. ...9000).
                acc_id = str(r["account_id"])
                own_id = str(r["owner_id"])
                owner_name = owner_map.get(own_id, "Sconosciuto")#se non trovo nome
                accounts.append({
                    "id": acc_id,
                    "label": f"Account {acc_id} — {owner_name}"
                })
            return accounts

    else:
        raise HTTPException(status_code=400, detail="Entity type non supportato")

@app.get("/api/home/stats")
def get_home_stats():
    """Metriche globali per la Home page (conteggi su MongoDB).
    Utilizzato dalla pagina / (Home).
    """
    return {
        "total_persons":    db.mongo_db.person.count_documents({}),
        "total_accounts":   db.mongo_db.account.count_documents({}),
        "blocked_accounts": db.mongo_db.account.count_documents({"isBlocked": True}),
        "total_companies":  db.mongo_db.company.count_documents({}),
        "blocked_companies":db.mongo_db.company.count_documents({"isBlocked": True})
    }


# Categoria 2 — Query Analitiche

# A1 — (MongoDB Aggregation) Statistiche aziende per nazione
@app.get("/api/analytics/companies/stats")
def get_companies_stats():
    """Aggregazione MongoDB: raggruppa le aziende per nazione, conta il totale e
    quante sono bloccate, calcola la percentuale.
    Utilizzata dalla pagina /company-stats (CompanyStats).
    """
    pipeline = [
        {
            "$group": {
                "_id": "$country",# ragggruppa per nazione
                "total_companies": {"$sum": 1},
                "blocked_companies": {
                    "$sum": {"$cond": [{"$eq": ["$isBlocked", True]}, 1, 0]} #cond è un if else inline, se isBlocked è true allora somma 1 altrimenti 0
                    #come COUNT(CASE WHEN isBlocked = true THEN 1 END) in sql
                }
            }
        },
        { #rimodella doc, id diventa cauntry, rimuove id, calcola percentuale, -1 per il sort decrescente
            "$project": {
                "country": "$_id",
                "_id": 0,
                "total_companies": 1,
                "blocked_companies": 1,
                "blocked_percentage": {
                    "$multiply": [
                        {"$divide": ["$blocked_companies", "$total_companies"]},
                        100
                    ]
                }
            }
        },
        {"$sort": {"total_companies": -1}}
    ]
    stats = list(db.mongo_db.company.aggregate(pipeline))
    return {"analytics": stats}


# A2 — (Neo4j) Shortest path tra due account
@app.get("/api/analytics/network/shortest-path")
def get_shortest_path(
    from_id: int,
    to_id: int,
    max_hops: int = Query(10, ge=1, le=15, description="Numero massimo di salti da esplorare")
):
    """Usa l'algoritmo shortestPath nativo di Neo4j (ricerca bidirezionale) per
    trovare il percorso con il minor numero di salti tra due account.
    Utilizzata dalla pagina /shortest-path (ShortestPath).
    """
    # Stesso conto su entrambi gli estremi: distanza 0, nessuna query di path serve.
    if from_id == to_id:
        with db.neo4j_driver.session() as session:
            exists = session.run(
                "MATCH (a:Account {id: $id}) RETURN a LIMIT 1", id=from_id
            ).single()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Conto/i non trovato/i: [{from_id}]")
        return {
            "from": from_id, "to": to_id,
            "path_found": True, "jumps": 0, "path": [str(from_id)]
        }
    #il tetto *1..max_hops evita di esplorare tutta la rete se i conti non sono connessi; il verso -> segue la direzione reale dei trasferimenti.
    query = f"""
    MATCH path = shortestPath(
        (start:Account {{id: $from_id}})-[:TRANSFERS*1..{max_hops}]->(end:Account {{id: $to_id}})
    )
    RETURN length(path) AS jumps, [n IN nodes(path) | toString(n.id)] AS path_nodes
    """
    with db.neo4j_driver.session() as session:
        result = session.run(query, from_id=from_id, to_id=to_id).single()

    if not result:
        # Distinguo "conto inesistente"da "nessun percorso entro max_hops".
        with db.neo4j_driver.session() as session:
            found_ids = session.run(
                "MATCH (a:Account) WHERE a.id IN [$from_id, $to_id] RETURN a.id AS id",
                from_id=from_id, to_id=to_id
            ).value("id")
        missing = [i for i in (from_id, to_id) if i not in found_ids]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Conto/i non trovato/i: {missing}"
            )
        return {
            "from": from_id, "to": to_id,
            "path_found": False,
            "message": "Nessun percorso trovato entro il limite di salti impostato"
        }
    return {
        "from": from_id,
        "to": to_id,
        "path_found": True,
        "jumps": result["jumps"],
        "path": result["path_nodes"]
    }


# A3 — (Cross-DB) Ciclo di riciclaggio sospetto
@app.get("/api/analytics/suspicious-cycle/{account_id}")
def get_suspicious_cycle(
    account_id: int,
    depth: int = Query(3, ge=2, le=6, description="Profondità massima del ciclo")
):
    """Trova, tra le catene di trasferimenti che partono da un conto e vi tornano
    entro `depth` salti, quella dove i soldi cambiano meno da un passaggio
    all'altro (il segnale di un vero giro di riciclaggio, dove l'importo si
    conserva quasi invariato lungo il ciclo). Usa Dijkstra
    Utilizzata dalla pagina /laundering-cycle (LaunderingCycle).
    """

    # Un ciclo richiede almeno un TRANSFERS in uscita e uno in entrata su "start";
    # se manca l'uno o l'altro evitiamo di esplorare il grafo inutilmente.
    with db.neo4j_driver.session() as session:
        pre_check = session.run(
            """
            MATCH (start:Account {id: $id})
            RETURN EXISTS { (start)-[:TRANSFERS]->() } AS has_out,
                   EXISTS { ()-[:TRANSFERS]->(start) } AS has_in
            """,
            id=account_id
        ).single()

    if not pre_check:
        raise HTTPException(status_code=404, detail="Conto non trovato")

    if not pre_check["has_out"] or not pre_check["has_in"]:
        return {"account_id": account_id, "suspicious_cycle_found": False}

    # Dijkstra sul "grafo delle transazioni"
    with db.neo4j_driver.session() as session:
        #dizionario con id->lista trasf in uscita
        #es: 1->[(2,100),(3,200),(4,300)]
        out_edges_cache = {}

        def out_edges(acc_id): #funzione che restituisce la lista di trasf in uscita da un conto
            if acc_id not in out_edges_cache:
                rows = session.run(
                    "MATCH (:Account {id: $id})-[r:TRANSFERS]->(next:Account) "
                    "RETURN next.id AS next_id, r.amount AS amount",
                    id=acc_id
                )
                #trasformo il lista di coppie
                out_edges_cache[acc_id] = [(r["next_id"], r["amount"]) for r in rows]
            return out_edges_cache[acc_id]

        heap = []
        # per ogni conto in uscita viene aggiunto all'heap con costo 0.0 e hops 1
        for next_id, amount in out_edges(account_id):
            if next_id != account_id:
                heapq.heappush(heap, (0.0, next_id, amount, 1, (account_id, next_id), (amount,)))

        settled = set()
        best_cycle = None

        # fino a che non esaurisco i conti o non trovo un ciclo
        while heap:
            # prendo la tupla col costo più basso rimasta in coda
            cost, current_id, current_amount, hops, chain_ids, amounts = heapq.heappop(heap)

            # questo conto, a questo numero di salti, l'ho già processato? salto
            if (current_id, hops) in settled:
                continue
            settled.add((current_id, hops))  # lo segno come fatto

            # sono tornato su start con almeno 2 salti? ciclo trovato, è il migliore possibile
            if current_id == account_id and hops >= 2:
                best_cycle = {"chain_ids": chain_ids, "amounts": amounts, "cost": cost}
                break

            # ho finito i salti disponibili, da qui non posso più andare avanti
            if hops >= depth:
                continue

            # provo tutti i trasferimenti in uscita di questo conto
            for next_id, next_amount in out_edges(current_id):
                # quanto cambia l'importo rispetto all'ultimo salto fatto
                step_cost = abs(next_amount - current_amount) / current_amount
                # nuova tupla: costo aggiornato, un salto in più,
                # catena di conti e di importi allungata di uno
                heapq.heappush(heap, (
                    cost + step_cost, next_id, next_amount, hops + 1,
                    #catens di conti visti fino a qwul momento
                    chain_ids + (next_id,), amounts + (next_amount,)
                ))

    if best_cycle is None:
        return {"account_id": account_id, "suspicious_cycle_found": False}

    # cycle_accounts come stringhe: solo per il frontend, in JS gli id numerici
    # grandi perdono precisione (Number.MAX_SAFE_INTEGER).
    cycle_accounts = [str(i) for i in best_cycle["chain_ids"]]

    with db.neo4j_driver.session() as session:
        owner_ids = [r["owner_id"] for r in session.run(
            """
            UNWIND $ids AS acc_id
            MATCH (owner)-[:OWNS]->(:Account {id: acc_id})
            RETURN DISTINCT owner.id AS owner_id
            """,
            ids=list(best_cycle["chain_ids"])
        )]

    # Ora andiamo su MongoDB a recuperare nome e nazione di ogni proprietario.
    # Un conto può appartenere a una Person o a una Company, quindi controlliamo entrambe
    # le collection e mettiamo tutto insieme in un'unica lista.
    owner_details = []
    for p in db.mongo_db.person.find(
        {"id": {"$in": owner_ids}},
        {"_id": 0, "id": 1, "name": 1, "country": 1}
    ):
        owner_details.append({
            "id": p["id"],
            "name": p.get("name", "N/A"),
            "country": p.get("country", "N/A"),
            "type": "Person"
        })

    for c in db.mongo_db.company.find(
        {"id": {"$in": owner_ids}},
        {"_id": 0, "id": 1, "name": 1, "country": 1}
    ):
        owner_details.append({
            "id": c["id"],
            "name": c.get("name", "N/A"),
            "country": c.get("country", "N/A"),
            "type": "Company"
        })

    # Set comprehension: per ogni owner "o" nella lista owner_details prendo o["country"],
    # scartando quelli con country "N/A"; e le nazioni ripetute in quantoè uin set
    # Se alla fine ci sono più nazioni diverse, allora è un caso di riciclaggio internazionale.
    countries = list({o["country"] for o in owner_details if o["country"] != "N/A"})

    return {
        "account_id": account_id,
        "suspicious_cycle_found": True,
        "cycle_length": len(cycle_accounts) - 1,
        "cycle_path": cycle_accounts,
        "owners": owner_details,
        "international_laundering": len(countries) > 1,
        "nations_involved": countries
    }


