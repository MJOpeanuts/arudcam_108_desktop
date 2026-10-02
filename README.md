# Arducam Capture

Application locale Windows/Linux pour organiser les captures d'une caméra Arducam. Tant que les
tests avec la caméra B0494C ne sont pas réalisés, seule la caméra de démonstration est activée :
elle génère des images synthétiques et ne pilote aucun matériel.

## Développement

Python 3.12 ou plus récent est requis.

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell : .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,packaging]"
arducam-capture
```

L'interface écoute uniquement sur `127.0.0.1`. Les fichiers de données sont enregistrés dans le
répertoire utilisateur propre à l'OS ; `ARDUCAM_CAPTURE_DATA_DIR` permet de le remplacer. L'application
applique les migrations SQLite au démarrage. Pour lancer les tests : `pytest`. Vérifications de style
et de types : `ruff check .`, `ruff format --check .` et `mypy`.

Le paquet PyInstaller `onedir` est construit depuis la racine du dépôt avec :

```bash
pyinstaller packaging/pyinstaller.spec
```

L'installateur Windows `dist/Arducam Capture Setup.exe` (icône Bureau + menu Démarrer) se génère
ensuite avec [Inno Setup 6](https://jrsoftware.org/isinfo.php) : `iscc packaging/installer.iss`.
Au double-clic sur l'icône, l'interface s'ouvre automatiquement dans le navigateur ; le bouton
« Quitter » (barre latérale) ferme proprement l'application. Relancer l'icône alors que
l'application tourne rouvre simplement l'interface.

## État matériel

Les adaptateurs UVC Windows et V4L2 Linux sont volontairement différés : la plage des contrôles,
les modes 108 MP, le transport et le pilote requis doivent être vérifiés sur la caméra réelle avant
de choisir l'API native. Voir le protocole de validation de la caméra dans
[`docs/plan-architecture-arducam-capture.md`](docs/plan-architecture-arducam-capture.md).