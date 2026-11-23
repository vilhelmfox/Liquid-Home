# Liquid Home 1.6

**Ny version: 1.6.0 – automatisk parringskode og QR opsætning**

Liquid Home er en Home Assistant integration til iPad Air 1 med et Liquid Glass dashboard på seks felter, pauseskærm og telefonopsætning.

## Opdatering fra 1.5

1. Gå til **HACS → Liquid Home → ⋮ → Update information**.
2. Vælg **⋮ → Redownload**, og vælg **main** (hovedgrenen), hvis den vises. Der er endnu ikke en separat GitHub Release med versionsnummeret 1.6.0.
3. Genstart Home Assistant.
4. Gå til **Indstillinger → Enheder og tjenester → Liquid Home → Konfigurer** for at se din parringskode.

**Ved ny installation:** Tilføj Liquid Home via **Indstillinger → Enheder og tjenester → Tilføj integration**. Nu genererer Home Assistant selv en tilfældig parringskode.

**404 på /liquid_home/index.html?** Integrationens side findes først, efter integrationen er aktiveret. Se [installationsvejledningen på GitHub](https://github.com/vilhelmfox/Liquid-Home#readme).

**Bemærk:** Dette er en lokal prototype. HTTP er ikke krypteret; brug kun på et betroet netværk og eksponér ikke Home Assistant direkte mod internettet.
