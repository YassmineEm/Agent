import math


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule la distance en km entre 2 points GPS.
    Formule de Haversine.
    """
    R = 6371  # rayon de la Terre en km

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return round(R * c, 3)