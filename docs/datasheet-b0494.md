# Fiche technique — Arducam 108MP Motorized Focus USB3.0 Camera Module (B0494)

Source : datasheet V1.0 (20 janvier 2024). Référence pour le plan d'architecture
([plan-architecture-arducam-capture.md](plan-architecture-arducam-capture.md)).
Les valeurs sont celles du constructeur ; elles ne sont pas validées sur matériel.

## Capteur

| Paramètre | Valeur |
| --- | --- |
| Résolution | 108 MP, couleur, rolling shutter |
| Format optique / pixel | 1/1.52", 0,7 µm × 0,7 µm |
| Zone active | 12000 (H) × 9000 (V) |
| Format de sortie | YUY2 |
| IR | Filtre IR-cut intégré (lumière visible uniquement) |
| Cadence USB 3.0 | 1280×720 @ 60 fps ; 3840×2160 @ 10 fps ; 4000×3000 @ 7 fps (datasheet : « 4000×300 », probable coquille) ; 12000×9000 @ 1 fps |
| Cadence USB 2.0 | 1280×720 @ 10 fps |

## Optique

| Paramètre | Valeur |
| --- | --- |
| Mise au point | Motorisée |
| Champ de vision | 85° diag. × 70° horiz. × 57° vert. |
| Monture | Objectif fixe (stock) |
| Ouverture / focale | F1.89 / 5,89 mm |
| Plage de mise au point | 8 cm à l'infini |

## Interface, électrique, mécanique

- USB 3.2 Gen 1, rétrocompatible USB 2.0, connecteur Type-C, UVC (pas de pilote additionnel).
- Alimentation 5 V DC ± 5 % ; 1,25 W min, 1,92 W max.
- Température de fonctionnement 0 °C à 70 °C.
- Carte 34 × 34 mm, entraxe trous 28 × 28 mm (R2,5), profondeur 30 mm.
- OS supportés : Windows, Linux (exemples : PotPlayer, qv4l2).

## Contrôles UVC

- Disponibles : luminosité, contraste, saturation, balance des blancs auto/manuelle, gain,
  exposition auto/manuelle, mise au point manuelle.
- Affichés dans l'interface Windows (DirectShow) : teinte, netteté, gamma, contre-jour,
  anti-scintillement ; zoom, focus, exposition, iris, pan, tilt, roll, compensation faible luminosité.
  La présence réelle de chacun doit être détectée par l'adaptateur.
- Valeurs d'exemple : luminosité 0, contraste 10, saturation 10, balance des blancs 2498,
  gain 100, focus 416, exposition -11 (auto).

## Modes de fonctionnement (YUY2, 5 V)

| Mode | Résolution | fps max | Courant typ. | Puissance |
| --- | --- | --- | --- | --- |
| USB 3.0 | 6000×9000 (défaut pin de capture) | 1 | 384 mA | 1,92 W |
| USB 3.0 | 4000×3000 | 7 | 380 mA | 1,90 W |
| USB 3.0 | 3840×2160 (« 3480×2160 » dans le tableau) | 10 | 374 mA | 1,87 W |
| USB 3.0 | 1280×720 | 60 | 334 mA | 1,67 W |
| USB 3.0 | Repos | — | 102 mA | 0,51 W |
| USB 2.0 | 1280×720 | 10 | 250 mA | 1,25 W |
| USB 2.0 | Repos | — | 102 mA | 0,51 W |

Incohérences du datasheet à vérifier sur matériel : résolution pleine (12000×9000 en
capteur/cadence vs 6000×9000 en pin de capture), 4000×300 vs 4000×3000, 3480 vs 3840.

## Contact

www.arducam.com — support@arducam.com — +1 (319) 471-7640
