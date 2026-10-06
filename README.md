# MonitorBar Ubuntu 1.0.0

Une barre flottante CPU · RAM · GPU, adaptée du logiciel MonitorBar pour Mac.
Interface en français, sans compte ni télémétrie. Les mesures restent sur la machine.

## Télécharger et installer

Le fichier à proposer aux utilisateurs Ubuntu est **`monitorbar_1.0.0_all.deb`**, dans `dist/`.
L’archive **`MonitorBar-Ubuntu-1.0.0.zip`** contient également les sources, l’installateur,
les tests et cette documentation. Aucun compilateur ni installation par pip nécessaire.

Enregistrer le `.deb`, ouvrir un terminal dans son dossier et exécuter :

```sh
sudo apt update
sudo apt install ./monitorbar_1.0.0_all.deb
monitorbar
```

APT installe Python et PyQt5 depuis les dépôts Ubuntu si nécessaire. Une connexion
Internet et les droits administrateur sont nécessaires pour installer les dépendances.
L’application s’exécute ensuite avec les droits de l’utilisateur, **sans sudo**.
Le lanceur **MonitorBar** apparaît aussi dans le menu des applications.
Un double-clic sur le `.deb` peut ouvrir l’installateur graphique si celui-ci est disponible.

Depuis l’archive ZIP extraite :

```sh
cd MonitorBar-Ubuntu
sh install.sh
monitorbar
```

## Compatibilité

- Cibles : Ubuntu Desktop 22.04 et 24.04 LTS, avec Python 3.10 ou plus récent et PyQt5.
- Paquet `all` : code Python indépendant de l’architecture, utilisable sur amd64 et arm64
  lorsque les dépendances et pilotes sont disponibles. Ces architectures n’ont pas
  encore été toutes validées sur du matériel réel.
- X11 est le mode privilégié pour le placement, la transparence et la fenêtre au-dessus.
- Sous Wayland, le lanceur préfère automatiquement XWayland lorsque `DISPLAY` est
  disponible. En Wayland natif, le placement et le maintien au-dessus dépendent du
  compositeur et peuvent être restreints. Choisir une session X11 lorsqu’elle existe
  pour un comportement plus proche de la version Mac.
- L’apparition sur tous les espaces et au-dessus du plein écran dépend du gestionnaire
  de fenêtres. Ce comportement macOS n’est pas garanti par ce portage.
- L’icône de zone de notification apparaît si le bureau la prend en charge. Le clic
  droit directement sur la barre fonctionne également sans cette icône.

**État des vérifications :** voir `VALIDATION.md`. Le paquet est construit sur macOS ;
une installation réelle Ubuntu et les mesures sur matériel GPU ne sont pas encore certifiées.

## Utiliser et personnaliser

**Clic droit sur la barre** :

- Thèmes Terminal, Discret et Néon ; lueur néon ; couleurs communes ou par indicateur.
- Fond transparent ou semi-transparent avec curseur d’opacité.
- Couleurs selon la charge : vert sous 60 %, orange de 60 à 84 %, rouge dès 85 %.
- Libellés CPU / RAM / GPU ou symboles ⚙ / ▤ / ◇.
- Barre horizontale, colonne verticale ou capsules séparées.
- Espacement réglable de 0 à 80, retour à l’espacement normal.
- Indicateurs masquables, réordonnables, et courbes des 60 derniers relevés.
- Verrouillage de la position et de la taille ; alignement aux bords de l’écran.
- Choix du GPU lorsque plusieurs cartes sont détectées.
- Afficher la barre au centre ; quitter.

Glisser la barre pour la déplacer. Tirer les 24 pixels de son bord droit pour la
redimensionner de 60 % à 250 %. Les commandes Agrandir, Réduire et Taille normale
font la même chose. Le verrouillage empêche ces manipulations.

Les réglages sont sauvegardés dans `~/.config/monitorbar/settings.json` (ou
`$XDG_CONFIG_HOME/monitorbar/settings.json`). Les courbes repartent à zéro au lancement.
Un seul exemplaire est lancé à la fois dans la session. Pour retrouver la barre,
utiliser son icône de notification ; sinon fermer l’instance avec `pkill -f
'/usr/bin/python3 -m monitorbar'`, puis lancer `monitorbar --show-bar`.

## Mesures et GPU

**CPU** : différence des compteurs globaux de `/proc/stat`. Le temps inactif et
l’attente d’entrées-sorties ne sont pas comptés comme du travail CPU. Le premier
relevé est indisponible, car deux relevés sont nécessaires.

**RAM** : `(MemTotal - MemAvailable) / MemTotal`, d’après `/proc/meminfo`. La mémoire
récupérable par Linux n’est pas considérée comme occupée. Ce calcul diffère de macOS.

**GPU** : charge de la carte sélectionnée, avec les sources suivantes :

