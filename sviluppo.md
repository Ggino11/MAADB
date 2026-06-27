# Diario di Sviluppo e Guida ai Comandi - Progetto MAADB

Questo documento traccia il percorso di sviluppo del progetto passo dopo passo. Oltre a contenere tutti i comandi tecnici necessari, spiega le decisioni architetturali e i motivi dietro le nostre scelte. Sarà la base perfetta per la stesura della relazione finale.

---

## Il Percorso del Progetto (Cosa stiamo facendo e perché)

L'obiettivo del progetto MAADB è creare un'architettura **Poliglotta**, sfruttando il meglio di due mondi:
1.  **MongoDB (Database Documentale):** Perfetto per memorizzare in modo flessibile i profili, le anagrafiche e i dati testuali delle entità.
2.  **Neo4j (Database a Grafo):** Indispensabile per tracciare i collegamenti tra le entità (le transazioni di denaro) e scovare pattern complessi in modo efficiente, cosa impossibile da fare con i database relazionali o documentali.

### La Scelta del Dataset (Perché "Small"?)
Abbiamo scelto di utilizzare il generatore **LDBC FinBench DataGen**, uno standard per le simulazioni finanziarie. 
Tuttavia, attualmente stiamo utilizzando lo script `generate_small.sh` (Scale Factor 0.1). **Questo non è un limite, ma una precisa scelta di sviluppo.**
*   *Perché lo facciamo:* Caricare e interrogare un dataset intero richiede decine di minuti. Usando un campione ridotto con la stessa identica struttura, possiamo programmare, testare gli script e creare le API in modo istantaneo. 
*   *Il piano futuro:* Una volta che il codice sarà stabile e il sito web funzionante, svuoteremo i database e diremo al generatore di usare lo *Scale Factor 1.0* (o superiore). A quel punto, con lo stesso identico codice, popoleremo il database reale e faremo i test di performance (benchmark) per la relazione.

---

## Manuale Tecnico e Comandi Eseguiti

Di seguito sono riportate tutte le procedure tecniche che abbiamo eseguito finora, utili per riprodurre l'ambiente da zero.

### Fase 1: Setup Dati (Generazione Dataset)
Invece di installare localmente tecnologie pesanti come Java, Spark e Scala, abbiamo incapsulato il generatore in un container Docker.

1.  **Spostarsi nella cartella del generatore:**
    ```powershell
    cd ldbc_finbench_datagen
    ```
2.  **Compilare il Generatore (Solo la prima volta):**
    Questo comando scarica le dipendenze e crea l'immagine `ldbc-datagen`.
    ```powershell
    docker build -t ldbc-datagen .
    ```
3.  **Generare i Dati:**
    Avvia il generatore che crea i file CSV/Parquet e li salva tramite un volume condiviso nella cartella `dataset` del tuo PC.
    ```powershell
    docker run --rm -v "$PWD\..\dataset:/app/out" ldbc-datagen
    ```

### Fase 2: Infrastruttura (I Database)
Per non "sporcare" il sistema operativo, anche i database vengono eseguiti tramite Docker.

1.  **Avviare MongoDB e Neo4j:**
    Dalla cartella principale del progetto (dove si trova il `docker-compose.yml`), eseguiamo:
    ```powershell
    docker compose up -d
    ```
2.  **Esplorazione Manuale dei Database:**
    I database sono attivi in background ed esplorabili:
    *   **Neo4j (Grafo):** Tramite browser su `http://localhost:7474` (User: `neo4j` | Pass: `password`). Usa `MATCH (n) RETURN n LIMIT 50` per vedere il grafo.
    *   **MongoDB (Documenti):** Tramite MongoDB Compass o VS Code collegandosi a `mongodb://root:password@localhost:27017/`.

### Fase 3: Pipeline di Ingestion (ETL in Python)
Per trasferire i dati dalla cartella `dataset` ai due database, abbiamo creato degli script Python ad hoc.

1.  **Creazione Ambiente Virtuale (Isolamento Dipendenze):**
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r backend/requirements.txt
    ```
2.  **Caricamento in MongoDB:**
    Legge i dati e crea le "collection" per Person, Company e Account.
    ```powershell
    python backend/ingestion_mongo.py
    ```
3.  **Caricamento in Neo4j:**
    Legge i dati per creare i Nodi e tracciare le relazioni (OWNS, TRANSFERS).
    ```powershell
    python backend/ingestion_neo4j.py
    ```

### Fase 4: Le Query del Progetto (Sviluppo Backend API)
Il cuore del nostro progetto consiste nell'implementazione di 6 query parametriche, esposte tramite API REST (FastAPI). Per dimostrare la potenza dell'architettura poliglotta, due di queste query (una per categoria) interrogheranno simultaneamente entrambi i database.

**Query di Lookup (Esplorazione Puntuale)**
1. **(MongoDB)** Recupero dell'anagrafica completa di una singola persona dato il suo ID.
2. **(Neo4j)** Storico delle transazioni dirette di un singolo conto, esplorando il grafo per importi e timestamp.(da rifare)
3. **(Cross-DB)** Dato l'ID di un'azienda, Neo4j individua i conti di sua proprietà tramite le relazioni del grafo; MongoDB interviene per restituirne i dettagli documentali.

**Query Analitiche (Aggregazioni e Pattern)**
1. **(MongoDB)** Calcolo della percentuale di aziende bloccate per nazione, sfruttando l'Aggregation Pipeline di MongoDB.
2. **(Neo4j)** *Shortest Path* tra due conti: calcolo del numero minimo di "salti" di transazioni che li collegano, tramite l'algoritmo nativo dei grafi.
3. **(Cross-DB)** *Money Laundering Cycle*: Neo4j individua cicli chiusi di transazioni sospette (A→B→C→A) a partire da un conto e risale ai proprietari coinvolti; MongoDB riceve questi proprietari e aggrega i loro dati geografici per mostrare quante e quali nazioni distinte sono coinvolte nel ciclo.

---

## Workflow Quotidiano: Cosa fare ogni giorno?

Grazie ai volumi Docker, **i dati caricati sono persistenti**. Questo significa che quando accendi il PC domani **NON** devi rifare la generazione o gli script Python.

Ogni volta che apri il progetto per programmare, ti basterà:
1.  **Verificare che i Database siano accesi:**
    ```powershell
    docker compose up -d
    ```
    *(Spesso partono da soli se apri l'app Docker Desktop).*
2.  **Attivare Python e Avviare il Server API:**
    ```powershell
    .\.venv\Scripts\Activate.ps1
    uvicorn backend.main:app --reload
    ```
    *Il server sarà attivo e potrai testare graficamente tutte le 6 query aprendo il browser all'indirizzo: **http://localhost:8000/docs***
