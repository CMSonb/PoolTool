# Kulturpool – Metadaten normalisieren

Kleine Flask-Anwendung zur interaktiven Normalisierung von `dcType`, `medium` oder
`subject` in Kulturpool-JSON-Datensätzen. Die Oberfläche und Exportmeldungen sind
auf Deutsch. Eine Auswahl wird nur für die angehakten Varianten angewendet;
alle übrigen Werte bleiben unverändert.

## 1. Vokabular einrichten

Die CSV-Dateien liegen unter `data/vocabularies/`. Jede Datei enthält einen
Vorzugsbegriff pro Zeile. Die Kopfzeile `term,uri` ist optional; eine zweite
Spalte kann eine Konzept-URI enthalten:

```csv
term,uri
Fotografie,
Druckgraphik,https://example.org/concept/123
```

Die mitgelieferten CSV-Dateien enthalten nur die Kopfzeile. Bitte vor der
Verarbeitung mit dem eigenen Vokabular befüllen. `NORM_FIELD` bestimmt die
Vokabular-Datei und das Metadatenfeld; verfügbar sind `dcType`, `medium` und
`subject`. Standard ist `dcType`. Beim Feld `medium` werden kommaseparierte
Bestandteile einzeln verglichen.

## 2. Lokal starten

Voraussetzung: Python 3.10 oder neuer.

```powershell
cd Interface_prompting
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:NORM_FIELD = "dcType"
python app.py
```

Danach im Browser [http://localhost:5000](http://localhost:5000) öffnen. Für
`medium` oder `subject` den Wert von `NORM_FIELD` entsprechend ändern. Die
Standardanalyse verwendet den lokalen String-Matcher. Ein CLIP-Hook ist in
`matching.py` vorbereitet und kann dort ergänzt werden.

## 3. Mit Docker starten

Im Verzeichnis `Interface_prompting`:

```powershell
docker compose up --build
```

Die Oberfläche ist anschließend unter [http://localhost:5000](http://localhost:5000)
erreichbar. Feldwahl:

```powershell
$env:NORM_FIELD = "medium"
docker compose up --build
```

Vokabulare und Exporte werden über lokale Volumes eingebunden beziehungsweise
gespeichert (`data/vocabularies/` und `output/`).

## Eingabe und Ablauf

- Unterstützte Eingaben: JSONL/NDJSON (ein JSON-Objekt pro Zeile) oder ein
  JSON-Array. XML/RDF wird derzeit noch nicht verarbeitet.
- Datensätze sollen das gewählte Feld unter
  `content.aggregatedCHO.<Feld>` enthalten.
- Die Ähnlichkeitsschwelle ist beim Upload einstellbar. Der String-Matcher ist
  ein offline nutzbarer Platzhalter für die geplante CLIP-Integration.
- Kandidaten werden höchstens einem ähnlichsten Vokabularbegriff zugeordnet.
  Begriffe ohne Kandidaten werden automatisch übersprungen.
-   Die angezeigte und protokollierte ID wird aus dem ersten verfügbaren
  Original-ID-Feld (`src_id`, `source_id`, `original_id`, `record_id` oder
  `identifier`, einschließlich `content.aggregatedCHO.identifier`) gelesen.
  `kp_id` wird bewusst ignoriert. Fehlt eine Original-ID, wird eine Datensatznummer
  verwendet. Weitere Feldnamen lassen sich in `config.py` ergänzen.

## Export

Nach Abschluss können die vollständigen Datensätze als JSON-Array oder JSONL
und das Änderungsprotokoll als CSV oder JSON heruntergeladen werden. Die ZIP-
Option enthält beides. Zusätzlich kann ein Verarbeitungsbericht als Markdown-
oder PDF-Datei erstellt werden. Das PDF verwendet dieselbe lokal eingebundene
Atkinson-Hyperlegible-Next-Schrift wie die Website. Der Bericht fasst Datensatz-
und Änderungssummen zusammen und listet angenommene sowie abgelehnte Vorschläge
mit Ähnlichkeitswert und Zahl der betroffenen Datensätze auf. Ähnlichkeit ist
ein textbasierter Vergleichswert, keine Wahrscheinlichkeit für die fachliche
Richtigkeit. Protokolliert werden Datensatz-ID, Feld, alter und neuer Wert,
Variante, Vorzugsbegriff und gegebenenfalls alte/neue URI.

Uploads und Ergebnisse liegen in `uploads/` beziehungsweise `output/`. Der
Upload wird nach der Verarbeitung entfernt. Die Sitzungen werden im
Arbeitsspeicher gehalten und gehen beim Neustart des Servers verloren.
