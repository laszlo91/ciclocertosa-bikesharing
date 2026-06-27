# Contesto

La mia ciclofficina ha delle bici in avanzo, e abbiamo deciso di sistemarle e metterle a disposizione del quartiere. Affinché queste bici possano essere tenute fuori dall'officine e le persone possano prenderle quando vogliono, sono legate con un catenaccio con codice. Oggi molte persone che sappiamo usare le biciclette in sharing hanno il codice, ma vorremmo creare un'applicazione perché le persone possano sbloccare le biciclette in autonomia.

# Descrizione funzionale

L'applicazione sarà una webapp mobile responsive accessibile pubblicamente su internet. Nella landing page ci sono le card delle bici disponibili. Se nessuna bici è disponibile apparirà messaggio zero disponibilità bici. L'utente clicca la card della bici d'interesse, passando alla finestra successiva, stile wizard. Nella finestra successiva viene richiesta una mail valida. Se l'utente è già registrato basta digitarla, confermare e va avanti alla schermata tre, altrimenti ci sarà un flusso speciale di validazione della mail tramite codice OTP inviato via email. Nella schermata 3 l'utente dovrà dire quando pensa di restituire la bicicletta (data e ora indicativa). Nella schermata successiva ci sarà un messaggio in cui pregheremo l'utente di rispettare la bici e riportarla, poiché altra gente fa affidamento su di essa. L'utente accetta, e riceve il codice di sblocco. Fine della procedura.

# Architettura
L'applicazione è basata su Streamlit Python e il DB sarà un SQLlite con le seguenti tabelle.
1) Tabella con tutte le prenotazioni bici
2) Tabella delle bici con stato disponibile/non disponibile e codice di sblocco
3) Tabella con tutte le mail salvate
Un cruscotto admin sarà a disposizione per fare operazioni sul DB. Sarà uno swagger sotto basic authentication, e saranno disponibili le seguenti azioni/API
- Change bike status
- Update code for a specific bike
- Read last N bookings
- Add a bike
- Remove a bike
- Check health

# Aspetto
La webapp, oltre che deve essere facilmente utilizzabile da smartphone (sarà principalmente usata da là) deve avere colori ad altro contrasto, un font ad alta accessibilità, e nessuna emoji. 