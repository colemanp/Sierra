"""Test Garmin Connect API access

Requires Garmin Connect credentials.
On first run, will prompt for email/password and save session token.
"""
import os
import json
from datetime import date, timedelta
from pathlib import Path
from getpass import getpass

from garminconnect import Garmin

# Token file for session persistence
TOKEN_DIR = Path(__file__).parent.parent / "data" / ".garmin"
TOKEN_FILE = TOKEN_DIR / "session.json"


def get_client() -> Garmin:
    """Get authenticated Garmin client"""
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)

    # Try loading existing session
    if TOKEN_FILE.exists():
        print("Loading saved session...")
        try:
            client = Garmin()
            client.login(str(TOKEN_FILE))
            # Test if session is valid
            client.get_full_name()
            print("Session valid!")
            return client
        except Exception as e:
            print(f"Session expired or invalid: {e}")

    # Need fresh login
    email = input("Garmin email: ")
    password = getpass("Garmin password: ")

    client = Garmin(email, password)
    client.login()

    # Save session
    client.garth.dump(str(TOKEN_FILE))
    print(f"Session saved to {TOKEN_FILE}")

    return client


def test_user_info(client: Garmin):
    """Test basic user info"""
    print("\n=== User Info ===")
    print(f"Name: {client.get_full_name()}")
    print(f"Unit: {client.get_unit_system()}")


def test_heart_rate(client: Garmin):
    """Test heart rate data"""
    print("\n=== Heart Rate (Today) ===")
    today = date.today().isoformat()
    try:
        hr = client.get_heart_rates(today)
        if hr:
            print(f"Resting HR: {hr.get('restingHeartRate')}")
            print(f"Max HR: {hr.get('maxHeartRate')}")
            print(f"Min HR: {hr.get('minHeartRate')}")
        else:
            print("No HR data for today")
    except Exception as e:
        print(f"Error: {e}")


def test_resting_hr_history(client: Garmin):
    """Test historical resting HR"""
    print("\n=== Resting HR History (Last 7 Days) ===")
    end = date.today()
    start = end - timedelta(days=7)
    try:
        # Get daily summaries which include resting HR
        for i in range(7):
            day = (start + timedelta(days=i)).isoformat()
            hr = client.get_heart_rates(day)
            if hr and hr.get('restingHeartRate'):
                print(f"{day}: {hr['restingHeartRate']} bpm")
    except Exception as e:
        print(f"Error: {e}")


def test_activities(client: Garmin):
    """Test recent activities"""
    print("\n=== Recent Activities (Last 5) ===")
    try:
        activities = client.get_activities(0, 5)
        for a in activities:
            name = a.get('activityName', 'Unknown')
            atype = a.get('activityType', {}).get('typeKey', '?')
            dist = a.get('distance', 0)
            dur = a.get('duration', 0)
            print(f"- {name} ({atype}): {dist/1609.34:.1f}mi, {dur/60:.0f}min")
    except Exception as e:
        print(f"Error: {e}")


def test_weight(client: Garmin):
    """Test weight data"""
    print("\n=== Weight (Last 7 Days) ===")
    end = date.today()
    start = end - timedelta(days=7)
    try:
        weights = client.get_weigh_ins(start.isoformat(), end.isoformat())
        if weights and 'dailyWeightSummaries' in weights:
            for w in weights['dailyWeightSummaries']:
                d = w.get('summaryDate', '?')
                latest = w.get('latestWeight', {})
                wt = latest.get('weight', 0) / 1000  # grams to kg
                wt_lbs = wt * 2.20462
                print(f"{d}: {wt_lbs:.1f} lbs")
        else:
            print("No weight data")
    except Exception as e:
        print(f"Error: {e}")


