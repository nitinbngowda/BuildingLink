# BuildingLink Badminton Booking — cURL API Reference

This document explains the raw API requests used by the BuildingLink web application for amenities booking.

---

## 1. Authentication & Headers

All requests to the amenity reservation API require two critical headers:
1. **`Authorization: Bearer <ACCESS_TOKEN>`** — The OAuth 2.0 JWT issued by `https://auth.buildinglink.com/connect/token`.
2. **`x-api-key: hylwvvmjdgc45mt9kab1agriyvuh0nig9qx8djmu`** — The AWS API Gateway subscription key used by BuildingLink's frontend.

---

## 2. Refreshing an Access Token with cURL

If you already have a `refresh_token`, you can generate a fresh 15-minute `access_token` directly via cURL:

```bash
curl -X POST "https://auth.buildinglink.com/connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
  -d "grant_type=refresh_token" \
  -d "client_id=vue-app" \
  -d "refresh_token=YOUR_REFRESH_TOKEN"
```

---

## 3. Querying Available Slots for a Date

**Endpoint:** `GET https://amenityreservation-us1.buildinglink.com/resident/amenities/{amenityId}/available-slots?date={YYYY-MM-DD}`

### cURL:
```bash
curl -X GET "https://amenityreservation-us1.buildinglink.com/resident/amenities/ba1bb1f4-980e-400c-8892-30dc37d20473/available-slots?date=2026-11-04" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "x-api-key: hylwvvmjdgc45mt9kab1agriyvuh0nig9qx8djmu" \
  -H "Accept: application/json" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
```

### Response Example:
```json
{
  "amenityId": "ba1bb1f4-980e-400c-8892-30dc37d20473",
  "date": "2026-11-04",
  "isOpen": true,
  "slotLengthMinutes": 60,
  "slots": [
    {
      "startUtc": "2026-11-04T13:00:00.0000000Z",
      "endUtc": "2026-11-04T14:00:00.0000000Z",
      "startLocal": "2026-11-04T08:00:00.0000000Z",
      "endLocal": "2026-11-04T09:00:00.0000000Z"
    },
    {
      "startUtc": "2026-11-04T14:00:00.0000000Z",
      "endUtc": "2026-11-04T15:00:00.0000000Z",
      "startLocal": "2026-11-04T09:00:00.0000000Z",
      "endLocal": "2026-11-04T10:00:00.0000000Z"
    }
  ]
}
```

---

## 4. Booking a Badminton Slot

**Endpoint:** `POST https://amenityreservation-us1.buildinglink.com/resident/reservations`

### cURL:
```bash
curl -X POST "https://amenityreservation-us1.buildinglink.com/resident/reservations" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "x-api-key: hylwvvmjdgc45mt9kab1agriyvuh0nig9qx8djmu" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
  -d '{
    "amenityId": "ba1bb1f4-980e-400c-8892-30dc37d20473",
    "contactName": "Nitin Byadarahalli",
    "contactEmail": "nitingowda223@gmail.com",
    "contactPhone": "+1 6478295886",
    "description": null,
    "startUtc": "2026-11-04T13:00:00.000Z",
    "endUtc": "2026-11-04T14:00:00.000Z",
    "isAllDay": false,
    "liabilityWaiverAccepted": false,
    "liabilityWaiverTypedResponse": null
  }'
```

---

## 5. Listing Your Current Reservations

**Endpoint:** `GET https://amenityreservation-us1.buildinglink.com/resident/reservations`

### cURL:
```bash
curl -X GET "https://amenityreservation-us1.buildinglink.com/resident/reservations?includePast=false&includeRecurring=false&pageNumber=0&pageSize=25" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "x-api-key: hylwvvmjdgc45mt9kab1agriyvuh0nig9qx8djmu" \
  -H "Accept: application/json" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
```

---

## 6. Canceling a Reservation

**Endpoint:** `POST https://amenityreservation-us1.buildinglink.com/resident/reservation-occurrences/{OCCURRENCE_ID}/cancel`

### cURL:
```bash
curl -X POST "https://amenityreservation-us1.buildinglink.com/resident/reservation-occurrences/5ab576e8-e1c5-4e12-9afc-9440fb2039fe/cancel" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "x-api-key: hylwvvmjdgc45mt9kab1agriyvuh0nig9qx8djmu" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "Accept: application/json" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
```

