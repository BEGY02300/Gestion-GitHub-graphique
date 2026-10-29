# GitHub Desk

Application de bureau en français pour gérer les dépôts GitHub sans utiliser
le terminal au quotidien.

## Démarrer

1. Double-clique sur `Nouveau Fichier source Python.bat`.
2. Au premier lancement, le lanceur prépare un environnement Python isolé,
   installe pywebview et essaie d'installer GitHub CLI et Git avec winget
   (ou Chocolatey).
3. Connecte-toi une première fois avec GitHub CLI si l'application l'indique,
   puis relance `Nouveau Fichier source Python.bat`.

L'application utilise la connexion enregistrée localement par GitHub CLI ; elle
ne stocke pas de jeton GitHub dans ses fichiers.

## Cache local et synchronisation

GitHub Desk ouvre d'abord la dernière copie enregistrée sur ce PC. Au démarrage,
il demande avant de contacter GitHub s'il faut vérifier les changements ; sans
copie existante, la première synchronisation est nécessaire. Le bouton
« Vérifier les changements » relit la liste compacte des dépôts, n'enregistre
que les dépôts ajoutés ou modifiés et supprime du cache ceux qui ont disparu.
Les détails, README, branches, issues, pull requests et exécutions déjà lus
sont gardés dans le cache et chaque page propose une vérification ciblée.

Le cache SQLite et l'image de profil sont conservés dans
`%LOCALAPPDATA%\GitHubDesk\cache.sqlite3`. Il ne contient pas de jeton GitHub.
Les liens vers les dépôts, issues et pull requests s'ouvrent dans l'application ;
seul le bouton explicite « Ouvrir sur GitHub… » lance le navigateur.

## Fonctions

- Dépôts : liste, filtres, création, renommage, description, visibilité,
  archivage, réactivation, suppression et copie des fichiers vers une archive
  privée (créée automatiquement si elle n'existe pas). Les créations peuvent
  utiliser un modèle Python, Node.js, site web statique ou un dépôt modèle
  GitHub accessible. La colonne « Plan » permet aussi de choisir, dépôt par
  dépôt, conserver, archiver, archiver puis supprimer, ou supprimer sans copie.
- Branches : liste, création depuis une branche existante, renommage et
  suppression. La branche par défaut et les branches protégées sont bloquées
  contre la suppression.
- Pull requests : liste, création, fermeture et fusion. La fusion est refusée
  si GitHub ne déclare pas la PR propre et fusionnable.
- Issues : liste, création, modification, fermeture et réouverture.
- GitHub Actions : consulter les workflows et exécutions, relancer ou annuler
  une exécution.
- Statistiques : dépôts privés/publics/archivés, étoiles, forks et langages.
- Réglages, sécurité et accès : sujets (topics), options de dépôt, alertes de
  vulnérabilités et invitations/retraits de collaborateurs, selon les droits
  du compte GitHub.
- MCP : serveur local compatible MCP en lecture seule et client stdio pour
  connecter manuellement des serveurs MCP externes.

Les suppressions et autres actions sensibles demandent une confirmation.
La copie d'archive contient les fichiers de la révision, pas l'historique Git.
Vérifie toujours la visibilité avant de rendre un dépôt public.
Pour exécuter un plan de rangement, vérifie la liste résumée puis saisis
`EXECUTER PLAN`. Une source choisie pour « archiver puis supprimer » n'est
supprimée qu'après la publication réussie de sa copie dans l'archive privée.

## Modèles de dépôt

Dans « Nouveau dépôt », choisis un modèle intégré (Python, Node.js ou site
statique) pour créer un README et des fichiers de départ, ou indique le nom
`proprietaire/depot` d'un dépôt GitHub configuré comme modèle et accessible à
ton compte. GitHub crée alors le nouveau dépôt à partir de ce modèle.

## MCP

Dans l'onglet MCP, la configuration affichée permet d'ajouter GitHub Desk comme
serveur stdio à un client MCP compatible. Les outils exposés sont en lecture
seule et utilisent l'identité déjà connectée dans GitHub CLI ; ils peuvent donc
accéder aux dépôts privés auxquels ce compte a accès.

GitHub Desk peut aussi démarrer des serveurs MCP stdio externes. La commande et
les arguments sont enregistrés dans
`%APPDATA%\GitHubDesk\mcp-servers.json`. Un serveur ne démarre qu'après un clic
sur « Connecter », et ses outils ne s'exécutent qu'après un clic explicite.
N'ajoute que des programmes de confiance : leurs outils peuvent effectuer des
actions sur la machine ou les comptes auxquels ils sont connectés. N'inscris pas
de jeton ou de mot de passe dans les arguments.

## Prérequis

- Windows 10 ou 11 avec Python 3 installé.
- Une connexion Internet au premier lancement.
- Un compte GitHub connecté dans GitHub CLI.
- Le runtime Microsoft Edge WebView2, normalement présent sur Windows récent.
