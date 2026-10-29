# GitHub Desk

Application de bureau en français pour gérer les dépôts GitHub sans utiliser
le terminal au quotidien.

## Démarrer

1. Double-clique sur `Lancer.bat`.
2. Au premier lancement, le lanceur prépare un environnement Python isolé,
   installe pywebview et essaie d'installer GitHub CLI et Git avec winget
   (ou Chocolatey).
3. Connecte-toi une première fois avec GitHub CLI si l'application l'indique,
   puis relance `Lancer.bat`.

L'application utilise la connexion enregistrée localement par GitHub CLI ; elle
ne stocke pas de jeton GitHub dans ses fichiers.

## Fonctions

- Dépôts : liste, filtres, création, renommage, description, visibilité,
  archivage, réactivation, suppression et copie des fichiers vers une archive
  privée (créée automatiquement si elle n'existe pas).
- Branches : liste, création depuis une branche existante, renommage et
  suppression. La branche par défaut et les branches protégées sont bloquées
  contre la suppression.
- Pull requests : liste, création, fermeture et fusion. La fusion est refusée
  si GitHub ne déclare pas la PR propre et fusionnable.
- Issues : liste, création, modification, fermeture et réouverture.
- GitHub Actions : consulter les workflows et exécutions, relancer ou annuler
  une exécution.
- Statistiques : dépôts privés/publics/archivés, étoiles, forks et langages.

Les suppressions et autres actions sensibles demandent une confirmation.
La copie d'archive contient les fichiers de la révision, pas l'historique Git.
Vérifie toujours la visibilité avant de rendre un dépôt public.

## Prérequis

- Windows 10 ou 11 avec Python 3 installé.
- Une connexion Internet au premier lancement.
- Un compte GitHub connecté dans GitHub CLI.
- Le runtime Microsoft Edge WebView2, normalement présent sur Windows récent.
