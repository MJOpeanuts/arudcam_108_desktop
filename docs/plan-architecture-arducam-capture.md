# Plan d'architecture — Arducam Capture

> Statut : **proposition en attente de validation**. Aucun code applicatif n'est généré à ce stade,
> conformément à la demande (« Attends ma validation du plan avant de générer le code. »).
>
> Nom provisoire de l'application : **Arducam Capture**
> Nom du package Python : `arducam_capture`

---

## 1. Reformulation du besoin et hypothèses

### 1.1 Reformulation

Le besoin est de fournir une application **100 % locale**, exécutable sur un poste Windows 11 x64
**sans Python installé** (via un packaging PyInstaller `onedir`), permettant à un opérateur de :

1. détecter et piloter une caméra USB Arducam 108 MP Motorized Focus (réf. B0494C) ;
2. visualiser un aperçu vidéo fluide à une résolution réduite ;
3. choisir une résolution de capture parmi les modes supportés par le pilote ;
4. régler manuellement la mise au point motorisée (0–1023) et les réglages réellement exposés par
   le pilote (exposition, gain, balance des blancs, luminosité, etc. — seulement s'ils existent) ;
5. déclencher une capture fiable (écriture atomique), y compris en haute résolution (opération
   potentiellement longue, à traiter en tâche asynchrone/non bloquante pour l'UI) ;
6. conserver un historique exhaustif et traçable des clichés (fichier + métadonnées SQLite) ;
7. explorer, filtrer, ouvrir, supprimer (avec confirmation) et exporter cet historique (CSV/XLSX).

L'architecture doit respecter une séparation stricte en couches (`domain`, `application`,
`infrastructure`, `platform`, `frontends`, `launcher`, `diagnostics`), le front Streamlit étant un
pur client des services applicatifs typés, sans accès direct à la caméra, au système de fichiers ou
à SQLite.

### 1.2 Hypothèses à valider explicitement (information manquante aujourd'hui)

Ces points **ne sont pas inventés** : ils sont listés comme hypothèses de travail à confirmer avant
ou pendant l'implémentation, notamment lors des tests avec la caméra réelle (voir section 9).

| # | Hypothèse | Impact si invalidée | À valider par |
|---|---|---|---|
| H1 | La caméra B0494C est reconnue comme webcam UVC (USB Video Class) standard par Windows et Linux, sans pilote propriétaire obligatoire. | Si un SDK propriétaire est requis, l'`CameraAdapter` Windows devra passer par ce SDK plutôt que par `DirectShow`/`Media Foundation` génériques. | Test matériel §9 |
| H2 | La mise au point motorisée est exposée via les contrôles UVC standard `CT_FOCUS_ABSOLUTE_CONTROL` (plage mappable sur 0–1023), accessible depuis les deux OS. | Si le focus n'est pilotable que via un utilitaire fournisseur, il faudra un adaptateur dédié (ex. appel à un exécutable/DLL Arducam). | Test matériel §9 |
| H3 | Les réglages exposition / gain / balance des blancs / luminosité sont disponibles comme contrôles UVC standard, mais leur présence effective et leurs bornes réelles sont inconnues tant que la caméra n'a pas été interrogée. | Détermine la liste des réglages affichés dynamiquement par `CameraControlService` (aucun réglage ne doit être affiché s'il n'est pas confirmé disponible). | Test matériel §9 |
| H4 | Le mode « 12000x9000 @ 1 fps » est un mode « still capture » (capture unique) plutôt qu'un flux vidéo continu, et n'est donc pas utilisable pour l'aperçu. | Si c'est un mode streaming classique, l'architecture de capture peut être simplifiée (pas de distinction preview/capture au niveau pilote). | Test matériel §9 |
| H5 | Le format YUYV est le format par défaut exposé en resolution maximale ; un éventuel mode MJPEG à plus haute résolution n'est pas garanti disponible. | Change l'encodeur utilisé lors de la conversion YUYV → fichier image (JPEG/PNG/TIFF). | Test matériel §9 |
| H6 | Une seule caméra Arducam est connectée à la fois (pas de multi-caméra simultanée dans la v1). | Simplifie `CameraDiscoveryService` (un seul device actif suivi en base `cameras`). | Confirmation métier |
| H7 | Le format de fichier de sortie attendu pour les clichés n'est pas précisé dans la demande : hypothèse de travail = **TIFF 16/8 bits ou PNG sans perte** par défaut (pas de JPEG avec perte), configurable. | Impacte la taille des fichiers et le champ `image_format` en base. | Confirmation métier |
| H8 | L'application est mono-utilisateur, mono-poste (pas de partage réseau de la base SQLite). | Cohérent avec « aucun port exposé sur le réseau » ; Streamlit sera lancé en `--server.address=127.0.0.1` et sans écoute externe. | Confirmation métier |
| H9 | Le pilote Linux utilisé en développement est `video4linux2` (V4L2) via un backend `OpenCV`/`v4l2-ctl`, Linux n'étant pas la cible finale de déploiement mais un environnement de développement/CI. | Change la portée des tests automatiques exécutables en CI (pas de caméra physique en CI → usage systématique du `FakeCameraAdapter`). | Confirmation métier |
| H10 | « Autofocus futur » signifie uniquement réserver un point d'extension dans `CameraAdapter`/`CameraControlService` (ex. méthode `set_autofocus(enabled: bool)` non implémentée ou levant `NotImplementedError` explicite), sans algorithme de netteté dans la v1. | Évite une implémentation prématurée et non demandée. | Confirmation métier |

### 1.3 Hors périmètre v1 (à confirmer)

- Autofocus logiciel (analyse de netteté) — préparé, non implémenté.
- Multi-caméra simultané.
- Édition/retouche d'image.
- Synchronisation réseau / cloud / partage multi-poste.
- Authentification utilisateur (application mono-poste, mono-session).

---

## 2. Différences Windows / Linux et risques pour le pilotage caméra

Le principe directeur : **ne jamais supposer qu'un contrôle disponible sous un OS l'est aussi sous
l'autre**. L'interface `CameraAdapter` abstrait ces différences ; chaque implémentation OS déclare
ses capacités réelles et le domaine/application n'affichent que ce qui est confirmé disponible.

### 2.1 Accès à l'image et à l'aperçu

| Aspect | Windows | Linux | Risque identifié |
|---|---|---|---|
| API bas niveau | Media Foundation (`IMFCaptureEngine`) ou DirectShow (legacy) | Video4Linux2 (V4L2) via `/dev/videoN` | Les deux API ont des modèles de négociation de format différents (Media Foundation : `IMFMediaType` ; V4L2 : `VIDIOC_S_FMT`). Une bibliothèque Python unique ne couvre pas idéalement les deux avec le même niveau de contrôle fin. |
| Bibliothèque candidate la plus portable | `OpenCV` (`cv2.VideoCapture`, backend `CAP_MSMF` ou `CAP_DSHOW`) | `OpenCV` (`cv2.VideoCapture`, backend `CAP_V4L2`) | OpenCV simplifie l'aperçu mais **limite fortement l'accès aux contrôles UVC avancés** (focus absolu, exposition manuelle précise) : le mapping des `cv2.CAP_PROP_*` vers les contrôles UVC réels n'est pas garanti fiable ni complet selon le backend. **Point à valider sur matériel réel (voir §9).** |
| Bibliothèque candidate pour contrôle fin UVC | `pygrabber` (wrapper DirectShow) ou appel direct à Media Foundation via `pymf`/`winrt` (support incertain) | `v4l2-python3` / appels directs `ioctl` (`VIDIOC_*`) ou `pyv4l2` | Aucune bibliothèque Python mature et activement maintenue ne couvre nativement et de façon fiable DirectShow/Media Foundation **et** V4L2 avec le même set de contrôles UVC (focus absolu 0–1023, etc.). Il faut probablement composer OpenCV (flux image) + un accès UVC complémentaire par OS pour les contrôles avancés. |
| Modes de capture « still » haute résolution (12000x9000@1fps) | Dépend du support du mode par le pilote UVC installé par Windows (pilote caméra UVC générique ou pilote Arducam dédié) | Dépend du pilote V4L2 exposé par le noyau Linux pour ce périphérique | Non confirmé : il est possible que ce mode ne soit accessible qu'en négociant un format USB spécifique non exposé simplement par `cv2.VideoCapture`. Nécessite un test caméra réelle. |

### 2.2 Contrôle de la mise au point motorisée (0–1023)

| Aspect | Windows | Linux | Risque |
|---|---|---|---|
| Contrôle UVC standard | `CameraControl_Focus` via DirectShow (`IAMCameraControl`) ou propriété Media Foundation équivalente | Contrôle V4L2 `V4L2_CID_FOCUS_ABSOLUTE` | La plage réelle (min/max/step) rapportée par le pilote peut différer de 0–1023 selon l'OS (ex. l'un rapporte 0–255, l'autre 0–1023) : **il faut lire dynamiquement les bornes du pilote et les mapper**, plutôt que de supposer 0–1023 de façon universelle. Le brief indique 0–1023 comme plage *annoncée* par le constructeur : à confirmer comme plage effective sur chaque OS. |
| Latence de déplacement | Inconnue | Inconnue | Le temps de stabilisation mécanique du focus avant capture n'est pas documenté : à mesurer lors du test matériel, pour éventuellement ajouter un délai de stabilisation avant capture. |

### 2.3 Réglages exposition / gain / balance des blancs / luminosité

| Aspect | Windows | Linux | Risque |
|---|---|---|---|
| Disponibilité | Contrôles UVC `CT_EXPOSURE_TIME_ABSOLUTE`, `CT_AE_MODE`, `PU_GAIN`, `PU_WHITE_BALANCE_TEMPERATURE`, `PU_BRIGHTNESS` exposés via DirectShow `IAMCameraControl` / `IAMVideoProcAmp` | Contrôles V4L2 `V4L2_CID_EXPOSURE_ABSOLUTE`, `V4L2_CID_GAIN`, `V4L2_CID_WHITE_BALANCE_TEMPERATURE`, `V4L2_CID_BRIGHTNESS` | Le set de contrôles réellement exposé par le pilote Arducam n'est pas garanti identique entre OS (certains constructeurs désactivent des contrôles automatiques UVC standard côté Windows). **Chaque adaptateur doit interroger le pilote à l'exécution et ne renvoyer que les contrôles confirmés disponibles** (`CameraCapabilities.supported_controls`), jamais une liste statique supposée. |

### 2.4 Cycle de vie / reconnexion USB

| Aspect | Windows | Linux | Risque |
|---|---|---|---|
| Déconnexion USB | Notification via WM_DEVICECHANGE / évènements WMI, ou simplement échec des appels suivants | Suppression du nœud `/dev/videoN`, erreurs `ENODEV` sur les appels V4L2 | Les deux OS nécessitent une détection *best effort* par échec d'appel (try/except sur lecture de frame et sur contrôle), car un évènement système fiable et portable n'est pas trivial à implémenter de façon unifiée en v1. `CameraDiscoveryService` doit re-sonder périodiquement la disponibilité. |
| Reconnexion | Le périphérique peut réapparaître sous un identifiant différent (index DirectShow) | Le périphérique peut réapparaître sous un `/dev/videoN` différent | L'identifiant stable à privilégier est le couple **VID:PID + numéro de série USB** si le pilote l'expose, plutôt que l'index d'énumération qui peut changer. À confirmer si le descriptor USB de la B0494C contient un numéro de série exploitable. |

### 2.5 Conclusion de l'analyse

- `CameraAdapter` doit être une interface strictement orientée « capacités déclarées + contrôles
  dynamiquement découverts », sans aucune valeur supposée par défaut.
- Deux implémentations concrètes dès la v1 : `WindowsCameraAdapter` (Media
  Foundation/DirectShow via une bibliothèque à confirmer, potentiellement complétée par `OpenCV`
  pour le flux image) et `LinuxV4L2CameraAdapter` (V4L2, utile surtout en développement/CI).
- Un `FakeCameraAdapter` (test double) est indispensable pour développer et tester sans matériel et
  sans dépendre de l'OS hôte du CI.
- Toute capacité non confirmée par un test matériel documenté (§9) reste marquée *provisoire* dans
  le code et la documentation.

---

## 3. Architecture détaillée et arborescence du dépôt

### 3.1 Principes

- **`domain`** : entités, value objects, règles métier pures, aucune dépendance externe (pas de
  SQLAlchemy, pas de Streamlit, pas de pilote caméra).
- **`application`** : services applicatifs typés (cas d'usage), orchestrent `domain` +
  `infrastructure` via des interfaces (ports) définies dans `domain`/`application`.
- **`infrastructure`** : implémentations techniques des ports : SQLAlchemy/SQLite, système de
  fichiers, export CSV/XLSX, pilotes caméra concrets.
- **`platform`** : détails liés à l'OS et à l'environnement d'exécution (chemins de données,
  verrou d'instance unique, horloge, journalisation structurée, configuration Pydantic).
- **`frontends`** : UI Streamlit, strictement consommatrice des services `application` (aucune
  logique métier, aucun accès direct DB/fichier/caméra).
- **`launcher`** : point d'entrée packagé (PyInstaller), démarrage du serveur Streamlit local,
  vérifications préalables (verrou, migrations Alembic, création des répertoires).
- **`diagnostics`** : collecte d'informations de diagnostic (versions, état caméra/pilote, état
  base, chemins, espace disque, journaux) consommées par la page *Diagnostic* et par le launcher.

### 3.2 Arborescence proposée

```
arudcam_108_desktop/
├── README.md
├── docs/
│   └── plan-architecture-arducam-capture.md        (ce document)
├── .github/
│   └── copilot-instructions.md                     (à écrire après validation du plan)
├── pyproject.toml                                   (dépendances, Ruff, mypy, pytest)
├── alembic.ini
├── src/
│   └── arducam_capture/
│       ├── __init__.py
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── models/
│       │   │   ├── camera.py          # Camera, CameraCapabilities, FocusRange, ControlSpec...
│       │   │   └── capture.py         # Capture, CaptureStatus, CaptureParameters...
│       │   └── errors.py              # Exceptions métier (CameraNotFoundError, ...)
│       ├── application/
│       │   ├── __init__.py
│       │   ├── ports/                 # Interfaces consommées par les services
│       │   │   ├── camera_adapter.py  # CameraAdapter (voir §4)
│       │   │   ├── capture_repository.py
│       │   │   ├── camera_repository.py
│       │   │   └── file_storage.py
│       │   └── services/
│       │       ├── camera_discovery_service.py
│       │       ├── camera_control_service.py
│       │       ├── preview_service.py
│       │       ├── capture_service.py
│       │       ├── capture_history_service.py
│       │       ├── export_service.py
│       │       └── diagnostic_service.py
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   ├── camera/
│       │   │   ├── windows_camera_adapter.py
│       │   │   ├── linux_v4l2_camera_adapter.py
│       │   │   └── fake_camera_adapter.py
│       │   ├── persistence/
│       │   │   ├── orm/               # Mapping SQLAlchemy 2 (modèles + Base)
│       │   │   │   ├── base.py
│       │   │   │   ├── camera_orm.py
│       │   │   │   └── capture_orm.py
│       │   │   ├── sqlalchemy_camera_repository.py
│       │   │   ├── sqlalchemy_capture_repository.py
│       │   │   └── session.py         # engine, session factory, PRAGMA (WAL, FK, timeout)
│       │   ├── storage/
│       │   │   └── local_file_storage.py   # écriture atomique, arborescence captures/YYYY/MM/DD
│       │   └── export/
│       │       ├── csv_exporter.py
│       │       └── excel_exporter.py
│       ├── platform/
│       │   ├── __init__.py
│       │   ├── config.py              # Pydantic Settings (ARDUCAM_CAPTURE_DATA_DIR, etc.)
│       │   ├── paths.py               # résolution des répertoires par défaut par OS
│       │   ├── logging_setup.py       # journalisation structurée
│       │   ├── instance_lock.py       # verrou d'instance unique
│       │   └── clock.py               # horloge UTC/local injectable (testabilité)
│       ├── frontends/
│       │   └── streamlit_app/
│       │       ├── app.py             # point d'entrée Streamlit, injection des services
│       │       └── pages/
│       │           ├── 1_camera.py
│       │           ├── 2_capture.py
│       │           ├── 3_historique.py
│       │           ├── 4_exports.py
│       │           └── 5_diagnostic.py
│       ├── launcher/
│       │   └── main.py                # entry-point PyInstaller : lock, migrations, run streamlit
│       └── diagnostics/
│           ├── __init__.py
│           └── report.py              # collecte des informations de diagnostic
├── migrations/                        # Alembic
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   └── application/
│   ├── integration/
│   │   ├── test_sqlite_repositories.py
│   │   ├── test_migrations.py
│   │   ├── test_atomic_capture_write.py
│   │   └── test_exports.py
│   └── fixtures/
│       └── fake_camera_adapter.py     # réutilise infrastructure/camera/fake_camera_adapter.py
└── packaging/
    └── pyinstaller.spec
```

### 3.3 Règles de dépendance entre couches

```
frontends  ──▶ application ──▶ domain
launcher   ──▶ application, platform, infrastructure
diagnostics──▶ application (lecture seule), platform
infrastructure ──▶ domain, application.ports (implémente les interfaces)
platform   ──▶ (aucune dépendance vers les autres couches métier)
domain     ──▶ (aucune dépendance externe)
```

Le front Streamlit n'importe **jamais** `infrastructure` ni `sqlalchemy` ni les pilotes caméra
directement : il reçoit des instances de services `application` déjà câblées (composition root dans
`launcher`/`frontends/streamlit_app/app.py`).

---

## 4. Interfaces Python principales

> Signatures à titre de proposition de contrat ; les types détaillés (`CameraCapabilities`, etc.)
> seront affinés lors de l'implémentation mais la forme ci-dessous fixe les engagements structurants.

### 4.1 `domain/models/camera.py` (extrait conceptuel)

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ControlKind(str, Enum):
    FOCUS_ABSOLUTE = "focus_absolute"
    EXPOSURE_ABSOLUTE = "exposure_absolute"
    GAIN = "gain"
    WHITE_BALANCE = "white_balance"
    BRIGHTNESS = "brightness"


@dataclass(frozen=True)
class ControlRange:
    minimum: int
    maximum: int
    step: int
    default: int | None


@dataclass(frozen=True)
class CameraCapabilities:
    """Capacités confirmées par le pilote au moment de l'interrogation.

    Aucun champ ne doit être renseigné par supposition : une capacité non confirmée
    doit être absente de `supported_controls` / `supported_resolutions`.
    """

    supported_resolutions: tuple[tuple[int, int], ...]
    supported_controls: dict[ControlKind, ControlRange]
    supports_autofocus: bool  # réservé, doit valoir False tant que non implémenté


@dataclass(frozen=True)
class CameraDescriptor:
    camera_id: str          # identifiant stable si possible (VID:PID[:serial]), sinon index
    name: str
    hardware_reference: str | None
    is_connected: bool
```

### 4.2 `application/ports/camera_adapter.py` — `CameraAdapter`

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from arducam_capture.domain.models.camera import CameraCapabilities, CameraDescriptor


class PreviewFrame(Protocol):
    """Image brute d'aperçu (format et dimensions définis par l'implémentation)."""

    width: int
    height: int
    data: bytes  # buffer image décodé (ex. RGB24) prêt à afficher


class CameraAdapter(ABC):
    """Port abstrait de pilotage caméra. Une implémentation par OS.

    Contrat : aucune méthode ne doit simuler une capacité non confirmée par le
    pilote réel ; en cas de doute, lever `CapabilityNotSupportedError` plutôt que
    de renvoyer une valeur par défaut inventée.
    """

    @abstractmethod
    def discover(self) -> list[CameraDescriptor]:
        """Énumère les caméras compatibles actuellement visibles par l'OS."""

    @abstractmethod
    def open(self, camera_id: str) -> None:
        """Ouvre une session de pilotage sur la caméra identifiée."""

    @abstractmethod
    def close(self) -> None:
        """Ferme proprement la session (libération des ressources OS)."""

    @abstractmethod
    def get_capabilities(self) -> CameraCapabilities:
        """Interroge le pilote et retourne les capacités réellement disponibles."""

    @abstractmethod
    def start_preview(self, width: int, height: int) -> None:
        """Démarre un flux d'aperçu à une résolution réduite et fluide."""

    @abstractmethod
    def read_preview_frame(self) -> PreviewFrame | None:
        """Retourne la dernière frame d'aperçu disponible, ou None si indisponible."""

    @abstractmethod
    def stop_preview(self) -> None:
        """Arrête le flux d'aperçu sans fermer la session caméra."""

    @abstractmethod
    def set_focus(self, value: int) -> None:
        """Positionne la mise au point motorisée (0-1023 selon capacité confirmée)."""

    @abstractmethod
    def get_focus(self) -> int | None:
        """Retourne la position actuelle de la mise au point, si lisible."""

    @abstractmethod
    def set_control(self, control: "ControlKind", value: int) -> None:
        """Applique un réglage (exposition, gain, etc.) si et seulement si supporté."""

    @abstractmethod
    def get_control(self, control: "ControlKind") -> int | None:
        """Lit la valeur actuelle d'un réglage, si lisible."""

    @abstractmethod
    def set_autofocus(self, enabled: bool) -> None:
        """Réservé à une extension future. Doit lever `NotImplementedError` en v1."""

    @abstractmethod
    def capture_still(self, width: int, height: int) -> "RawStillImage":
        """Capture une image fixe à la résolution demandée (opération potentiellement longue)."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Vérifie best-effort si la caméra répond encore (détection déconnexion USB)."""
```

`RawStillImage` est un objet domaine portant les octets bruts (ou décodés), la résolution
effective, le format source (ex. YUYV) et les paramètres caméra lus **au moment de la capture**
(valeurs effectivement relues du pilote, pas de simple recopie des valeurs demandées).

### 4.3 Services applicatifs (signatures indicatives)

```python
class CameraDiscoveryService:
    def list_available_cameras(self) -> list[CameraDescriptor]: ...
    def refresh_known_camera(self, camera_id: str) -> CameraDescriptor: ...

class CameraControlService:
    def get_capabilities(self, camera_id: str) -> CameraCapabilities: ...
    def set_focus(self, camera_id: str, value: int) -> None: ...
    def set_control(self, camera_id: str, control: ControlKind, value: int) -> None: ...

class PreviewService:
    def start(self, camera_id: str, width: int, height: int) -> None: ...
    def read_frame(self, camera_id: str) -> PreviewFrame | None: ...
    def stop(self, camera_id: str) -> None: ...

class CaptureService:
    def capture(self, camera_id: str, width: int, height: int) -> CaptureResult: ...
    # Garantit : écriture atomique (fichier temporaire + renommage), le statut
    # `captured` n'est persisté qu'après succès complet de l'écriture et du hash
    # SHA-256 ; en cas d'échec, nettoyage du temporaire + statut `failed` avec message.

class CaptureHistoryService:
    def list_captures(self, filters: CaptureFilters) -> list[CaptureSummary]: ...
    def get_capture(self, capture_id: str) -> CaptureDetail: ...
    def delete_capture(self, capture_id: str, confirmed: bool) -> None: ...
    def check_file_consistency(self, capture_id: str) -> ConsistencyStatus: ...

class ExportService:
    def export_csv(self, filters: CaptureFilters, delimiter: str) -> bytes: ...
    def export_excel(self, filters: CaptureFilters) -> bytes: ...

class DiagnosticService:
    def build_report(self) -> DiagnosticReport: ...
    # versions (python/paquets), état caméra/pilote, état base, chemins, espace disque, logs récents
```

Toutes les méthodes de service manipulent des **DTO typés** (dataclasses/Pydantic), jamais les
modèles SQLAlchemy ni les objets `CameraAdapter` bruts : c'est la frontière que le front Streamlit
ne doit jamais franchir.

---

## 5. Schéma SQLite initial

Conventions : clés primaires `TEXT` (UUID v4 str), horodatages UTC en `TEXT` ISO-8601
(`YYYY-MM-DDTHH:MM:SS.ffffff+00:00`) pour rester lisibles et triables lexicographiquement, montants
en octets en `INTEGER`. Activation `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`,
`PRAGMA busy_timeout = 5000`.

### 5.1 Table `cameras`

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | TEXT | PK | UUID du périphérique côté application |
| `device_key` | TEXT | UNIQUE NOT NULL | Identifiant stable (VID:PID[:serial] ou équivalent OS) |
| `name` | TEXT | NOT NULL | Nom rapporté par le pilote |
| `hardware_reference` | TEXT | NULL | Référence matériel si disponible (ex. `B0494C`) |
| `os_platform` | TEXT | NOT NULL | `windows` / `linux` au moment de la détection |
| `first_seen_at_utc` | TEXT | NOT NULL | Première détection |
| `last_seen_at_utc` | TEXT | NOT NULL | Dernière détection confirmée |
| `is_connected` | INTEGER | NOT NULL DEFAULT 0 | Booléen (0/1) |
| `capabilities_json` | TEXT | NULL | Dernier instantané de `CameraCapabilities` sérialisé (JSON), informatif uniquement |

Index : `UNIQUE (device_key)`.

### 5.2 Table `captures`

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | TEXT | PK | UUID du cliché |
| `camera_id` | TEXT | NOT NULL, FK → `cameras(id)` | Caméra utilisée |
| `file_name` | TEXT | NOT NULL | Nom de fichier |
| `relative_path` | TEXT | NOT NULL | Chemin relatif sous `captures/YYYY/MM/DD/` |
| `created_at_utc` | TEXT | NOT NULL | Horodatage UTC de création |
| `created_at_local` | TEXT | NOT NULL | Horodatage local affichable (dénormalisé pour affichage) |
| `width` | INTEGER | NOT NULL | Largeur effective |
| `height` | INTEGER | NOT NULL | Hauteur effective |
| `image_format` | TEXT | NOT NULL | Format fichier (ex. `png`, `tiff`) |
| `file_size_bytes` | INTEGER | NULL | Taille fichier (NULL si capture en échec sans fichier) |
| `focus_value` | INTEGER | NULL | 0–1023 ou NULL si non lisible |
| `exposure` | INTEGER | NULL | NULL si non supporté/non lisible |
| `gain` | INTEGER | NULL | NULL si non supporté/non lisible |
| `white_balance` | INTEGER | NULL | NULL si non supporté/non lisible |
| `brightness` | INTEGER | NULL | NULL si non supporté/non lisible |
| `extra_params_json` | TEXT | NULL | Autres paramètres supportés, sérialisés JSON (clé/valeur), jamais inventés |
| `capture_mode` | TEXT | NOT NULL | Ex. `still_12000x9000`, `still_4000x3000`, etc. |
| `capture_duration_ms` | INTEGER | NULL | Durée mesurée de la capture |
| `sha256` | TEXT | NULL | Empreinte du fichier (NULL si fichier non écrit) |
| `status` | TEXT | NOT NULL CHECK (`status` IN ('captured','missing','deleted','failed')) | Statut du cliché |
| `error_message` | TEXT | NULL | Message d'erreur exploitable si `status = 'failed'`/`'missing'` |

Index :
- `CREATE INDEX ix_captures_created_at_utc ON captures(created_at_utc);`
- `CREATE INDEX ix_captures_camera_id ON captures(camera_id);`
- `CREATE INDEX ix_captures_status ON captures(status);`
- `FOREIGN KEY (camera_id) REFERENCES cameras(id) ON DELETE RESTRICT`

### 5.3 Table `settings`

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `key` | TEXT | PK | Clé de configuration locale |
| `value` | TEXT | NULL | Valeur sérialisée (JSON si structuré) |
| `updated_at_utc` | TEXT | NOT NULL | Dernière mise à jour |

### 5.4 Migrations

- Alembic avec une révision initiale `0001_initial_schema` créant les trois tables, index et
  contraintes ci-dessus.
- `env.py` configuré pour utiliser la même URL SQLite que l'application (chemin issu de
  `ARDUCAM_CAPTURE_DATA_DIR/database/arducam_capture.db`), avec activation des `PRAGMA` nécessaires.
