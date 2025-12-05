"""
Mapping entre les IDs des zones de la carte et leurs noms descriptifs.
Utilisé pour afficher les noms compréhensibles dans le dashboard et les sessions.
"""

ZONE_NAMES = {
    "area": "Rando Homme",
    "area1": "Showroom Rando Mobilier",
    "area2": "Accueil",
    "area3": "Surf - Plage",
    "area4": "Junior Cycle",
    "area5": "Sports de Précision",
    "area6": "Fit Homme",
    "area7": "Fit Femme",
    "area8": "Fit Junior",
    "area9": "Santé Déc",
    "area10": "Cabines",
    "area11": "Encaissement",
    "area12": "Chaussant Rando + Femme",
    "area13": "Showroom Rando - Tentes + Couchages",
    "area14": "Basketball",
    "area15": "Équitation",
    "area16": "Chasse",
    "area17": "Cycle",
    "area18": "Natation",
    "area19": "SUP / Plongée / Voile",
    "area20": "Atelier",
    "area21": "Football",
    "area22": "SDR / Golf",
    "area23": "Showroom Fit",
    "area24": "Marche",
    "area25": "Running",
    "area26": "Pêche",
}


def get_zone_name(zone_id):
    """
    Retourne le nom descriptif d'une zone à partir de son ID ou nom.

    Args:
        zone_id (str): L'ID de la zone (ex: "area1", "area12") ou son nom (ex: "CYCLISME")

    Returns:
        str: Le nom descriptif de la zone, formaté en Title Case
    """
    if not zone_id:
        return "Zone inconnue"

    # Si c'est un ID de zone (areaX), utiliser le mapping
    if zone_id.lower().startswith('area'):
        zone_name = ZONE_NAMES.get(zone_id.lower(), zone_id)
        return zone_name

    # Sinon, c'est déjà un nom de zone (CYCLISME, RANDONNÉE, etc.)
    # Le formater en Title Case pour une meilleure lisibilité
    return zone_id.title()


def get_all_zones():
    """
    Retourne la liste de toutes les zones avec leurs noms.

    Returns:
        dict: Dictionnaire {zone_id: zone_name}
    """
    return ZONE_NAMES.copy()
