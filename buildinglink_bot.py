#!/usr/bin/env python3
"""
BuildingLink Badminton Court Automated Booking Scheduler
=========================================================
Automates resident amenity booking on BuildingLink using official OAuth2 PKCE
and Amenity Reservation APIs.
"""

import os
import sys
import json
import time
import base64
import hashlib
import urllib.request
import urllib.parse
import http.cookiejar
import re
import argparse
from datetime import datetime, timedelta

# Constants
DEFAULT_AMENITY_ID = "ba1bb1f4-980e-400c-8892-30dc37d20473"  # Badminton Court
API_KEY = "hylwvvmjdgc45mt9kab1agriyvuh0nig9qx8djmu"
AUTH_BASE_URL = "https://auth.buildinglink.com"
AMENITY_BASE_URL = "https://amenityreservation-us1.buildinglink.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class BuildingLinkClient:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = 0
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def refresh(self):
        """Refreshes the access token using the OAuth2 refresh_token grant."""
        if not self.refresh_token:
            return False
        token_data = {
            'grant_type': 'refresh_token',
            'client_id': 'vue-app',
            'refresh_token': self.refresh_token
        }
        token_req = urllib.request.Request(
            f"{AUTH_BASE_URL}/connect/token",
            data=urllib.parse.urlencode(token_data).encode(),
            headers={
                'User-Agent': USER_AGENT,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        try:
            with self.opener.open(token_req) as token_resp:
                tokens = json.loads(token_resp.read().decode())
                self.access_token = tokens['access_token']
                if 'refresh_token' in tokens:
                    self.refresh_token = tokens['refresh_token']
                self.token_expiry = time.time() + tokens.get('expires_in', 900) - 30
            print("[+] Token refreshed successfully via refresh_token.")
            return True
        except Exception as e:
            print(f"[*] Token refresh failed ({e}), falling back to full login...")
            return False

    def login(self, force=False):
        """Authenticates using OAuth 2.0 Authorization Code flow with PKCE."""
        # If token is already valid and not forcing fresh login, reuse it
        if not force and self.access_token and time.time() < self.token_expiry:
            return self.access_token

        # Try fast refresh_token first if available
        if self.refresh_token and self.refresh():
            return self.access_token

        print(f"[*] Authenticating with BuildingLink as '{self.username}'...")
        
        # 1. Generate PKCE verifier and challenge
        code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('ascii')).digest()).decode('utf-8').rstrip('=')
        state = os.urandom(16).hex()

        auth_params = {
            'client_id': 'vue-app',
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'redirect_uri': 'https://www.buildinglink.com/voidc-callback',
            'response_type': 'code',
            'scope': 'openid profile email buildinglink internal_website_apis uuids offline_access',
            'state': state
        }
        auth_url = f"{AUTH_BASE_URL}/connect/authorize?" + urllib.parse.urlencode(auth_params)

        req = urllib.request.Request(auth_url, headers={'User-Agent': USER_AGENT})
        with self.opener.open(req) as resp:
            login_html = resp.read().decode('utf-8')
            login_url = resp.geturl()

        # Check if already authenticated via active session cookies
        parsed_url = urllib.parse.urlparse(login_url)
        qs = urllib.parse.parse_qs(parsed_url.query)
        auth_code = qs.get('code', [None])[0]

        if not auth_code:
            # Extract __RequestVerificationToken and ReturnUrl
            token_match = re.search(r'name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', login_html)
            if not token_match:
                # If cookies were stale or corrupted, clear cookie jar and retry once cleanly
                if len(self.cj) > 0:
                    print("[*] Stale session detected. Clearing cookies and retrying login...")
                    self.cj.clear()
                    return self.login(force=True)
                raise RuntimeError("Failed to find __RequestVerificationToken on login page")

            req_token = token_match.group(1)
            return_url = qs.get('ReturnUrl', [''])[0]

            # 2. Submit credentials
            login_data = {
                'Username': self.username,
                'Password': self.password,
                'ReturnUrl': return_url,
                'RememberLogin': 'true',
                '__RequestVerificationToken': req_token
            }

            post_url = f"{AUTH_BASE_URL}/Account/Login?ReturnUrl=" + urllib.parse.quote(return_url)
            post_req = urllib.request.Request(
                post_url,
                data=urllib.parse.urlencode(login_data).encode(),
                headers={
                    'User-Agent': USER_AGENT,
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )

            with self.opener.open(post_req) as post_resp:
                final_url = post_resp.geturl()

            qs_final = urllib.parse.parse_qs(urllib.parse.urlparse(final_url).query)
            auth_code = qs_final.get('code', [None])[0]

            if not auth_code:
                # Check for error in query or page
                error = qs_final.get('error', [None])[0]
                raise RuntimeError(f"Authentication failed. No auth code returned. Error: {error}")

        # 3. Exchange code for JWT tokens
        token_data = {
            'grant_type': 'authorization_code',
            'client_id': 'vue-app',
            'code': auth_code,
            'code_verifier': code_verifier,
            'redirect_uri': 'https://www.buildinglink.com/voidc-callback'
        }

        token_req = urllib.request.Request(
            f"{AUTH_BASE_URL}/connect/token",
            data=urllib.parse.urlencode(token_data).encode(),
            headers={
                'User-Agent': USER_AGENT,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )

        with self.opener.open(token_req) as token_resp:
            tokens = json.loads(token_resp.read().decode())
            self.access_token = tokens['access_token']
            self.refresh_token = tokens.get('refresh_token')
            self.token_expiry = time.time() + tokens.get('expires_in', 900) - 30

        print("[+] Logged in successfully! Access token acquired.")
        return self.access_token

    def _api_request(self, endpoint, method='GET', data=None):
        if not self.access_token or time.time() >= self.token_expiry:
            self.login()

        url = f"{AMENITY_BASE_URL}{endpoint}"
        headers = {
            'User-Agent': USER_AGENT,
            'Authorization': f"Bearer {self.access_token}",
            'x-api-key': API_KEY,
            'Accept': 'application/json'
        }

        encoded_data = None
        if data is not None:
            headers['Content-Type'] = 'application/json'
            encoded_data = json.dumps(data).encode('utf-8')

        req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read().decode('utf-8')
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='ignore')
            raise RuntimeError(f"API {method} {endpoint} failed [{e.code}]: {err_body}")

    def get_contact_info(self):
        """Fetches the default contact details for the authenticated resident."""
        return self._api_request("/resident/contact")

    def get_amenity_info(self, amenity_id=DEFAULT_AMENITY_ID):
        """Fetches amenity details and booking rules."""
        return self._api_request(f"/resident/amenities/{amenity_id}")

    def get_available_slots(self, date_str, amenity_id=DEFAULT_AMENITY_ID):
        """
        Fetches open slots for date_str (YYYY-MM-DD).
        """
        return self._api_request(f"/resident/amenities/{amenity_id}/available-slots?date={date_str}")

    def book_slot(self, slot, contact_name, contact_email, contact_phone, amenity_id=DEFAULT_AMENITY_ID, description=None):
        """
        Books the specified slot dictionary.
        """
        payload = {
            "amenityId": amenity_id,
            "contactName": contact_name,
            "contactEmail": contact_email,
            "contactPhone": contact_phone,
            "description": description,
            "startUtc": slot['startUtc'],
            "endUtc": slot['endUtc'],
            "isAllDay": False,
            "liabilityWaiverAccepted": False,
            "liabilityWaiverTypedResponse": None
        }
        return self._api_request("/resident/reservations", method="POST", data=payload)

    def list_reservations(self, include_past=False):
        """Lists current reservations."""
        flag = "true" if include_past else "false"
        return self._api_request(f"/resident/reservations?includePast={flag}&includeRecurring=false&pageNumber=0&pageSize=25")

    def cancel_reservation(self, occurrence_id):
        """Cancels a reservation by its occurrence ID."""
        return self._api_request(f"/resident/reservation-occurrences/{occurrence_id}/cancel", method="POST")


def normalize_time_str(time_input):
    """
    Normalizes time strings like '7pm', '7:00 PM', '19:00', '19' into 'HH:MM' (24-hour).
    """
    t = time_input.strip().upper()
    formats = ['%I:%M %p', '%I %p', '%I:%M%p', '%I%p', '%H:%M', '%H']
    for fmt in formats:
        try:
            dt = datetime.strptime(t, fmt)
            return dt.strftime('%H:%M')
        except ValueError:
            pass
    raise ValueError(f"Cannot parse time format: '{time_input}' (examples: '19:00', '7:00 PM', '7pm')")


def find_best_slot(available_slots, preferred_times):
    """
    Finds the first available slot matching user preferences in priority order.
    """
    if not available_slots or not available_slots.get('isOpen'):
        return None

    slots = available_slots.get('slots', [])
    if not slots:
        return None

    # Pre-parse startLocal times into HH:MM
    # e.g. "2026-11-04T08:00:00.0000000Z" -> "08:00"
    for pref in preferred_times:
        try:
            norm_pref = normalize_time_str(pref)
        except ValueError:
            print(f"[!] Warning: invalid preferred time format: {pref}")
            continue

        for slot in slots:
            start_local = slot.get('startLocal', '')
            # Extract time portion: T(HH:MM)
            m = re.search(r'T(\d{2}:\d{2})', start_local)
            if m and m.group(1) == norm_pref:
                return slot

    # If no preferred time matched, or preferred_times was empty, return first available slot
    return slots[0] if (not preferred_times or preferred_times == ["any"]) else None


def load_config(config_path="config.json"):
    config = {
        "username": "",
        "password": "",
        "amenity_id": DEFAULT_AMENITY_ID,
        "preferred_times": ["19:00", "20:00", "18:00", "21:00"],
        "days_ahead": 1,
        "description": ""
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_conf = json.load(f)
                config.update(user_conf)
        except Exception as e:
            print(f"[!] Error loading {config_path}: {e}")
    return config


def run_booking(client, config, target_date=None, dry_run=False):
    """Executes the booking logic."""
    if not target_date:
        days_ahead = config.get("days_ahead", 1)
        target_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    amenity_id = config.get("amenity_id", DEFAULT_AMENITY_ID)
    preferred_times = config.get("preferred_times", [])

    print(f"\n==========================================")
    print(f" Target Date:        {target_date}")
    print(f" Amenity ID:         {amenity_id}")
    print(f" Preferred Times:    {preferred_times}")
    print(f" Dry Run Mode:       {dry_run}")
    print(f"==========================================\n")

    # 1. Fetch available slots
    print(f"[*] Querying available slots for {target_date}...")
    slots_resp = client.get_available_slots(target_date, amenity_id)
    is_open = slots_resp.get("isOpen", False)
    slots = slots_resp.get("slots", [])

    print(f"[*] Facility isOpen: {is_open}. Total available slots: {len(slots)}")
    for s in slots:
        start_local = s.get("startLocal", "")
        end_local = s.get("endLocal", "")
        # Format for readability
        m1 = re.search(r'T(\d{2}:\d{2})', start_local)
        m2 = re.search(r'T(\d{2}:\d{2})', end_local)
        t_str = f"{m1.group(1)} - {m2.group(1)}" if (m1 and m2) else f"{start_local} - {end_local}"
        print(f"    - Slot: {t_str} (UTC: {s.get('startUtc')})")

    if not is_open or not slots:
        print(f"[-] No slots available for {target_date}.")
        return False

    # 2. Match best slot
    selected_slot = find_best_slot(slots_resp, preferred_times)
    if not selected_slot:
        print(f"[-] None of your preferred times {preferred_times} were available.")
        return False

    m_start = re.search(r'T(\d{2}:\d{2})', selected_slot.get('startLocal', ''))
    m_end = re.search(r'T(\d{2}:\d{2})', selected_slot.get('endLocal', ''))
    slot_label = f"{m_start.group(1)} - {m_end.group(1)}" if (m_start and m_end) else selected_slot.get('startLocal')
    print(f"\n[+] Selected Slot: {slot_label}")

    if dry_run:
        print("[*] DRY RUN enabled: skipping actual reservation creation.")
        return True

    # 3. Fetch contact details
    print("[*] Retrieving resident contact details...")
    contact = client.get_contact_info()
    first_name = contact.get('firstName', '')
    last_name = contact.get('lastName', '')
    full_name = f"{first_name} {last_name}".strip()
    email = contact.get('email', '')
    phone = contact.get('phone', '')

    print(f"[*] Booking for: {full_name} ({email}, {phone})")

    # 4. Book
    print(f"[*] Submitting reservation request...")
    res = client.book_slot(
        selected_slot,
        contact_name=full_name,
        contact_email=email,
        contact_phone=phone,
        amenity_id=amenity_id,
        description=config.get("description")
    )
    print(f"[SUCCESS] Reservation confirmed! Details:")
    print(json.dumps(res, indent=2))
    return True


def wait_until_midnight_and_run(client, config):
    """
    Loops until 00:00:00 (12:00 AM midnight), then immediately executes booking.
    """
    now = datetime.now()
    tomorrow = now.date() + timedelta(days=1)
    target_time = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0, 500000) # 00:00:00.5
    wait_secs = (target_time - now).total_seconds()
    print(f"[*] Scheduler active. Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[*] Waiting until midnight ({target_time.strftime('%Y-%m-%d %H:%M:%S')}) ~ {wait_secs:.1f} seconds...")
    
    # Refresh token 2 minutes before midnight so token is fresh
    pre_refresh_time = target_time - timedelta(minutes=2)
    if datetime.now() < pre_refresh_time:
        time.sleep((pre_refresh_time - datetime.now()).total_seconds())
        print("[*] Pre-authenticating before midnight...")
        client.login(force=True)

    # Sleep remaining seconds until exactly midnight
    remaining = (target_time - datetime.now()).total_seconds()
    if remaining > 0:
        time.sleep(remaining)

    print(f"\n[*] 12:00 AM Midnight reached! Executing automated booking now...")
    run_booking(client, config)


def main():
    parser = argparse.ArgumentParser(description="BuildingLink Amenities Automated Booking Scheduler")
    parser.add_argument("--config", default="config.json", help="Path to config file (default: config.json)")
    parser.add_argument("--date", help="Specific booking date (YYYY-MM-DD). Defaults to tomorrow.")
    parser.add_argument("--time", nargs="+", help="Preferred start time(s) e.g. 19:00 20:00 '7:00 PM'")
    parser.add_argument("--dry-run", action="store_true", help="Check available slots and match without booking")
    parser.add_argument("--schedule", action="store_true", help="Wait in background until 12:00 AM midnight and trigger booking")
    parser.add_argument("--list", action="store_true", help="List active reservations")
    parser.add_argument("--cancel", help="Cancel reservation by occurrence ID")

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    if args.time:
        config["preferred_times"] = args.time

    username = os.environ.get("BL_USERNAME") or config.get("username")
    password = os.environ.get("BL_PASSWORD") or config.get("password")

    if not username or not password:
        print("[!] Error: Username and password must be set in config.json or environment variables (BL_USERNAME, BL_PASSWORD).")
        sys.exit(1)

    client = BuildingLinkClient(username, password)

    if args.list:
        client.login()
        res = client.list_reservations()
        print(json.dumps(res, indent=2))
        return

    if args.cancel:
        client.login()
        res = client.cancel_reservation(args.cancel)
        print("[+] Reservation canceled:", json.dumps(res, indent=2))
        return

    if args.schedule:
        client.login()
        wait_until_midnight_and_run(client, config)
    else:
        client.login()
        run_booking(client, config, target_date=args.date, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