| Matériel | Source | Prérequis / limites |
| --- | --- | --- |
| NVIDIA | `nvidia-smi`, champ `utilization.gpu` | Pilote NVIDIA fonctionnel avec `nvidia-smi`. Certaines cartes ou modes ne fournissent pas cette mesure. |
| AMD et pilotes compatibles | `/sys/class/drm/card*/device/gpu_busy_percent` | Le pilote doit exposer un compteur lisible ; courant avec `amdgpu`. |
| Intel | `intel_gpu_top -J` | Paquet `intel-gpu-tools`, pilote compatible et accès aux compteurs PMU. Valeur du moteur le plus occupé, pas une somme. |

Installation de l’outil Intel optionnel :

```sh
sudo apt install intel-gpu-tools
intel_gpu_top -L
intel_gpu_top -J -s 500
```

Arrêter la commande de diagnostic avec Ctrl+C. Si elle indique « Permission denied »,
les permissions des compteurs de performance doivent être configurées par
l’administrateur de la machine. MonitorBar ne modifie pas la politique de sécurité,
ne change pas `perf_event_paranoid` et ne demande jamais de lancer l’interface en root.
Les GPU Intel récents utilisant `xe` dépendent aussi du support de la version installée
de `intel-gpu-tools` ; la présence d’un GPU Intel ne garantit pas une mesure.

Pour NVIDIA, vérifier que `nvidia-smi` fonctionne dans un terminal. Pour AMD, vérifier
que le fichier `gpu_busy_percent` correspondant existe et peut être lu.

Un GPU absent, non pris en charge ou inaccessible affiche **—**, jamais un faux 0 %.
L’infobulle et le menu indiquent la source ou l’indisponibilité. Le mode automatique
choisit la première carte détectée (NVIDIA en priorité) ; choisir explicitement une
carte hybride dans **Carte GPU** si nécessaire. Les cartes sont redétectées périodiquement.

Les relevés arrivent environ toutes les secondes plus la durée de lecture GPU.
Intel peut porter l’intervalle à environ 2,7 secondes. Les courbes représentent donc
60 **relevés**, pas nécessairement 60 secondes. La collecte tourne hors de l’interface.
L’interrogation d’un GPU dédié peut le réveiller et augmenter la consommation.

Sur Mac, « Metal » mesurait la mémoire de cette application rapportée à son budget.
Le nouveau pourcentage GPU Linux mesure une activité : les deux chiffres ne sont
pas comparables. Le style est reproduit avec Qt ; les polices et menus restent ceux
du bureau Linux.

Références techniques :
- [Compteur AMD du noyau Linux](https://www.kernel.org/doc/html/latest/gpu/amdgpu/thermal.html)
- [Documentation NVIDIA SMI](https://docs.nvidia.com/deploy/nvidia-smi/)
- [Manuel Ubuntu intel_gpu_top](https://manpages.ubuntu.com/manpages/noble/man1/intel_gpu_top.1.html)

## Démarrage automatique et suppression

Depuis l’archive extraite après installation :

```sh
sh autostart.sh enable
sh autostart.sh disable
```

Si seul le `.deb` a été téléchargé, ouvrir l’outil du bureau « Applications au
démarrage » et ajouter la commande `monitorbar`.

Désinstaller :

```sh
sudo apt remove monitorbar
```

Retirer également l’entrée MonitorBar des applications au démarrage si elle a été
ajoutée. Les préférences restent conservées ; supprimer le dossier
`~/.config/monitorbar` manuellement pour les effacer.

## Lancer depuis les sources sans installation du paquet

```sh
sudo apt install python3-pyqt5
sh monitorbar-run
```

Le dossier doit rester à son emplacement pour ce mode. Le paquet `.deb` est préférable
pour les utilisateurs finaux : il installe un lanceur global et gère les mises à jour.

## Développer, vérifier et distribuer

```sh
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 build_release.py
```

Le constructeur fonctionne aussi sur macOS avec `python3`. Il produit dans `dist/` :

- `monitorbar_1.0.0_all.deb` : paquet Ubuntu avec dépendances déclarées.
- `MonitorBar-Ubuntu-1.0.0.zip` : distribution complète, sources incluses.
- `SHA256SUMS` : empreintes SHA-256 des deux fichiers.

Pour vérifier les fichiers téléchargés sous Ubuntu, réunir ces trois fichiers puis :

```sh
sha256sum -c SHA256SUMS
```

Publier ces fichiers sur une page de téléchargement ou une release GitHub, accompagnés
des instructions d’installation ci-dessus. Aucun hébergement public n’est configuré
par ce dossier. Les empreintes vérifient l’intégrité, pas l’identité de l’éditeur.
Avant publication, effectuer la recette Ubuntu décrite dans `VALIDATION.md` et préciser
les conditions de licence du projet (voir `NOTICE.md`). Les futures versions devront
mettre à jour le numéro dans `__init__.py`, `build_release.py` et `install.sh`.

Un workflow `.github/workflows/ubuntu.yml` est fourni pour exécuter les tests et
l’installation sur Ubuntu 22.04 / 24.04 après publication du dépôt GitHub. Il ne
remplace pas les essais graphiques et GPU sur un vrai bureau.