- Le `launcher` applique les migrations au démarrage (upgrade to `head`) avant d'ouvrir l'UI.

---

## 6. Dépendances candidates et justification

| Dépendance | Rôle | Justification |
|---|---|---|
| `streamlit` | Front local | Imposé par le cahier des charges ; exécution locale `127.0.0.1`, pas de port exposé réseau. |
| `sqlalchemy>=2.0` | ORM / Core | Imposé ; API 2.0 (typed, `Mapped[...]`) pour la couche `infrastructure/persistence`. |
| `alembic` | Migrations | Imposé ; gère l'évolution du schéma SQLite de façon versionnée et testable. |
| `pydantic>=2.0` / `pydantic-settings` | Configuration & validation | Imposé ; `pydantic-settings` pour charger `ARDUCAM_CAPTURE_DATA_DIR` et autres variables d'environnement de façon typée. |
| `opencv-python` (ou `opencv-python-headless`) | Accès flux vidéo multiplateforme (aperçu + fallback capture) | Bibliothèque la plus mature pour l'accès caméra multiplateforme en Python ; **limite connue** : accès incomplet aux contrôles UVC avancés (focus absolu, exposition manuelle précise) → à compléter par un accès UVC natif par OS (voir ci-dessous). *Choix à confirmer après test matériel §9.* |
| `pygrabber` (Windows uniquement) | Énumération + accès DirectShow avancé | Candidat pour lister les devices DirectShow et piloter certains contrôles caméra sous Windows ; maintenance et couverture des contrôles UVC à vérifier sur la caméra réelle. |
| `v4l2-python3` ou appels `fcntl.ioctl` directs avec les constantes `linux/videodev2.h` (Linux) | Contrôle fin UVC (focus, exposition, gain...) | Nécessaire si `opencv-python` ne couvre pas tous les contrôles UVC requis ; usage principalement en développement/CI (cible finale = Windows). |
| `Pillow` | Encodage/décodage image (YUYV → PNG/TIFF, génération miniatures) | Bibliothèque standard, légère, bien supportée par PyInstaller. |
| `numpy` | Manipulation de buffers image bruts | Dépendance naturelle d'OpenCV et utile pour la conversion YUYV → RGB. |
| `openpyxl` | Export `.xlsx` | Imposé explicitement pour l'export Excel. |
| `pytest`, `pytest-cov` | Tests | Imposé ; `pytest-cov` pour mesurer la couverture des couches `domain`/`application`. |
| `ruff` | Lint/format | Imposé pour la qualité de code. |
| `mypy` | Typage statique | Imposé ; strict sur `domain` et `application` au minimum. |
| `pyinstaller` | Packaging `onedir` | Imposé pour la distribution sans Python préinstallé. |
| `portalocker` ou implémentation maison (`msvcrt`/`fcntl`) | Verrou d'instance unique | `portalocker` offre une API multiplateforme simple pour le verrou fichier ; alternative : implémentation native par OS dans `platform/instance_lock.py` pour limiter les dépendances. *Arbitrage à faire lors de l'implémentation.* |
| `structlog` ou `logging` stdlib + formatter JSON | Journalisation structurée | `logging` stdlib suffit généralement (moins de dépendances pour PyInstaller) ; `structlog` apporte une API plus ergonomique si le besoin de structuration est important. *Arbitrage à faire lors de l'implémentation, stdlib privilégié par défaut pour limiter la surface de packaging.* |

