# Diagnostica

```bash
python3 localcode.py status
python3 localcode.py logs
curl http://127.0.0.1:18080/health
curl http://127.0.0.1:18080/v1/models
curl --compressed http://127.0.0.1:18080/ > /tmp/argo-webui.html
python3 localcode.py stats
docker stats --no-stream argo-forge-lfm25
```

La Web UI compressa richiede supporto gzip: `curl` senza `--compressed` può
ricevere 415; i browser normali lo supportano. `/health` risponde 503 durante
il caricamento. Il launcher attende fino a 600 secondi, senza ridurre 131072.
Se scade l'attesa, il container rimane ispezionabile tramite log e status.

Memoria insufficiente: controllare `free -h`, Docker stats e gli eventi OOM del
container. Liberare carichi concorrenti; il launcher non cambia il contesto.
Su Ivy Bridge i prompt lunghi possono richiedere tempi elevati; aumentare gli
step senza necessità può produrre esecuzioni di ore. Non promettere prestazioni
interattive su tutto il contesto.

Porta occupata: individuare il servizio con `ss -ltn`; non eliminarlo. Container
precedente attivo: arrestarlo solo con una decisione esplicita dell'utente.
Configurazione incompatibile: il launcher non rimuove né sostituisce container.
Docker non accessibile: predisporre i permessi amministrativamente; non usare
sudo automaticamente. Illegal instruction: verificare di usare build Ivy Bridge
e OpenCode baseline.

Tool calling: una risposta testuale non prova l'integrazione. Occorrono chiamata
shell reale, modifica effettiva e test post-modifica verde. Il server condivide
uno slot: evitare richieste Web UI durante la verifica dell'agente.

## Richieste lunghe e timeout

Distinguere I/O server, attesa header, pausa fra chunk e timeout totale della
singola fetch OpenCode; tutti i valori lunghi sono finiti, ma non si sommano in
una deadline globale. Un heartbeat SSE non misura il completamento del compito.
Non riavviare un modello solo perché sta elaborando lentamente. Per annullare,
usare Stop nel client o /stop in Hermes; il rilascio del batch CPU può non essere
istantaneo. Non rilanciare subito la stessa domanda presumendo che il calcolo
precedente sia già cessato.

Se lo smoke test termina dopo 900 secondi, ha raggiunto il limite del test, non
necessariamente quello della singola fetch. Se un comando shell rimane attivo,
il timeout LLM non è un process killer del tool Bash. Conservare health 2 s,
startup 600 s, diagnostica 10 s e rete Telegram breve: alzarli tutti a sei ore
nasconderebbe errori di disponibilità. Dettagli in [TIMEOUTS.md](TIMEOUTS.md).

## Configurazione precedente o namespace Hermes

Confrontare Cmd effettivo e launcher: --help mostra il default compilato 3600,
non il valore già impostato a 21600 nel container. Un semplice restart non cambia
Cmd. Un'incompatibilità richiede manutenzione separata, non rimozione automatica.
Se il server è stato ricreato, verificare che Hermes condivida il suo namespace
attuale: il 127.0.0.1 nel container non è quello dell'host. Non pubblicare nuove
porte per aggirare un collegamento non aggiornato.

## Audit di distribuzione fallito

Eseguire `python3 -B tools/audit_distribution.py`. Se il manifest diverge da Git,
revisionare localmente i candidati: il controllo mostra soltanto conteggi per
non esporre nomi inattesi. Non usare add forzato per backup o dati privati.
Se compare un override Dockerfile.dockerignore, una COPY locale o un ampliamento
del contesto, rivedere il contratto prima di qualsiasi build. Per segnalazioni di
segreti l'output omette i valori: non incollare credenziali in issue o report.
