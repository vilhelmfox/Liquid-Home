# Liquid Home 1.5 — HACS-klar prototype

Liquid Glass pauseskærm og et 3 × 2 dashboard til gamle iPads (iOS 12), med opsætning fra telefonen ved QR kode.

## Installation — ingen YAML eller manuel kopiering af HTML

**Forudsætning:** Projektet skal ligge i et GitHub repository, før det kan tilføjes som *Custom Repository* i HACS. ZIP filen er **ikke** et HACS-installationslink, og repoet er ikke publiceret automatisk.

1. Læg hele dette projekts indhold i roden af et GitHub repository.
2. Åbn HACS i Home Assistant → tre prikker → **Custom repositories** → indsæt repositoryets URL → kategori **Integration**.
3. Installér **Liquid Home** og genstart Home Assistant.
4. Gå til **Indstillinger → Enheder og tjenester → Tilføj integration → Liquid Home**.
5. Vælg en parringskode på mindst 12 tegn i installationsdialogen. Ingen `configuration.yaml`.
6. Åbn `http://homeassistant.local:8123/liquid_home/index.html` på iPad'en.
7. Scan QR koden med telefonen. Angiv parringskoden én gang på telefonen for at godkende.
8. Tryk på felterne på iPad'en og vælg enheder fra listen på telefonen.

### Eksisterende bruger af v1.4
Fjern den gamle `liquid_home:` sektion fra `configuration.yaml` **en enkelt gang**, før du genstarter med v1.5, da den gamle variant ellers kan skabe forvirring. Ingen efterfølgende filredigering er nødvendig. HACS kan ikke importere en gammel YAML-adgangskode automatisk. En gammel hjemmeskærmsgenvej til `/local/liquid-home.html` skal oprettes på ny med `/liquid_home/index.html`.

### Sikkerhed og begrænsninger
- Dette er en **prototype**, ikke sikkerhedsrevideret eller testet på din konkrete Raspberry Pi 5 og iPad Air 1.
- Parringskoden og den særskilte enhedsnøgle kan opsnappes over HTTP. Brug kun et betroet lokalt net og eksponér **aldrig** porten mod internettet. HTTPS anbefales, hvor muligt.
- Integrationens enhedsnøgle er begrænset til de valgte entiteter og handlinger, men er ikke en erstatning for netværkskryptering.
- QR parring er en lokal session på 15 minutter.
- Et LLAT er ikke nødvendigt: integrationen kan kalde Home Assistants interne service API.
- Telefonen skal kende parringskoden. Vi kan senere erstatte dette med en godkendelsesdialog fra Home Assistant.
- Der kræves fortsat en første installation af en integration via HACS og en GitHub repositoryadresse. HACS kan ikke installere direkte fra denne ZIP fil.