**Points ouverts nécessitant validation matérielle avant de figer ce tableau** : couverture réelle
des contrôles UVC par `opencv-python` seul sur la B0494C (focus absolu notamment), et nécessité ou
non d'une dépendance Windows dédiée (`pygrabber` ou accès Media Foundation natif). Voir §9.

---

## 7. Tests et critères d'acceptation de la v1

### 7.1 Stratégie de tests

- **Unitaires `domain`** : règles de validation (ex. focus borné 0–1023, transitions de statut
  `captured`/`missing`/`deleted`/`failed`), sans dépendance externe.
- **Unitaires `application`** : chaque service testé avec des doubles de test (`FakeCameraAdapter`,
  repositories en mémoire ou SQLite temporaire), notamment :
  - `CaptureService` : succès nominal, échec d'écriture fichier (nettoyage + statut `failed`),
    cohérence du hash SHA-256.
  - `CameraControlService` : rejet des valeurs hors bornes, absence de réglage non supporté.
  - `CaptureHistoryService` : détection d'un fichier manquant (`missing`), suppression cohérente
    fichier + base, filtres (période, caméra, statut).
  - `ExportService` : neutralisation des cellules formule, BOM UTF-8 CSV, génération `.xlsx`.
- **Intégration SQLite** : base temporaire (`tmp_path`), `PRAGMA foreign_keys`, contraintes
  `CHECK`, index, `ON DELETE RESTRICT`.
