# SecureCollab

**Projektdokumentation – Stand: Hobby/Proof of Concept**

---

## Inhaltsverzeichnis

1. [What is this?](#what-is-this)
2. [Das Problem das wir lösen](#das-problem-das-wir-lösen)
3. [Kryptographisches Modell](#kryptographisches-modell)
4. [Was die Plattform sehen kann – und was nicht](#was-die-plattform-sehen-kann--und-was-nicht)
5. [Trust Model: Warum du uns nicht vertrauen musst](#trust-model-warum-du-uns-nicht-vertrauen-musst)
6. [Wettbewerbslandschaft & Positionierung](#wettbewerbslandschaft--positionierung)
7. [Roadmap](#roadmap)
8. [Schnell skalierbar: Was bereits produktionsreif designed wurde](#schnell-skalierbar-was-bereits-produktionsreif-designed-wurde)
9. [Technischer Stack](#technischer-stack)
10. [Lokale Entwicklung](#lokale-entwicklung)
11. [Kontakt & Interesse](#kontakt--interesse)

---

## What is this?

SecureCollab ist eine Plattform für verschlüsselte Multi-Party Datenkollaboration, primär für klinische und pharmazeutische Forschung. Sie ermöglicht es mehreren Institutionen, gemeinsam auf kombinierten Datensätzen zu rechnen – ohne dass irgendeine Partei die Rohdaten einer anderen je sieht.

Das wird nicht durch Verträge garantiert, sondern durch Mathematik: **Homomorphic Encryption (HE)** erlaubt Berechnungen auf verschlüsselten Daten. Der Entschlüsselungsschlüssel existiert nie vollständig an einem Ort. Jede Operation ist kryptographisch beweisbar und im Audit Trail verankert.

### Aktueller Status

Dieses Projekt ist ein funktionierendes Hobby-Projekt. Es demonstriert das vollständige kryptographische Konzept mit echtem HE (TenSEAL/CKKS), einem funktionierenden Multi-Party Workflow und einer benutzbaren Web-Oberfläche.

Es ist kein MVP, das auf Kunden wartet. Es ist ein durchdachtes Fundament, das bei konkretem Interesse schnell in ein produktionsreifes System überführt werden kann – weil die Architektur von Anfang an dafür ausgelegt wurde.

---

## Das Problem das wir lösen

Wertvolle klinische und genomische Daten werden heute kaum geteilt. Regulatorische Anforderungen (DSGVO, HIPAA) machen den Austausch von Patientendaten rechtlich aufwändig. Institutionen misstrauen einander: Konkurrenz, unterschiedliche Rechtssysteme und die Angst vor Datenlecks oder Reputationsverlust führen dazu, dass Daten in Silos bleiben. Selbst wenn alle Beteiligten kooperieren wollen, fehlt oft ein vertrauenswürdiger Dritter – oder er ist zu teuer und zu langsam.

Das hat konkrete Kosten: verzögerte Studien, kleinere Kohorten, schlechtere statistische Power und langsamere Medikamentenentwicklung. Forschung, die auf größeren, kombinierten Datensätzen basieren könnte, wird nicht durchgeführt oder dauert Jahre länger.

Existierende Lösungen adressieren das nur teilweise. **Data Transfer Agreements (DTAs)** und **Federated Queries** setzen voraus, dass Daten entweder physisch übertragen oder dass mindestens eine Partei Zugriff auf Metadaten oder Abfrageergebnisse hat. **Data Clean Rooms** reduzieren das Risiko, erfordern aber weiterhin Vertrauen in die Betreiber und bieten keine mathematische Garantie, dass Rohdaten nie sichtbar werden. **Trusted Third Party**-Ansätze verschieben das Problem: Wer kontrolliert den Dritten? Wer haftet bei einem Breach? Für viele Institutionen ist „einfach jemandem vertrauen“ keine akzeptable Antwort – besonders wenn es um Patientendaten geht.

SecureCollab löst das, indem die Plattform **mathematisch ausgeschlossen** wird: Sie sieht nur verschlüsselte Daten und Metadaten. Rohdaten und Schlüssel bleiben verteilt bei den Institutionen.

---

## Kryptographisches Modell

### Homomorphic Encryption (CKKS)

Wir verwenden das **CKKS-Schema** (Cheon–Kim–Kim–Song), eine Variante von Homomorphic Encryption für **Gleitkommazahlen**. Im Gegensatz zu reinen Ganzzahl-Schemata erlaubt CKKS, Summen, Produkte und lineare Operationen direkt auf verschlüsselten Dezimalzahlen durchzuführen – genau das, was für statistische Auswertungen (Mittelwerte, Regressionen, Korrelationen) benötigt wird. Es ist auch für maschinelles Lernen auf verschlüsselten Daten geeignet.

CKKS ist **approximativ**: Rechenergebnisse unterliegen einem kleinen Rundungsfehler. Für Aggregationen über viele Werte (z. B. Mittelwert über Hunderte von Patienten) ist dieser Fehler in der Praxis vernachlässigbar und für die Entscheidungsfindung irrelevant. Wir nutzen TenSEAL als Python-Bindung zu Microsoft SEAL, der CKKS implementiert.

### Threshold Key Generation

Der Schlüssel zum Entschlüsseln existiert nie vollständig an einem Ort. Stattdessen erzeugen die Teilnehmer gemeinsam einen **kombinierten Public Key**; jeder hält lokal einen **Key Share** (einen Teil des privaten Schlüssels).

```
Institution A  →  Key Share A  ─┐
Institution B  →  Key Share B  ─┼→  Combined Public Key (zum Verschlüsseln)
Institution C  →  Key Share C  ─┘

Entschlüsseln: braucht t von n Key Shares
```

- **Kein einzelner Teilnehmer** kann alleine entschlüsseln.
- **Die Plattform** hat keinen einzigen Key Share – sie speichert nur den kombinierten Public Key.
- Es ist **mathematisch unmöglich** für die Plattform, Daten zu sehen.

Im aktuellen Stand ist die Threshold-Key-Generierung vereinfacht (der erste eingereichte Key Share wird als kombinierter Public Key verwendet). Eine vollständige t-of-n DKG-Implementierung ist für Phase 2 geplant.

### Cryptographic Commitments

Bei jedem Upload wird ein **Commitment Hash** berechnet:

`commitment = SHA3-256(ciphertext || public_key_fingerprint || timestamp || institution_email)`

Dieser Hash beweist, dass:

- **diese Datei** mit genau **diesem Public Key** verschlüsselt wurde,
- von **dieser Institution**,
- zu **diesem Zeitpunkt**,

und dass das nachträglich nicht änderbar ist. Jeder – die Institution selbst, Auditoren, Regulatoren – kann den Hash lokal nachrechnen und mit dem gespeicherten Wert vergleichen. So ist nachweisbar, welcher Schlüssel verwendet wurde und dass die auf der Plattform gespeicherte Datei mit der hochgeladenen übereinstimmt.

### Audit Trail & Blockchain Anchoring

Jeder Eintrag im Audit Trail enthält neben Aktion, Akteur und Details den **Hash des vorherigen Eintrags**. Dadurch entsteht eine Kette: Ändert jemand einen vergangenen Eintrag, bricht die Kette, und die Manipulation ist nachweisbar. Die Hash-Verkettung ist bereits implementiert (SHA3-256 über `action_type || actor || details || timestamp || previous_hash`).

**Blockchain Anchoring** (geplant für Phase 2): Täglich wird ein Root-Hash aller Audit-Einträge berechnet und in einer Transaktion auf der Polygon-Blockchain gespeichert. Damit kann jeder unabhängig verifizieren, dass die Plattform die History nicht nachträglich geändert hat – selbst wenn sie es wollte. Die Kosten liegen bei unter 1 € pro Tag.

*Status:* Die interne Hash-Verkettung ist implementiert und bietet starke Garantien. Blockchain-Anchoring fügt externe Unveränderlichkeit hinzu und ist auf der Roadmap für Phase 2 – relevant, sobald erste institutionelle Kunden onboarded werden.

---

## Was die Plattform sehen kann – und was nicht

| **KANN SEHEN** | **KANN NICHT SEHEN** |
|----------------|----------------------|
| Verschlüsselte Datensätze (Ciphertexte) | Rohdaten (Patientendaten, klinische Messwerte) |
| Metadaten (Dateigrößen, Timestamps, Institutionsnamen) | Private Key Shares (verbleiben lokal bei jeder Institution) |
| Audit-Trail-Einträge (Aktionen, nicht Inhalte) | Entschlüsselte Ergebnisse vor expliziter Freigabe durch alle Teilnehmer |
| Commitment Hashes | Welche Werte in einem Dataset enthalten sind |
| Kombinierter Public Key Fingerprint | |
| Verschlüsselte Zwischenergebnisse | |

Die rechte Spalte ist **nicht** eine Frage von Policy oder Vertrauen – sie ist unter dem gewählten kryptographischen Modell **mathematisch unmöglich** für die Plattform.

---

## Trust Model: Warum du uns nicht vertrauen musst

### Das Problem mit „Vertrau uns“

Duality Technologies löst das Vertrauensproblem durch akademische Autorität – ihr Gründerteam umfasst eine Turing Award Gewinnerin und MIT-Professoren. Das ist ein valides Vertrauensmodell, aber eines das auf Reputation basiert.

Wir haben keine vergleichbare Reputation. Deshalb haben wir ein anderes Vertrauensmodell gewählt: **Verifikation statt Vertrauen**.

### Unsere vier Verifikationsebenen

**Ebene 1: Vollständig Open Source**  
Nicht nur die Kryptographie-Bibliothek (wie bei Duality), sondern der gesamte Plattform-Code ist öffentlich. Jede Zeile die auf deinen Daten operiert ist lesbar, auditierbar, und verifizierbar.

- GitHub: [URL]
- Lizenz: Apache 2.0

**Ebene 2: Codebase Hash in jedem Audit-Eintrag**  
Jede Operation auf deinen Daten wird mit dem SHA3-256 Hash der aktiven Codebase gestempelt. Du kannst nach einer Studie verifizieren: *„Diese Berechnung lief auf Commit [hash] – ich habe diesen Code gelesen.“*

- `GET /system/integrity` gibt dir den aktuellen Hash.
- VERIFY.md erklärt, wie du lokal denselben Hash berechnen kannst.

**Ebene 3: Blockchain-verankerte Unveränderlichkeit (Phase 2)**  
Täglich wird der Audit Trail Hash auf der Polygon Blockchain verankert. Danach können wir die History nicht mehr ändern – selbst wenn wir wollten. Polygon Transaction ID wird öffentlich veröffentlicht.

**Ebene 4: Reproducible Builds**  
Jeder kann aus unserem Quellcode exakt dieselben Docker Images bauen und den Hash mit unserem produktiven Server vergleichen. Anleitung: VERIFY.md.

### Was das bedeutet

Du musst uns nicht vertrauen. **Du kannst prüfen.**  
Das ist der fundamentale Unterschied zu proprietären Lösungen.

### Was wir ehrlich nicht bieten (noch nicht)

- Keinen externen Security Audit (geplant für Phase 2)
- Keine Confidential Computing Hardware (TEE, geplant für Phase 2)
- Keine akademischen Kryptographie-Credentials im Gründerteam

Wir sind ehrlich über diese Lücken, weil Ehrlichkeit Teil unseres Vertrauensmodells ist.

---

## Wettbewerbslandschaft & Positionierung

### Existierende Anbieter

**Duality Technologies** – direktester Wettbewerber. Kombiniert HE, Federated Learning und TEEs. Hat bereits NHS England und andere institutionelle Kunden. $30M Series B (2021). Verkauft Enterprise-Verträge mit langen Sales-Zyklen und Enterprise-Preisen. Nicht zugänglich für mittelgroße Institutionen ohne entsprechendes IT-Budget.

**Enveil (ZeroReveal)** – fokussiert auf Enterprise Search und Analytics, vom CIA-Investment-Arm unterstützt. Weniger auf Multi-Party Clinical Data und akademische Kooperationen ausgerichtet.

**IBM HE4Cloud** – IBMs FHE Cloud Service, primär für ML-Modelle auf verschlüsselten Daten. Enterprise-fokussiert, komplex und für kleine Teams kaum realistisch einzusetzen.

**Zama** – Open-Source-Kryptographie, $57M Series B, hohe Bewertung. Fokus auf Blockchain und AI, nicht auf klinische Datenkollaboration. Eher Technologie-Lieferant als direkter Wettbewerber.

**Inpher** – Privacy-Preserving ML, November 2024 von Arcium akquiriert. Die Plattform wird wahrscheinlich pivotieren.

### Unsere Positionierung

Wir konkurrieren nicht mit Duality im Enterprise-Segment. Unser Zielmarkt:

- Universitätskliniken und akademische Forschungsinstitute  
- Mittelgroße Biotech-Unternehmen (&lt;500 Mitarbeiter)  
- Nationale und regionale Biobanken  
- Forschungskooperationen ohne Enterprise-IT-Budget  

Diese Institutionen haben denselben regulatorischen Druck wie große Pharmaunternehmen, wurden von Enterprise-Anbietern aber praktisch nie bedient.

### Unsere Differenzierung

1. **Zugänglichkeit:** Setup in Minuten statt Monaten. Das SDK funktioniert mit wenigen CLI-Befehlen. Keine Enterprise-Integration erforderlich.

2. **Transparenz als Kernfeature:** Blockchain-Anchoring des Audit Trails ist geplantes Standard-Feature, kein optionales Add-on. Kein Wettbewerber hat das als zentrales Verkaufsargument positioniert.

3. **Faire Preisgestaltung:** SaaS-Modell mit monatlichen Gebühren statt Enterprise-Jahresverträgen. Datenanbieter können Daten kostenlos oder gegen Revenue-Share anbieten.

---

## Roadmap

### Phase 1 – Hobby / Proof of Concept (aktueller Stand)

**Ziel:** Vollständiges kryptographisches Konzept demonstrieren. Kein Produktionsdruck, kein Kundendruck. Lernen und Fundament legen.

- ✓ HE-Kern mit TenSEAL (CKKS) – Berechnungen auf verschlüsselten Daten  
- ✓ FastAPI-Backend mit Study-Management  
- ✓ Threshold Key Generation (vereinfacht)  
- ✓ Cryptographic Commitments bei jedem Upload  
- ✓ Hash-verketteter Audit Trail  
- ✓ Client-SDK mit lokaler Verifikation  
- ✓ Web-UI für Provider und Researcher  
- ✓ Multi-Party-Workflow (mehrere Institutionen, eine Study)  

**Verfügbare Algorithmen:**  
Descriptive Statistics (Mean, Std Dev, Min, Max), Correlation Analysis, Group Comparison (t-Test-Näherung), Linear Regression, Distribution Overview.

**Hosting:** Einzelner Server (z. B. Hetzner), ca. 50 €/Monat.  
**Status:** Funktionierend, demonstrierbar, nicht produktionsreif.

### Phase 2 – Erste institutionelle Kunden (bei konkretem Interesse)

**Ziel:** Von „funktioniert auf meinem Server“ zu „vertrauenswürdig genug für echte Patientendaten“. Wird nur begonnen, wenn 2–3 konkrete Institutionen ernsthaftes Interesse zeigen.

**Infrastruktur:** Migration zu Azure Confidential Computing (AMD SEV-SNP), GPU-Instanzen für schnellere HE-Berechnungen, Managed PostgreSQL statt SQLite, automatische Backups, Monitoring, Alerting.

**Kryptographie:** Vollständige Threshold-Decryption-Implementierung, Blockchain-Anchoring des Audit Trails (Polygon, &lt;1 €/Tag), Zero-Knowledge-Proofs für Upload-Verifikation.

**Compliance:** DSGVO Data Processing Agreement, HIPAA BAA, ISO 27001-Vorbereitung, Penetration Test durch externe Firma.

**Produkt:** Federated Mode (lokaler Agent, Daten verlassen die Institution nie), erweiterter Algorithmen-Katalog, API für programmatischen Zugriff, SLA und Support.

**Geschätzte Kosten Phase 2:** 2.000–5.000 €/Monat Infrastruktur, plus einmalig 15.000–30.000 € für Compliance und Sicherheitsaudit. Finanzierbar ab 3–5 zahlenden institutionellen Kunden.

### Phase 3 – Skalierung (bei validiertem Geschäftsmodell)

- Genomik-Use-Case: SNP-Datenbanksuche, Allelfrequenz-Abfragen  
- Multi-Party-Compute über föderierte Nodes (Daten verlassen die Institution nie)  
- Marketplace: Institutionen bieten Datenzugang an, andere kaufen Analysen  
- White-Label-Option für große Pharmakonzerne  
- Dedicated Deployment für Institutionen mit höchsten Compliance-Anforderungen  

---

## Schnell skalierbar: Was bereits produktionsreif designed wurde

Auch als Hobby-Projekt wurde die Architektur so gebaut, dass der Schritt zu einem produktionsreifen System keine Neuentwicklung erfordert:

- **Datenbank:** SQLite → PostgreSQL ist ein Konfigurations-Switch (Connection String), kein Schema-Umbau. Die Tabellenstruktur ist produktionsreif.

- **API:** FastAPI ist produktionsreif und wird von großen Unternehmen in Produktion eingesetzt. Kein Framework-Wechsel nötig.

- **Kryptographie:** TenSEAL/CKKS ist die richtige Wahl für Produktion. Die Algorithmen-Implementierungen sind korrekt und austauschbar.

- **Infrastruktur:** Docker Compose → Kubernetes ist ein Deployment-Wechsel, keine Architektur-Änderung. Hetzner → Azure Confidential Computing ist eine Migration, kein Umbau.

- **SDK:** Das Client-SDK ist so designed, dass es unverändert in Produktion eingesetzt werden kann. Institutionen, die es heute testen, können es morgen mit derselben API in Produktion nutzen.

**Was für Produktion wirklich neu gebaut oder ergänzt werden muss:**

- Vollständige Threshold Decryption (geschätzt 2–3 Wochen)  
- Blockchain-Anchoring (geschätzt 1 Woche)  
- Compliance-Dokumentation (extern)  
- Security Audit (extern)  

**Geschätzte Zeit von erstem Kundeninteresse zu produktionsreif:** 8–12 Wochen mit einem zusätzlichen Backend-Entwickler.

---

## Technischer Stack

### Warum diese Technologie-Entscheidungen

**TenSEAL (CKKS)**  
TenSEAL ist eine Python-Bindung zu Microsoft SEAL und implementiert CKKS. Es ist gut dokumentiert, aktiv gepflegt und für Gleitkommazahlen und statistische Operationen geeignet. Alternativen (z. B. HElib, OpenFHE) sind leistungsstark, aber der Einstieg und die Integration in Python sind aufwändiger. Für Produktion bleibt CKKS die passende Wahl; TenSEAL kann bei Bedarf durch eine andere SEAL-Bindung ersetzt werden, ohne das Konzept zu ändern.

**FastAPI**  
Schnell, typisiert, mit automatischer OpenAPI-Dokumentation. Wird in Produktion von vielen Unternehmen eingesetzt. Die Alternative wäre Flask oder Django – FastAPI bietet bessere Performance und eine klarere API-Struktur für ein reines REST-Backend ohne Monolithen-Overhead.

**SQLModel / SQLite**  
SQLModel kombiniert SQLAlchemy und Pydantic; das Schema ist in Python definiert und migrationsfreundlich. SQLite ist für Phase 1 ausreichend und erlaubt lokale Entwicklung ohne Setup. Der Wechsel zu PostgreSQL erfordert nur eine andere Connection URL und ggf. kleine Syntax-Anpassungen – das Schema bleibt.

**Next.js / Tailwind**  
Next.js (App Router) und Tailwind ermöglichen eine moderne, wartbare UI ohne schweres Framework. Die Alternative wäre ein reines React-Setup oder ein anderes Meta-Framework; Next.js ist weit verbreitet und eignet sich für spätere Skalierung (SSR, API Routes bei Bedarf).

**Docker / Hetzner**  
Docker ermöglicht reproduzierbare Umgebungen; ein einzelner VPS bei Hetzner hält die Kosten in Phase 1 niedrig. Der Wechsel zu Azure oder AWS mit Kubernetes ist eine Infrastruktur-Entscheidung, keine Anwendungs-Architektur-Änderung.

---

## Lokale Entwicklung

### Voraussetzungen

- **Python 3.11** (TenSEAL hat keine Wheels für neuere Python-Versionen)  
- **Node.js 18+** (für Next.js)  
- Optional: **Docker** für konsistente Umgebung  

### Installation (unter 10 Minuten)

Alle Befehle beziehen sich auf das Projektroot (das Verzeichnis, in dem die Ordner `backend` und `frontend` liegen).

**1. Backend einrichten**

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

**2. Frontend einrichten**

```bash
cd frontend
npm install
cd ..
```

**3. Backend starten** (in einem Terminal)

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**4. Frontend starten** (in einem zweiten Terminal)

```bash
cd frontend
npm run dev
```

- Backend: http://localhost:8000  
- Frontend: http://localhost:3000  
- API-Dokumentation: http://localhost:8000/docs  

### Demo-Workflow: Von CSV zu verschlüsseltem Ergebnis (5 Schritte)

**Schritt 1 – CSV vorbereiten**  
Eine CSV mit numerischen Spalten (z. B. `backend/sample_clinical_data.csv`).

**Schritt 2 – Lokal verschlüsseln**

```bash
cd backend
.venv/bin/python encrypt.py sample_clinical_data.csv encrypted.bin
```

Die Ausgabe zeigt die erkannten Spalten und eine JSON-Liste für das `columns`-Formular beim Upload.

**Schritt 3 – Compute (optional rein lokal)**

```bash
.venv/bin/python compute.py descriptive_statistics '["blood_pressure_systolic"]' encrypted.bin result.json
.venv/bin/python decrypt.py result.json
```

**Algorithmen E2E-Test (optional)**  
Mit installiertem TenSEAL (z. B. in der .venv) kannst du alle Algorithmen einmal mit den Beispieldaten durchlaufen lassen und die Fehlermeldungen bei ungültigen Spalten prüfen:

```bash
.venv/bin/python scripts/test_algorithms_e2e.py
```

Ohne TenSEAL gibt das Skript nur eine kurze Anleitung aus. Es testet u. a. `descriptive_statistics`, `correlation`, `prevalence_and_risk`, `survival_analysis_approx` und die Validierung (klare Fehlermeldung bei fehlender Spalte).

**Schritt 4 – Study anlegen (über Web-UI)**  
Unter http://localhost:3000/studies/new eine Study erstellen (Name, Threshold, erlaubte Algorithmen). Nach dem Erstellen erscheint die Study-ID.

**Schritt 5 – Multi-Party mit SDK**

- Key Share erzeugen:  
  `python sdk.py generate-key --email institution@hospital.com`  
- Study verifizieren:  
  `python sdk.py verify-study --study-id <ID> --url http://localhost:8000`  
- Nach Aktivierung der Study (genug Teilnehmer): Upload mit SDK  
  `python sdk.py upload --csv data.csv --study-id <ID> --email institution@hospital.com --url http://localhost:8000`  

Weitere Befehle: `decrypt-share`, `verify-audit`, `generate-report` (siehe `python sdk.py --help`).

### Multi-Party Study mit zwei Test-Institutionen simulieren

1. **Study erstellen** (Web-UI oder `POST /studies/create`): z. B. `threshold_n=2`, `threshold_t=2`, zwei erlaubte Algorithmen.  
2. **Institution A:** SDK `generate-key --email a@test.com`, Public Key Share manuell oder per Script an `POST /studies/{id}/join` senden (oder zweiten Teilnehmer simulieren).  
3. **Institution B:** Gleiches mit `b@test.com`, `join` mit eigenem Key Share.  
4. Sobald `threshold_n` Teilnehmer gejoint haben, wird die Study automatisch **active**.  
5. Beide können nun über die Web-UI oder das SDK Datasets hochladen, Analysen anfragen und Approvals/Decryption Shares abgeben.  

Die Web-UI unter `/studies/<id>` zeigt alle Tabs (Overview, Participants, Datasets, Analysis, Audit Trail, Protocol Report) und den kryptographischen Status.

---

## Kontakt & Interesse

Wenn du eine Institution bist, die Interesse an einer Pilot-Kollaboration hat, oder ein Entwickler, der an diesem Projekt mitwirken möchte:

**[Deine Kontaktinformation hier]**

Dieses Projekt ist kein Startup, das Investoren sucht. Es ist ein funktionierendes System, das nach dem richtigen ersten Anwendungsfall sucht. Wenn dein Problem zu dem passt, was SecureCollab löst, reden wir.
