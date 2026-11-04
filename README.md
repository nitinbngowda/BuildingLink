# BuildingLink Badminton Court Automated Booking Scheduler

A lightweight, zero-dependency Python automation tool for booking amenities on [BuildingLink](https://www.buildinglink.com).

---

## How the API Works

Under the hood, BuildingLink uses:
1. **OAuth 2.0 PKCE with IdentityServer4**: The client authenticates against `https://auth.buildinglink.com/Account/Login` with client ID `vue-app`, receiving an authorization code which is exchanged for a JWT `access_token` and `refresh_token` at `/connect/token`.
2. **AWS API Gateway Subscription Key**: All requests to `https://amenityreservation-us1.buildinglink.com` require the header `x-api-key: hylwvvmjdgc45mt9kab1agriyvuh0nig9qx8djmu`.
3. **Availability Endpoint**: `GET /resident/amenities/{id}/available-slots?date={YYYY-MM-DD}` returns open 1-hour slots with both local building time and UTC timestamps.
4. **Reservation Endpoint**: `POST /resident/reservations` submits the reservation with resident contact info and UTC timestamps.
5. **Booking Rules**:
   - Limit: 1 reservation per unit per day.
   - Advance Notice: Bookings open 1 day in advance at 12:00 AM (midnight).
   - Hours: 6:00 AM to 10:00 PM.

---

## Configuration (`config.json`)

Configure your preferences in `config.json`:

```json
{
  "username": "nbyadarahalli",
  "password": "YOUR_PASSWORD",
  "amenity_id": "ba1bb1f4-980e-400c-8892-30dc37d20473",
  "amenity_name": "Badminton Court",
  "preferred_times": [
    "19:00",
    "20:00",
    "18:00",
    "21:00",
    "08:00"
  ],
  "days_ahead": 1,
  "description": ""
}
```

### Preferred Times:
- Priority order: The script checks each time in order and books the first one available.
- Supported time formats:
  - 24-hour: `"19:00"`, `"20:00"`, `"08:00"`
  - 12-hour: `"7:00 PM"`, `"8:00 PM"`, `"8am"`
  - Any slot: `["any"]` will book the earliest available slot.

---

## Usage

### 1. Test Run (Dry Run — Does NOT book)
Inspect available slots for tomorrow and see which slot would be booked:
```bash
py buildinglink_bot.py --dry-run
```

### 2. Override Preferred Time on the fly
```bash
py buildinglink_bot.py --dry-run --time "10:00 AM" "11:00 AM"
```

### 3. Check for a specific date
```bash
py buildinglink_bot.py --dry-run --date 2026-11-04
```

### 4. Immediate Booking
```bash
py buildinglink_bot.py
```

### 5. List Active Reservations
```bash
py buildinglink_bot.py --list
```

### 6. Cancel a Reservation
```bash
py buildinglink_bot.py --cancel <OCCURRENCE_ID>
```

---

## Scheduling Everyday at 12:00 AM Midnight

Because BuildingLink opens bookings 1 day ahead right at 12:00 AM midnight, you can schedule this using either method:

### Option A: Windows Task Scheduler (Recommended)

1. Press `Win + R`, type `taskschd.msc`, and press Enter.
2. Click **Create Basic Task...** in the right panel.
3. **Name**: `BuildingLink Badminton Booking`
4. **Trigger**: Select **Daily**, set time to **12:00:01 AM** (00:00:01).
5. **Action**: Select **Start a program**.
6. **Program/script**: `C:\Development\BuildingLink\run_daily.bat` (or browse to your `run_daily.bat`).
7. **Start in (optional)**: `C:\Development\BuildingLink`
8. Check **Open the Properties dialog** and click **Finish**.
9. In Properties:
   - Select **Run whether user is logged on or not**.
   - Check **Run with highest privileges**.

Logs are automatically written to `booking.log`.

---

### Option B: Built-in Python Background Scheduler

If your computer or server is left on:
```bash
py buildinglink_bot.py --schedule
```
This sleeps until exactly 12:00:00 AM midnight, automatically pre-authenticates 2 minutes before to acquire a fresh token, and submits the booking at the exact second midnight hits.

---

### Option C: Linux / macOS Cron

Add to crontab (`crontab -e`):
```cron
0 0 * * * cd /path/to/BuildingLink && python3 buildinglink_bot.py >> booking.log 2>&1
```

---

## Raw cURL Reference
See [CURL_GUIDE.md](CURL_GUIDE.md) for direct curl commands and payload specifications.

