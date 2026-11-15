# Argo Forge — LFM2.5 locale

<p align="center">
  <img src="assets/Mascotte_IA_LFM2_5_Intel_i3-3240.png"
       alt="Argo Forge - LFM2.5 su Intel Core i3-3240"
       width="500">
</p>

<p align="center">
  <strong>LFM2.5-24B-A2B Q4_K_M</strong><br>
  Intel Core i3-3240 @ 3.40 GHz — Ivy Bridge (2012)
</p>

Ambiente dedicato a **LFM2.5-24B-A2B Q4_K_M** su argo3, Ubuntu 24.04,
Intel Core i3-3240 (Ivy Bridge, 2012), 2 core / 4 thread, 32 GB RAM installata
(circa 30 GiB utilizzabili), nessuna GPU dedicata.
Inferenza esclusivamente CPU: AVX/F16C, nessuna dipendenza da AVX2/FMA.

Il solo modello utilizzato è `LFM2.5-24B-A2B-Q4_K_M.gguf`.
Il suo percorso è fissato nella costante `MODEL` di `localcode.py` per il deployment
di riferimento: verificare il percorso prima di usare una copia su un altro host.
Il file rimane esterno al repository, montato in sola lettura. Il contesto è sempre
**131072 token**, con due thread e un solo slot; non esistono selettori o fallback.

```text
localcode.py → un container llama.cpp → GGUF read-only
                         ↑
            Web UI + API su 127.0.0.1:18080
                         ↑
       OpenCode → shell compatta → repository corrente
```

## Comandi

```bash
python3 localcode.py dry-run
python3 localcode.py start
python3 localcode.py status
python3 localcode.py logs
python3 localcode.py stats
python3 localcode.py restart
python3 localcode.py stop
```

Aprire **http://127.0.0.1:18080** per la Web UI integrata. API compatibile
OpenAI: `http://127.0.0.1:18080/v1`. Il server resta attivo dopo OpenCode;
`stop` lo arresta senza eliminarlo. `restart` riusa lo stesso container.
Non vengono scaricati pesi né eliminate immagini o container.

Per usare l'agente nel proprio progetto:

```bash
cd /percorso/del/progetto
python3 /percorso/argo-forge/localcode.py code --steps 24 --output 256
```

OpenCode chiede approvazione prima dei comandi shell. `--auto-approve` abilita
esplicitamente l'esecuzione senza approvazione per ogni comando; usarlo solo
in progetti fidati. La shell opera come l'utente corrente: **non è una sandbox**.
Il tool può leggere, modificare, compilare e testare tramite Bash.
`--prompt 'istruzione'` esegue un task non interattivo. OpenCode gestisce il loop;
`--steps` e `--output` sono budget indipendenti dal contesto fisso.

## Accesso LAN

Il binding resta esclusivamente localhost. Da un altro computer della LAN,
con accesso SSH già configurato tramite chiave:

```bash
ssh -N -L 127.0.0.1:18080:127.0.0.1:18080 utente@server
```

Aprire `http://127.0.0.1:18080` su quel computer. Non sono necessari password
applicative o credenziali nel repository. Non configurare port forwarding sul
router né pubblicare la porta Docker su `0.0.0.0`. API e Web UI condividono lo
stesso modello e uno slot: richieste simultanee possono attendere in coda.

## Documentazione

- [Installazione](docs/INSTALLATION.md)
- [Architettura e sicurezza](docs/ARCHITECTURE.md)
- [Diagnostica](docs/TROUBLESHOOTING.md)
- [Verifica effettiva](docs/VALIDATION.md)
- [Timeout fino a sei ore e collegamento Hermes](docs/TIMEOUTS.md)
- [Preparazione e verifica della distribuzione](docs/PUBLICATION.md)

128K è la capacità configurata, non una garanzia di velocità o qualità su prompt
lunghi. RAM, cache e prompt processing possono limitare fortemente questo host;
nessuna riduzione automatica del contesto. Non sono stati eseguiti benchmark estesi.

Licenza [MIT](LICENSE).

## Elaborazioni lente e Hermes

La configurazione prudenziale usa `--timeout 21600` per l'I/O HTTP di llama.cpp
e `21600000` millisecondi per le opzioni OpenCode `timeout`, `headerTimeout` e
`chunkTimeout`. La risposta viene consegnata appena pronta: **sei ore non sono
un'attesa obbligatoria, una garanzia di completamento o una deadline globale**.
Non è stato eseguito un collaudo continuo di sei ore. Health, caricamento e
smoke test mantengono limiti brevi e distinti. Dettagli in [TIMEOUTS](docs/TIMEOUTS.md).

Argo Forge può servire anche un'installazione separata di Hermes English Teacher,
con Telegram e voce locale IT/EN. Queste funzionalità, i token e i dati didattici
appartengono al progetto Hermes e non sono distribuiti qui. Se Hermes condivide
il namespace Docker del modello, una futura sostituzione del container server
richiede manutenzione coordinata e riaggancio del consumer, preservando i volumi.
Pubblicare i sorgenti già applicati non richiede riavviare il server locale.

## Controlli senza inferenza o modifiche ai servizi

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
python3 -B tools/audit_distribution.py
```

L'audit confronta Git con `distribution-files.txt`, verifica le esclusioni e
mostra il contesto Docker ammesso: soltanto `Dockerfile` e `.dockerignore`.
Non esegue build, installazioni, staging, commit o push. Backup, evidenze e
rapporti operativi locali restano fuori dalla distribuzione. La verifica dei
segreti è euristica e non sostituisce la revisione dei file da pubblicare.
