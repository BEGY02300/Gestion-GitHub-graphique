# GitHub Desk

GitHub Desk est une application de bureau en français pour gérer ses dépôts,
branches, pull requests, issues, workflows et plans d'archivage sans utiliser
le site GitHub au quotidien.

## Télécharger l'application

Les versions Windows, macOS et Linux sont publiées dans
[GitHub Releases](https://github.com/BEGY02300/Gestion-GitHub-graphique/releases).
Télécharge l'archive correspondant à ton système, décompresse-la, puis ouvre
l'application qu'elle contient. Le site de présentation se trouve dans
[docs/](./docs/) et sera disponible sur
[GitHub Pages](https://begy02300.github.io/Gestion-GitHub-graphique/) quand
Pages sera activé pour ce dépôt.

Chaque publication propose un fichier de sommes SHA-256 pour vérifier que le
téléchargement n'a pas été altéré. Les versions ne sont pas signées
actuellement : les sommes de contrôle ne remplacent pas une signature éditeur,
et les avertissements SmartScreen ou d'autres antivirus peuvent encore
apparaître. N'ajoute pas l'application aux exclusions antivirus pour contourner
une alerte ; vérifie le code source et les sommes de contrôle, et signale les
faux positifs à l'éditeur de sécurité.

Sous Windows, compare la valeur du fichier `SHA256SUMS-windows.txt` au résultat
de `Get-FileHash .\\github-desk-windows-x64.zip -Algorithm SHA256`. Sous macOS ou
Linux, utilise `shasum -a 256 <archive>`.

## Compatibilité et prérequis

- **Windows 10 et 11, x64** : Microsoft Edge WebView2 et GitHub CLI (`gh`).
- **macOS** : version publiée construite pour l'architecture indiquée dans son
  nom ; GitHub CLI (`gh`) est requis.
- **Linux x64** : GTK 3, WebKit2GTK 4.1 et GitHub CLI (`gh`) sont requis.
- Pour les fonctions d'archivage qui clonent des dépôts, Git est aussi requis.
- Une connexion GitHub CLI autorisée est nécessaire. Connecte le compte une
  fois avec `gh auth login` dans un terminal ; les commandes exécutées ensuite
  par l'application ne créent pas de fenêtre de terminal sur Windows.

Les versions publiées sont créées par GitHub Actions depuis le code de ce
dépôt. Le projet ne télécharge pas de programme tiers en douce et ne désactive
pas les protections de sécurité.

## Développement

Python 3.11 ou plus récent est recommandé.

```text
python -m venv .venv
python -m pip install -r requirements.txt
python 1.py
```

Les commandes de développement sont affichées dans le terminal utilisé pour
lancer Python. Les versions installables, elles, sont construites sans console.

Pour construire l'application sur le système correspondant :

```text
python -m pip install -r requirements-build.txt
python tools/package.py
```

Le paquet est placé dans `dist/`. PyInstaller construit sur le système courant ;
il ne produit pas un exécutable macOS depuis Windows, ni l'inverse.

Pour publier le site, sélectionne **Settings → Pages → Source: GitHub Actions**
dans les réglages du dépôt. Les changements ultérieurs dans `docs/` déclenchent
le déploiement automatiquement. Pour créer les paquets, pousse un tag de version
comme `v1.0.0` ; GitHub Actions construit les trois plateformes et publie les
archives et leurs sommes SHA-256 dans Releases.

## Cache, confidentialité et fonctions

GitHub Desk ouvre d'abord la dernière copie enregistrée localement et demande
avant de vérifier les changements sur GitHub. Les jetons restent gérés par
GitHub CLI ; l'application n'en enregistre pas dans son cache.

Le cache SQLite et l'image du profil sont stockés dans le dossier utilisateur
de l'application (`%LOCALAPPDATA%\\GitHubDesk` sous Windows,
`~/Library/Application Support/GitHubDesk` sous macOS ou
`$XDG_DATA_HOME/GitHubDesk` sous Linux). Les liens de dépôts, issues et pull
requests s'ouvrent dans l'application ; seul le bouton explicite « Ouvrir sur
GitHub… » lance le navigateur.

Fonctions disponibles : dépôts privés et publics, création à partir de modèles,
branches, pull requests, issues, GitHub Actions, statistiques, options de
sécurité et d'accès, archivage, favoris locaux et client/serveur MCP. Les
suppressions et opérations sensibles demandent une confirmation.

Les outils MCP sont en lecture seule côté serveur intégré. Pour un serveur MCP
externe, n'ajoute que des programmes de confiance : leurs outils peuvent agir
sur la machine ou sur les comptes auxquels ils sont connectés.