- **Tests de migrations Alembic** : `upgrade head` sur base vierge temporaire, puis vérification du
  schéma obtenu (tables/colonnes/index attendus).
- **Tests d'écriture atomique** : simulation d'interruption pendant l'écriture (fichier temporaire
  non renommé), vérification qu'aucun enregistrement `captured` n'existe sans fichier final valide.
- **Tests de cohérence fichier/base** : suppression manuelle d'un fichier hors application puis
  détection du statut `missing` par `CaptureHistoryService`.
- **Tests exports CSV/XLSX** : contenu, encodage, séparateur configurable, colonnes choisies,
  chemin relatif présent, absence d'image embarquée.
- **Tests de déconnexion caméra** : `FakeCameraAdapter` simulant une perte de connexion en cours
  d'aperçu/capture, vérification de la remontée d'erreur exploitable et de l'absence de crash UI.
- **Test manuel documenté (caméra réelle)** : protocole écrit (non automatisé) à exécuter sous
  Windows puis sous Linux avec la caméra B0494C branchée, couvrant détection, aperçu, changement de
  résolution, focus, réglages disponibles, capture 108 MP, historique, suppression, export.

### 7.2 Critères d'acceptation v1 (proposition)

1. Avec une caméra détectée (réelle ou `FakeCameraAdapter`), l'état et les capacités affichées
   correspondent exactement à ce que retourne `CameraAdapter.get_capabilities()` (aucun contrôle
   fictif affiché).
