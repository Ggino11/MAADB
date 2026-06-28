# MAADB — Multi-database Fraud Investigation Dashboard

Dashboard di investigazione antifrode che implementa una architettura **Polyglot Persistence** (MongoDB + Neo4j) con un backend FastAPI e un frontend React/TypeScript.

Il sistema analizza il dataset sintetico [LDBC FinBench](https://github.com/ldbc/ldbc_finbench_datagen), composto da persone, aziende e conti bancari connessi da relazioni di proprietà e trasferimento, per rilevare pattern sospetti di riciclaggio di denaro.

---

## Architettura

```
┌─────────────────────────────────────────┐
│           Frontend (React + TS)         │
│         http://localhost:5173           │
└─────────────────┬───────────────────────┘
                  │ HTTP / Vite proxy
┌─────────────────▼───────────────────────┐
│        Backend FastAPI (Python)         │
│         http://localhost:8000           │
└───────┬─────────────────────┬───────────┘
        │                     │
┌───────▼───────┐   ┌─────────▼──────────┐
│   MongoDB     │   │       Neo4j        │
│  (doc store)  │   │   (graph store)    │
│  port 27017   │   │  port 7687 (Bolt)  │
│               │   │  port 7474 (HTTP)  │
└───────────────┘   └────────────────────┘
```

### Perché due database?

| Esigenza | MongoDB | Neo4j |
|---|---|---|
| Dati anagrafici (persona, azienda, conto) | ✅ | — |
| Relazioni di proprietà (OWNS) | — | ✅ |
| Rete di trasferimenti (TRANSFERS) | — | ✅ |
| Aggregazioni statistiche per nazione | ✅ (Aggregation Pipeline) | — |
| Shortest path tra conti | — | ✅ (shortestPath algo) |
| Rilevamento di cicli chiusi | — | ✅ (pattern matching) |
| Ricerca testuale asincrona dei profili | ✅ ($regex) | — |

---

## Setup e Avvio

### 1. Prerequisiti

- Docker Desktop
- Python 3.11+
- Node.js 18+

### 2. Avvio dei database

```bash
cd backend
docker compose up -d
```

I container avviati sono:
- `maadb-mongodb` — MongoDB 6.0 su porta 27017 (credenziali: `root` / `password`)
- `maadb-neo4j` — Neo4j 5.12 su porta 7687 (credenziali: `neo4j` / `password1234`)

### 3. Installazione dipendenze Python

```bash
python -m venv .venv
.\.venv\Scripts\activate      # Windows
pip install -r backend/requirements.txt
```

### 4. Importazione dei dati (ETL)

I dati vengono letti dalla cartella `dataset/raw/` generata da LDBC FinBench Datagen.

```bash
# Importa persone, aziende e conti in MongoDB
python backend/ingestion_mongo.py

# Importa i nodi e le relazioni nel grafo Neo4j
python backend/ingestion_neo4j.py
```

### 5. Avvio del backend

```bash
cd backend
python -m uvicorn main:app --reload
```

API disponibile su `http://localhost:8000`. Documentazione interattiva: `http://localhost:8000/docs`

### 6. Avvio del frontend

```bash
cd frontend/App
npm install
npm run dev
```

App disponibile su `http://localhost:5173`

---

## Dettaglio dei File

### Backend

#### `database.py`
Definisce la classe `Database` e l'istanza globale `db` importata da tutti i moduli.  
Gestisce le due connessioni in modo centralizzato:
- `db.mongo_db` → oggetto database MongoDB (pymongo)
- `db.neo4j_driver` → driver Neo4j (connessione Bolt)

Le connessioni vengono aperte all'avvio FastAPI (`startup_event`) e chiuse allo spegnimento (`shutdown_event`).

#### `main.py`
Cuore dell'applicazione. Contiene tutte le route API raggruppate in categorie:

| # | Funzione | Endpoint | Tipo DB |
|---|---|---|---|
| L1 | `get_person` | `GET /api/lookup/person/{id}` | MongoDB |
| L2 | `get_account_transfers` | `GET /api/lookup/account/{id}/transfers` | Neo4j |
| L3 | `get_company_portfolio` | `GET /api/lookup/company/{id}/portfolio` | Cross-DB |
| A1 | `get_companies_stats` | `GET /api/analytics/companies/stats` | MongoDB |
| A2 | `get_shortest_path` | `GET /api/analytics/network/shortest-path` | Neo4j |
| A3 | `get_suspicious_cycle` | `GET /api/analytics/suspicious-cycle/{id}` | Cross-DB |
| — | `search_entity` | `GET /api/search/{entity_type}?q=...` | Cross-DB/Mongo |
| — | `get_home_stats` | `GET /api/home/stats` | MongoDB |

**Helper `mixed_ids(str_ids)`**: funzione di utilità che, data una lista di ID stringa, restituisce anche le versioni intere. Necessaria per interrogare MongoDB, che può avere gli ID salvati come `int` o `str` a seconda del CSV originale.

> ⚠️ **Nota su Neo4j e gli ID**: tutti gli ID sono importati come *stringhe* in Neo4j. La funzione `parse_id()` (conversione a `int`) è stata quindi rimossa perché superflua e causa di `404` sulle query al grafo.

> ⚠️ **Nota su `hops` e `depth`**: Cypher non supporta parametri (`$var`) come lunghezza di cammino (`*1..$hops`). Questi valori vengono pertanto iniettati nell'f-string Python prima di inviare la query, come documentato inline nel codice.

#### `ingestion_mongo.py`
Script ETL standalone. Per ciascuna entità (`person`, `company`, `account`):
1. Individua i file CSV in `dataset/raw/<entità>/` (pattern `part-*.csv`)
2. Li legge con pandas (separatore `|`)
3. Svuota la collezione MongoDB e reinserisce tutti i record

#### `ingestion_neo4j.py`
Script ETL standalone. Carica nel grafo Neo4j:
- **Nodi**: `Person`, `Company`, `Account` (solo la proprietà `id`)
- **Relazioni**: `OWNS` (Person→Account, Company→Account) e `TRANSFERS` (Account→Account)

I dati vengono inviati a Neo4j in batch da 1000 record tramite `session.execute_write`.

---

### Frontend

#### `api/client.ts`
Client HTTP centralizzato. Espone due funzioni base (`fetchJSON`, `postJSON`) e l'oggetto `api` con tutti i metodi della dashboard:

```typescript
api.searchEntities(type, q)            // → GET /api/search/{type}?q=...
api.getPerson(id)                      // → GET /api/lookup/person/{id}
api.getTransferChain(id, hops)         // → GET /api/lookup/account/{id}/transfers?hops=...
api.getCompanyPortfolio(id)            // → GET /api/lookup/company/{id}/portfolio
api.getCompanyStats()                  // → GET /api/analytics/companies/stats
api.getShortestPath(from, to)          // → GET /api/analytics/network/shortest-path
api.getLaunderingCycle(id, depth)      // → GET /api/analytics/suspicious-cycle/{id}?depth=...
```

Il Vite dev-server fa da proxy verso `localhost:8000`, quindi le chiamate usano path relativi (`/api/...`).

#### `components/Sidebar.tsx`
Navigazione laterale. Ogni tab corrisponde ad un pannello nella Dashboard (L1, L2, ecc). Ogni link ha un badge colorato che indica quale database viene interrogato (`MongoDB`, `Neo4j`, `Cross`).

#### `components/SearchableSelect.tsx`
Componente asincrono avanzato (basato su `react-select/async`). Sostituisce i classici dropdown filtrando dinamicamente i risultati con debounce (300ms) interagendo con la route `/api/search/`. L'utente digita il nome testualmente, il menu mostra i risultati pertinenti e salva segretamente l'ID esatto per le query di grafo.

#### `components/GraphViewer.tsx`
Wrapper attorno alla libreria `vis-network`. Riceve nodi ed archi e renderizza il grafo interattivo. Usato per visualizzare la rete di trasferimenti in L2.

#### `pages/Home.tsx`
La dashboard principale consolidata. Mostra in alto i contatori globali riepilogativi (da `GET /api/home/stats`) e contiene l'interfaccia a schede/pannelli (accordion) per lanciare tutte le query:
- **L1 (Anagrafica Persona):** Form visuale esteso (Person Lookup).
- **L2 (Catena Trasferimenti):** Renderizza interattivamente la rete in Neo4j.
- **L3 (Portafoglio Aziendale):** Ritorna le anagrafiche dei conti posseduti.
- **A1 (Statistiche Aziende):** Chart a barre riepilogative (nazioni bloccate).
- **A2 (Shortest Path):** Esplora percorsi in Neo4j (grafo e salti minimi).
- **A3 (Riciclaggio di Denaro):** Ricerca di cicli chiusi (money laundering cycles).

---

## Mappatura completa Funzione Backend → Pannello Frontend

| Endpoint Backend | Funzione Python | Pannello in `Home.tsx` | Tipo Query | Database |
|---|---|---|---|---|
| `GET /api/lookup/person/{id}` | `get_person` | `PanelL1` | Lookup L1 | MongoDB |
| `GET /api/lookup/account/{id}/transfers` | `get_account_transfers` | `PanelL2` | Lookup L2 | Neo4j |
| `GET /api/lookup/company/{id}/portfolio` | `get_company_portfolio` | `PanelL3` | Lookup L3 | Cross-DB |
| `GET /api/analytics/companies/stats` | `get_companies_stats` | `PanelA1` | Analitica A1 | MongoDB |
| `GET /api/analytics/network/shortest-path` | `get_shortest_path` | `PanelA2` | Analitica A2 | Neo4j |
| `GET /api/analytics/suspicious-cycle/{id}` | `get_suspicious_cycle` | `PanelA3` | Analitica A3 | Cross-DB |
| `GET /api/search/{type}?q=...` | `search_entity` | `SearchableSelect` | Supporto | Cross-Mongo/Neo4j |
| `GET /api/home/stats` | `get_home_stats` | Top Bar Stats | Supporto | MongoDB |

---

## Credenziali Database

| Database | Host | Porta | Username | Password |
|---|---|---|---|---|
| MongoDB | localhost | 27017 | `root` | `password` |
| Neo4j (Bolt) | localhost | 7687 | `neo4j` | `password1234` |
| Neo4j (Browser) | localhost | 7474 | `neo4j` | `password1234` |
