# Progetto prenotazione teatri

Piattaforma Django per gestione e prenotazione di spettacoli teatrali.

## Avvio rapido

1. Attiva virtualenv:
   - Linux/macOS: `source .venv/bin/activate`
2. Installa dipendenze:
   - `pip install -r requirements.txt`
3. Migrazioni e superuser:
   - `python manage.py makemigrations`
   - `python manage.py migrate`
   - `python manage.py createsuperuser`
4. Avvia server:
   - `python manage.py runserver`

## Ruoli
- Utente standard: prenotazioni, storico, cancellazione.
- Artista: crea spettacoli e conferma disponibilita.
- Amministratore teatro: crea sale e performance.
- Superuser: crea teatri e assegna admin tramite admin site.

## Note
- Tailwind via CDN (nessun build step).
- Media upload in `media/`.

## Dati iniziali consigliati
1. Entra in `/admin/` con il superuser.
2. Crea alcune categorie.
3. Crea un teatro e assegna un admin teatro.
4. Crea sale per il teatro.
5. Gli artisti creano spettacoli e li confermano.
6. Admin teatro crea le performance.