2. L'aperçu démarre à une résolution différente de la résolution de capture choisie et reste
   réactif (pas de blocage de l'UI Streamlit observé pendant l'aperçu).
3. Une capture réussie crée **un et un seul** enregistrement `captures` avec `status = 'captured'`,
   un fichier présent sur disque, un `sha256` correct et un `file_size_bytes` cohérent avec le
   fichier réel.
4. Une capture interrompue/en échec ne laisse **aucun** fichier temporaire orphelin et produit un
   enregistrement `status = 'failed'` avec `error_message` renseigné (ou aucun enregistrement,
   selon la politique retenue à l'implémentation — à trancher explicitement, voir §1.3/points
   ouverts).
5. L'historique est filtrable par période, caméra et statut, et chaque ligne reflète fidèlement les
   colonnes du schéma §5.2.
6. La suppression d'un cliché, après confirmation, supprime le fichier et marque/supprime
   l'enregistrement de façon cohérente (pas d'état où l'un existe sans l'autre, sauf transition
   explicite vers `missing`/`deleted` documentée).
7. L'export CSV est lisible dans Excel avec BOM UTF-8, les cellules commençant par `=`, `+`, `-`,
   `@` sont neutralisées, et l'export XLSX s'ouvre sans erreur avec les mêmes données.
