## Prenotazione spettacoli teatrali
---

### Descrizione del progetto
Il progetto è realizzato per l'esame di **Tecnologie Web** e consiste in una piattaforma online dedicata alla gestione e alla prenotazione di spettacoli teatrali. La piattaforma permette di consultare i teatri e gli spettacoli in programmazione, cercare le rappresentazioni disponibili tramite filtri, selezionare i posti in sala e prenotare i biglietti.

L'applicazione è accessibile sia ad utenti anonimi sia ad utenti registrati, con funzionalità differenti in base al ruolo assegnato. I ruoli sono gestiti tramite i gruppi di Django (`client`, `artist`, `manager`, `admin`).

L'applicazione è divisa nelle seguenti viste:

- **Utente non registrato**

    Un utente non registrato può cercare teatri e spettacoli tramite i filtri di ricerca, consultare le schede dei teatri e degli spettacoli, e visualizzare le date, gli orari e la disponibilità dei posti delle rappresentazioni in programmazione. Non può però effettuare alcuna prenotazione: per farlo è necessario registrarsi e accedere.

- **Utente standard (cliente)**

    Un utente standard ha la stessa vista di un utente non registrato, con l'aggiunta delle funzionalità legate alle prenotazioni.

    L'utente può selezionare i posti liberi in sala di una rappresentazione ed effettuare la prenotazione dei biglietti. Attraverso la propria area personale ha accesso allo storico delle prenotazioni, con la possibilità di **modificarle** (cambiando i posti selezionati) o di **annullarle**.

    Una prenotazione può essere modificata o annullata solo se la rappresentazione associata è ancora programmata e non è ancora iniziata: una volta che lo spettacolo ha avuto inizio (o non è più disponibile), la prenotazione non è più modificabile né annullabile.

    Sulla home page è inoltre presente un sistema di **suggerimento degli spettacoli**, basato sulle prenotazioni effettuate dall'utente: gli spettacoli vengono proposti in base all'affinità con le categorie e gli artisti già prenotati e alla popolarità globale, escludendo quelli già prenotati.

- **Utente artista**

    L'artista può inserire sulla piattaforma i propri spettacoli teatrali, specificando informazioni come titolo, descrizione, categoria, durata e locandina.

    Per evitare che una rappresentazione entri in programmazione senza il consenso dell'artista, ogni rappresentazione proposta da un amministratore per uno spettacolo dell'artista resta in attesa (`pending_artist_confirmation`) finché l'artista non la **conferma**. Solo dopo la conferma la rappresentazione diventa programmata (`scheduled`) e prenotabile dagli utenti; l'artista può in alternativa **rifiutarla**.

- **Amministratore di teatro (gestore)**

    Ogni teatro può essere gestito da uno o più amministratori. Dalla propria dashboard, l'amministratore di teatro organizza la programmazione del teatro scegliendo gli spettacoli proposti dagli artisti e assegnando sale, date e orari delle rappresentazioni.

    Può inoltre gestire le sale e le zone della sala, la disponibilità dei posti e i prezzi dei biglietti per zona, oltre ad assegnare eventualmente altri utenti come amministratori dello stesso teatro. L'ambito di gestione di un amministratore di teatro è limitato ai teatri a cui è stato assegnato.

- **Admin**

    L'admin, oltre ad avere accesso a tutte le viste precedenti, può creare nuovi teatri all'interno della piattaforma e assegnare agli utenti i ruoli, incluso quello di amministratore per la gestione delle relative strutture. Gestisce quindi utenti e ruoli dell'intera piattaforma.

### Struttura dei dati
Il dominio è modellato attorno alle seguenti entità principali:

- **Teatro** — una struttura con le proprie informazioni (nome, indirizzo, città, ecc.) e una o più sale.
- **Sala** (`Auditorium`) — appartiene a un teatro ed è suddivisa in **zone** (`AuditoriumZone`); da righe e posti per riga di ogni zona vengono generati automaticamente i **posti** (`Seat`).
- **Spettacolo** (`Show`) — creato da un artista, con titolo, descrizione, categoria, durata e locandina.
- **Rappresentazione** (`Performance`) — uno spettacolo in una sala a una certa data/ora, con un ciclo di vita (in attesa di conferma dell'artista → programmata → annullata) e un prezzo per zona (`PerformancePrice`).
- **Prenotazione** (`Booking`) — associa un utente a una rappresentazione, con i posti prenotati (`BookingSeat`). L'unicità del posto per rappresentazione è garantita a livello di database.

### Aggiornamento realtime dei posti disponibili
La prenotazione dei posti avviene in modo sicuro anche in presenza di più utenti collegati contemporaneamente sulla stessa rappresentazione: al momento della prenotazione i posti confermati vengono bloccati (`select_for_update`) all'interno di una transazione, i conflitti vengono ricontrollati e il vincolo di unicità a livello di database impedisce definitivamente la doppia prenotazione dello stesso posto.

### Test del software
Sono stati realizzati tre test differenti all'interno del progetto (in `apps/bookings/tests.py`):

- **Test di prenotazioni duplicate**

    Verifica l'impossibilità di prenotare più volte lo stesso posto per la stessa rappresentazione: un secondo tentativo di prenotare un posto già occupato viola il vincolo di unicità e viene rifiutato.

- **Test di vietata cancellazione di una prenotazione**

    Verifica l'impossibilità di annullare una prenotazione se la rappresentazione ad essa associata è già iniziata (o non è più programmata). Un caso di controllo verifica invece che, per una rappresentazione futura, l'annullamento vada a buon fine e liberi i posti.

- **Test di atomicità sulla prenotazione dei posti**

    Verifica l'atomicità dell'operazione di prenotazione: l'operazione deve eseguirsi interamente oppure non eseguirsi affatto. Lo scenario simulato è quello in cui un utente prenota il posto A1 e, successivamente, un altro utente prova a prenotare i posti A1 e A2 insieme: essendo A1 già occupato, la prenotazione deve fallire interamente e neanche il posto A2 deve risultare prenotato.

### Dipendenze ed estensioni utilizzate
Oltre a **Django** (framework principale) e **Pillow** (gestione delle immagini di locandine e copertine tramite gli `ImageField`), il progetto utilizza le seguenti estensioni:

- **django-crispy-forms** — rendering elegante e coerente dei form.
- **crispy-tailwind** — template pack di crispy-forms per lo stile Tailwind CSS dei form.
- **django-filter** — filtri di ricerca dei teatri e degli spettacoli (usato dalla `SearchView` tramite `FilterView`).
- **django-select2** — campi di selezione avanzati con ricerca (widget Select2) nei form di gestione di spettacoli, rappresentazioni e amministratori.
- **django-braces** — mixin aggiuntivi per le viste basate su classi; in particolare `GroupRequiredMixin` per il controllo degli accessi in base al gruppo/ruolo dell'utente.

### Avvio rapido
1. Attiva il virtualenv:
   - Linux/macOS: `source .venv/bin/activate`
2. Installa le dipendenze:
   - `pip install -r requirements.txt`
3. Applica le migrazioni:
   - `python manage.py migrate`
4. (Opzionale) Popola il database con dati di esempio:
   - `python manage.py seed_data`
5. Avvia il server:
   - `python manage.py runserver`

Per eseguire i test:
- `python manage.py test`
