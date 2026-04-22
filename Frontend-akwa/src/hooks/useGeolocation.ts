// hooks/useGeolocation.ts

export interface GeolocationResult {
  lat: number;
  lng: number;
}

export function getGeolocation(): Promise<GeolocationResult> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("La géolocalisation n'est pas supportée par ce navigateur."));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        });
      },
      (error) => {
        switch (error.code) {
          case error.PERMISSION_DENIED:
            reject(new Error("L'utilisateur a refusé la géolocalisation."));
            break;
          case error.POSITION_UNAVAILABLE:
            reject(new Error("La position est indisponible."));
            break;
          case error.TIMEOUT:
            reject(new Error("La demande de géolocalisation a expiré."));
            break;
          default:
            reject(new Error("Erreur de géolocalisation inconnue."));
        }
      },
      {
        enableHighAccuracy: true,  // GPS si disponible
        timeout: 8000,             // 8 secondes max
        maximumAge: 60000,         // Cache valide 1 minute
      }
    );
  });
}