def test_weight_historical(client: Garmin):
    """Test historical weight data from March 2010"""
    print("\n=== Weight (March 2010 - Historical) ===")
    start = date(2010, 3, 1)
    end = date(2010, 3, 31)
    try:
        weights = client.get_weigh_ins(start.isoformat(), end.isoformat())
        print(f"Raw API response keys: {list(weights.keys()) if weights else 'None'}")

        if weights and 'dailyWeightSummaries' in weights:
            summaries = weights['dailyWeightSummaries']
            print(f"Found {len(summaries)} daily summaries")

            for w in summaries[:5]:  # First 5 entries
                print(f"\n--- {w.get('summaryDate', '?')} ---")
                print(json.dumps(w, indent=2, default=str))
        else:
            print("No weight data for March 2010")
            print(f"Full response: {json.dumps(weights, indent=2, default=str)}")
    except Exception as e:
        print(f"Error: {e}")


def test_sleep(client: Garmin):
    """Test sleep data"""
    print("\n=== Sleep (Last Night) ===")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    try:
        sleep = client.get_sleep_data(yesterday)
        if sleep and 'dailySleepDTO' in sleep:
            s = sleep['dailySleepDTO']
            dur = s.get('sleepTimeSeconds', 0) / 3600
            print(f"Duration: {dur:.1f} hrs")
            print(f"Quality: {s.get('sleepScores', {}).get('overall', {}).get('value', '?')}")
        else:
            print("No sleep data")
    except Exception as e:
        print(f"Error: {e}")


def test_steps(client: Garmin):
    """Test step data"""
    print("\n=== Steps (Today) ===")
    today = date.today().isoformat()
    try:
        steps = client.get_steps_data(today)
        if steps:
            total = sum(s.get('steps', 0) for s in steps)
            print(f"Total: {total:,} steps")
        else:
            print("No step data")
    except Exception as e:
        print(f"Error: {e}")


def test_vo2max(client: Garmin):
    """Test VO2 Max data from training status"""
    print("\n=== VO2 Max ===")
    try:
        data = client.get_training_status(date.today().isoformat())
        if data and 'mostRecentVO2Max' in data:
            vo2_data = data['mostRecentVO2Max']

            # Running VO2 Max
            if vo2_data.get('generic'):
                g = vo2_data['generic']
                vo2 = g.get('vo2MaxPreciseValue') or g.get('vo2MaxValue')
                d = g.get('calendarDate', '?')
                print(f"Running VO2 Max: {vo2} ml/kg/min (as of {d})")

            # Cycling VO2 Max
            if vo2_data.get('cycling'):
                c = vo2_data['cycling']
                vo2 = c.get('vo2MaxPreciseValue') or c.get('vo2MaxValue')
                d = c.get('calendarDate', '?')
                print(f"Cycling VO2 Max: {vo2} ml/kg/min (as of {d})")
        else:
            print("No VO2 Max data in training status")
    except Exception as e:
        print(f"Error: {e}")


