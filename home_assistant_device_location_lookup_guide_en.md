# How to Configure Voice Assist to Find Your Devices

![image](images/20250608_ASxwFa.png)

## Features

- **Location Tracking:** Voice Assist will tell you if a device is at home, and specifically which room it is in (if detected).
- **Universal BLE Support:** Works with any BLE device tracked by the [Bermuda BLE Trilateration](https://github.com/agittins/bermuda) integration (Android, iOS, smartwatches, beacon tiles, etc.).
- **Mobile App Support:** Locates any device with the Home Assistant Companion App installed.
- **Ring to Find:** If the device has the Companion App, Voice Assist can trigger it to ring, even if it's in "Do Not Disturb" mode.
- **Privacy Focused:** The LLM does not have real-time access to your GPS coordinates. It only receives general location info (Home/Away, specific room) strictly when you ask to find a device.

## Limitations

- **LLM Compatibility:** Requires an LLM-based Voice Assist (like Gemini or OpenAI).
- **Entity Support:** Only works with `device_tracker` entities from Bermuda or the Mobile App.

## Prerequisites

- **Bermuda BLE Trilateration:** (Optional but recommended) Installed via HACS for room-level tracking. Make sure your Bluetooth proxies or scanners (ESPHome, Shelly, etc.) are assigned to their corresponding **Areas** in Home Assistant so Bermuda can report the room location.
- **Home Assistant Companion App:** Installed on mobile devices for "Ring to Find" functionality (with notification and critical alert permissions enabled).

## Installation Guide

### Step 1: Expose Device Trackers to Voice Assist

1. Navigate to **Settings** > **Voice assistants** > **Expose**.
2. Expose **only one** `device_tracker` entity per physical device.
3. **Tip:** Add friendly **Aliases** to your entities (e.g., "My Phone", "Keys") to make voice commands more natural.

**Important for Bermuda Users:**
If your phone has both a Mobile App tracker and a Bermuda tracker:

1. **Expose only the Bermuda tracker** to Voice Assist (it provides better room-level accuracy).
2. **Ensure the Bermuda device name / entity ID matches or contains the Mobile App device name**:
   - _Example:_ If your Mobile App tracker entity is `device_tracker.pixel_9`, naming your Bermuda device `Pixel 9` or `Pixel 9 BLE` results in `device_tracker.pixel_9_ble`. The blueprint automatically identifies that `pixel_9` matches your mobile device.
   - _Why?_ This dynamically links the accurate room-level location from Bermuda with the `notify.mobile_app_pixel_9` ringing service of the Mobile App.

### Step 2: Create a Shell Command for Alias Retrieval

This command allows the system to read the aliases you've set for your entities. Add this to your `configuration.yaml` file:

```yaml
shell_command:
  get_entity_alias: >-
    jq '[.data.entities[] | select(.options.conversation.should_expose == true) | {entity_id, aliases: (if has("aliases_v2") then ((if (.aliases_v2 | type) == "array" then .aliases_v2 else [] end) | map(select(. != null and . != ""))) else (if (.aliases | type) == "array" then .aliases else [] end) end)} | select(.aliases | length > 0)]' ./.storage/core.entity_registry
```

### Step 3: Create a Template Sensor

This sensor stores the alias information for the blueprints to use. Add this to your `configuration.yaml` (under `template:` or merge with your existing configuration):

```yaml
template:
  - triggers:
      - trigger: homeassistant
        event: start
      - trigger: event
        event_type: event_template_reloaded
    actions:
      - action: shell_command.get_entity_alias
        response_variable: response
    sensor:
      - name: "Assist: Entity IDs and Aliases"
        unique_id: entity_ids_and_aliases
        icon: mdi:format-list-bulleted
        device_class: timestamp
        state: "{{ now().isoformat() }}"
        attributes:
          entities: "{{ response.stdout }}"
```

**After adding these codes:**

1. **Restart** Home Assistant (or reload YAML configurations).
2. **Note:** If you add or change an Alias later, you must reload Template entities (Developer Tools > YAML > Template Entities) or restart HA.

### Step 4: Install Blueprints

#### 1. Device Location Lookup Blueprint

This blueprint powers the logic to find where your devices are.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevice_location_lookup_full_llm.yaml)

1. Import the blueprint.
2. Create a **Script** from it.
3. In the script settings, select the **Template Sensor** (`sensor.assist_entity_ids_and_aliases`) you created in Step 3.
4. **Keep the default script name** (`Find Device`).
5. **Restore LLM Description (Crucial Step):** After saving, click the three dots (`⋮`) in the top-right corner, select **Edit in YAML**, delete the `description: ...` line, and click **Save Script**. This restores the blueprint's native, optimized description so the LLM understands its purpose.
6. **Expose** this new script to Voice Assist.

#### 2. Device Ringing Blueprint

This blueprint allows Voice Assist to make your device ring.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevice_ringing_full_llm.yaml)

1. Import the blueprint.
2. Create a **Script** from it.
3. **Keep the default script name** (`Ring Device`).
4. **Restore LLM Description (Crucial Step):** After saving, click the three dots (`⋮`) in the top-right corner, select **Edit in YAML**, delete the `description: ...` line, and click **Save Script**.
5. **Expose** this new script to Voice Assist.

## Usage Examples

Once set up, try asking Voice Assist:

- "Find my phone."
- "Where is my iPhone?"
- "Where is my watch?"
- "Where is my wallet?" (for BLE tags)
- "Where is the dog?" (for pet tags)