8. L'application démarre sans connexion Internet, sans téléchargement, avec un seul process actif
   (verrou d'instance), et n'ouvre aucun port réseau accessible depuis l'extérieur de la machine.
9. L'intégralité de la suite de tests automatisés (`pytest`) passe sans caméra physique connectée,
   grâce au `FakeCameraAdapter`.
10. `ruff` et `mypy` ne rapportent aucune erreur bloquante sur `src/arducam_capture`.

---

## 8. Plan d'implémentation incrémental

> Chaque étape doit rester testable et mergeable indépendamment, sans casser les étapes précédentes.

1. **Socle projet** : `pyproject.toml`, configuration Ruff/mypy/pytest, arborescence de dossiers
   vide avec `__init__.py`, `.github/copilot-instructions.md` (après validation du présent plan).
2. **`platform`** : configuration Pydantic (`ARDUCAM_CAPTURE_DATA_DIR` et dérivés), résolution des
   chemins par OS, création idempotente de l'arborescence de données, verrou d'instance unique,
   journalisation structurée. Tests unitaires de résolution de chemins par OS (mock `os.name`/env).
3. **`domain`** : modèles `Camera*`, `Capture*`, exceptions métier, règles de validation (bornes
   focus, transitions de statut). Tests unitaires purs.
4. **Persistance** : modèles SQLAlchemy 2, session/engine avec PRAGMA (WAL, FK, timeout), migration
   Alembic initiale, repositories `camera`/`capture`. Tests d'intégration SQLite + tests migration.
5. **`FakeCameraAdapter`** + interface `CameraAdapter` finalisée. Permet de développer et tester
   tous les services sans matériel ni dépendance OS.
6. **Services applicatifs** (`CameraDiscoveryService`, `CameraControlService`, `PreviewService`,
   `CaptureService`, `CaptureHistoryService`) branchés sur `FakeCameraAdapter` + persistance réelle.
   Tests unitaires/intégration associés (écriture atomique, cohérence fichier/base).
7. **Export** (`ExportService`, `csv_exporter`, `excel_exporter`) + `DiagnosticService`. Tests
   dédiés (neutralisation formules, BOM, colonnes, rapport de diagnostic).
8. **Front Streamlit** : les 5 pages, consommant exclusivement les services `application` via une
   composition root. Pas de logique métier dans les fichiers de pages.
9. **`launcher`** : vérifications au démarrage (verrou, migrations, répertoires), lancement du
   process Streamlit local, configuration PyInstaller `onedir` (`packaging/pyinstaller.spec`).
10. **Implémentation `LinuxV4L2CameraAdapter`** (développement/CI) puis validation matérielle (§9)
    avant de démarrer l'implémentation `WindowsCameraAdapter` définitive, afin de ne pas figer de
    choix de bibliothèque Windows avant confirmation des capacités réelles de la caméra.
11. **`WindowsCameraAdapter`** définitif, ajustement de `CameraCapabilities` selon les résultats de
    validation matérielle, puis exécution du protocole de test manuel documenté sous Windows et
    Linux avec la caméra B0494C.
12. **Durcissement** : gestion des cas de déconnexion USB en cours d'aperçu/capture, détection des
    fichiers manquants en tâche de fond ou à la demande, finalisation de la page *Diagnostic*.

---

## 9. Validations matérielles requises avant de figer les choix techniques

Ces validations doivent être réalisées avec la caméra B0494C physique, sous Windows 11 **et** sous
Linux, avant de verrouiller définitivement les bibliothèques et les plages de contrôle :

1. **Énumération** : la caméra est-elle listée comme device UVC standard par `cv2.VideoCapture`
   (`CAP_MSMF`/`CAP_DSHOW` sous Windows, `CAP_V4L2` sous Linux) ? Un identifiant stable (VID:PID et
   éventuellement numéro de série) est-il récupérable sous chaque OS ?
2. **Modes de résolution/fréquence** : confirmer que les modes `12000x9000@1fps`, `4000x3000@7fps`,
   `3840x2160@10fps`, `1280x720@60fps` sont effectivement négociables via l'API retenue sur chaque
   OS, et déterminer si le mode 108 MP est un mode flux ou un mode « still capture » dédié.
3. **Format YUYV** : confirmer la disponibilité du format YUYV à chaque résolution testée, et
   vérifier l'existence ou non d'un mode MJPEG alternatif à haute résolution.
4. **Focus motorisé** : mesurer la plage réelle rapportée par le pilote sur chaque OS (bornes
   min/max/step), le temps de stabilisation mécanique, et confirmer la méthode d'accès effective
   (contrôle UVC standard vs utilitaire/SDK propriétaire).
5. **Réglages avancés** : déterminer la liste exacte des contrôles UVC exposés et lisibles/
   modifiables par le pilote (exposition, gain, balance des blancs, luminosité, autres), avec leurs
   bornes réelles, sur chaque OS.
6. **Couverture OpenCV vs accès natif** : vérifier si `cv2.VideoCapture`/`cv2.VideoCapture.set`
   suffisent à piloter le focus absolu et les réglages ci-dessus, ou si un accès complémentaire
   (DirectShow natif sous Windows, `ioctl` V4L2 sous Linux) est nécessaire.
7. **Identifiant stable** : confirmer si un numéro de série USB est exposé par le descripteur du
   périphérique, utilisable comme clé stable en base (`cameras.device_key`) indépendamment de
   l'ordre d'énumération.
8. **Comportement en déconnexion/reconnexion USB** : observer le comportement réel des appels
   (exceptions, timeouts, codes d'erreur) lors d'un débranchement à chaud pendant un aperçu et
   pendant une capture, sur chaque OS.
9. **Durée réelle d'une capture 108 MP** : mesurer le temps d'acquisition et de transfert à pleine
   résolution, pour calibrer l'UX (indicateur de progression, timeout éventuel) dans `CaptureService`
   et la page *Capture*.
10. **Pilote Windows requis** : déterminer si Windows 11 reconnaît la caméra nativement comme
    périphérique UVC (pilote intégré) ou si un pilote fournisseur doit être installé manuellement
    sur l'UC cible — ceci conditionne la documentation d'installation du poste final (hors
    périmètre applicatif mais à documenter pour l'exploitant).

**Tant que ces points ne sont pas validés sur la caméra réelle, les bibliothèques listées en
section 6 pour l'accès aux contrôles UVC avancés (`pygrabber`, `v4l2-python3`) restent des
candidats et ne doivent pas être considérées comme un choix définitif.**

---

## Prochaine étape

Ce plan attend une validation explicite avant toute génération de code applicatif
(`src/arducam_capture/...`), conformément à la demande initiale. Les points marqués *à confirmer*
ou *hypothèse* dans ce document doivent être tranchés (ou acceptés comme hypothèses de travail)
avant de démarrer l'étape 1 du plan d'implémentation (§8).