def test_activity_details(client: Garmin):
    """Test fetching activity details from yesterday"""
    print("\n=== Activity Details (Yesterday) ===")
    yesterday = date.today() - timedelta(days=1)
    try:
        # Get activities from yesterday
        activities = client.get_activities_by_date(
            yesterday.isoformat(), yesterday.isoformat()
        )
        if not activities:
            print("No activities found yesterday")
            return

        # Get first activity's details
        activity = activities[0]
        activity_id = activity.get('activityId')
        print(f"Activity: {activity.get('activityName')} (ID: {activity_id})")
        print(f"Type: {activity.get('activityType', {}).get('typeKey')}")

        # Basic stats from list response
        print(f"\n--- Basic Stats ---")
        print(f"Distance: {activity.get('distance', 0)/1609.34:.2f} mi")
        print(f"Duration: {activity.get('duration', 0)/60:.1f} min")
        print(f"Avg HR: {activity.get('averageHR')}")
        print(f"Max HR: {activity.get('maxHR')}")
        print(f"Calories: {activity.get('calories')}")
        print(f"Avg Pace: {activity.get('averageSpeed')}")

        # Get full activity details - dump everything
        print(f"\n--- Full Activity Details ---")
        details = client.get_activity(activity_id)
        print(json.dumps(details, indent=2, default=str))

        # Save to file for analysis
        output_dir = Path(__file__).parent.parent / "data" / "garmin_samples"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"activity_{activity_id}.json"

        all_data = {
            "activity_list": activity,
            "activity_details": details,
        }

        # Add splits
        try:
            all_data["splits"] = client.get_activity_splits(activity_id)
        except:
            pass

        # Add HR zones
        try:
            all_data["hr_zones"] = client.get_activity_hr_in_timezones(activity_id)
        except:
            pass

        # Add time series
        try:
            all_data["time_series"] = client.get_activity_details(activity_id)
        except:
            pass

        with open(output_file, "w") as f:
            json.dump(all_data, f, indent=2, default=str)
        print(f"\n*** Saved full activity data to: {output_file} ***")

        # Get splits/laps - full dump
        print(f"\n--- Splits (Full Data) ---")
        try:
            splits = client.get_activity_splits(activity_id)
            print(f"Splits keys: {list(splits.keys()) if splits else 'None'}")
            if splits:
                print(json.dumps(splits, indent=2, default=str))
        except Exception as e:
            print(f"  Error getting splits: {e}")

        # Get HR zones - full dump
        print(f"\n--- HR Zones (Full Data) ---")
        try:
            hr_zones = client.get_activity_hr_in_timezones(activity_id)
            print(json.dumps(hr_zones, indent=2, default=str))
        except Exception as e:
            print(f"  Error getting HR zones: {e}")

        # Try get_activity_details for GPS/HR time series
        print(f"\n--- Activity Details (Time Series) ---")
        try:
            activity_details = client.get_activity_details(activity_id)
            print(f"Keys: {list(activity_details.keys()) if activity_details else 'None'}")
            # This can be huge, just show structure
            if activity_details:
                for k, v in activity_details.items():
                    if isinstance(v, list):
                        print(f"  {k}: list of {len(v)} items")
                        if v:
                            print(f"    Sample: {json.dumps(v[0], indent=4, default=str)[:500]}")
                    else:
                        print(f"  {k}: {type(v).__name__}")
        except Exception as e:
            print(f"  Error getting activity details: {e}")

    except Exception as e:
        print(f"Error: {e}")


def test_vo2max_history_bulk(client: Garmin):
    """Test VO2 Max history using bulk endpoint (single API call)"""
    print("\n=== VO2 Max History - Bulk Endpoint (Last 90 Days) ===")
    end = date.today()
    start = end - timedelta(days=90)

    try:
        url = f"/metrics-service/metrics/maxmet/daily/{start.isoformat()}/{end.isoformat()}"
        data = client.connectapi(url)

        if data and isinstance(data, list):
            vo2_readings = []
            for entry in data:
                cal_date = entry.get('calendarDate')
                if not cal_date:
                    continue

                # Running VO2 Max (generic)
                if entry.get('generic'):
                    vo2 = entry['generic'].get('vo2MaxPreciseValue')
                    if vo2:
                        vo2_readings.append((cal_date, vo2, 'running'))

                # Cycling VO2 Max
                if entry.get('cycling'):
                    vo2 = entry['cycling'].get('vo2MaxPreciseValue')
                    if vo2:
                        vo2_readings.append((cal_date, vo2, 'cycling'))

            if vo2_readings:
                vo2_readings.sort(reverse=True)
                print(f"Found {len(vo2_readings)} readings in 1 API call:")
                for d, v, t in vo2_readings[:20]:
                    print(f"  {d}: {v} ml/kg/min ({t})")
            else:
                print("No VO2 Max data in response")
        else:
            print(f"Unexpected response: {type(data)}")

    except Exception as e:
        print(f"Bulk endpoint failed: {e}")
        print("Falling back to day-by-day method...")


def main():
    print("Garmin Connect API Test")
    print("=" * 40)

    client = get_client()

    test_user_info(client)
    test_heart_rate(client)
    test_resting_hr_history(client)
    test_activities(client)
    test_weight(client)
    test_weight_historical(client)
    test_sleep(client)
    test_steps(client)
    test_vo2max(client)
    test_vo2max_history_bulk(client)
    test_activity_details(client)

    print("\n" + "=" * 40)
    print("Tests complete!")


if __name__ == "__main__":
    main()
