# Unique Home Assistant Blueprints & Tutorials

**🇺🇸 English | [🇻🇳 Tiếng Việt](README_vi.md)**

> [!TIP]
> **[Blueprints Updater](https://github.com/luuquangvu/blueprints-updater)**: A highly useful integration that automatically updates blueprints in this collection. When you have many blueprints from different sources, keeping track of updates can be challenging - this integration handles it for you automatically.

<!-- MD028/no-blanks-blockquote: Blank line inside blockquote -->

> [!NOTE]
> **Google has recently significantly cut back on the free Gemini API, making it almost impossible to meet the usage needs of Home Assistant. You can find [a completely free alternative solution here](https://github.com/luuquangvu/ha-addons).**

_All blueprints in this collection are compatible with almost all local and online LLMs, though they are fine-tuned to work best with **Gemini Flash** models. Other models may require minor adjustments to behave as expected._

> [!IMPORTANT]
> **Crucial Setup Step:** Please refer to the [Installation & Setup Guide](#installation--setup-guide) below before setting up your blueprints. Many blueprints rely on shared dependencies such as the Entity Aliases sensor, Pyscript helper scripts, or Assist tool configuration to function correctly.

Transform Home Assistant into a fully-fledged personal teammate with this curated collection of blueprints and guides. Every scenario has been proven in real homes, backed by clear explanations, example voice prompts, and deployment tips so you can bring each idea to life right away.

---

## Table of Contents

- [Unique Home Assistant Blueprints & Tutorials](#unique-home-assistant-blueprints--tutorials)
  - [Table of Contents](#table-of-contents)
  - [Installation & Setup Guide](#installation--setup-guide)
    - [Universal Blueprint Installation Workflow](#universal-blueprint-installation-workflow)
    - [Shared Dependency Modules](#shared-dependency-modules)
      - [Module 1: Entity Aliases Sensor (Friendly-Name Lookup)](#module-1-entity-aliases-sensor-friendly-name-lookup)
      - [Module 2: Pyscript Integration & Helper Scripts](#module-2-pyscript-integration--helper-scripts)
      - [Module 3: Specialized Integrations & External Services](#module-3-specialized-integrations--external-services)
    - [Blueprint Dependency Matrix](#blueprint-dependency-matrix)
  - [Voice Assist - Smart Scheduling & Timers](#voice-assist---smart-scheduling--timers)
  - [Voice Assist - Memory & Information Retrieval](#voice-assist---memory--information-retrieval)
  - [Voice Assist - Camera Image Analysis](#voice-assist---camera-image-analysis)
  - [Voice Assist - Calendar & Event Management](#voice-assist---calendar--event-management)
    - [Create Calendar Events](#create-calendar-events)
    - [Calendar Events Lookup](#calendar-events-lookup)
  - [Voice Assist - Lunar Calendar Lookup & Conversion](#voice-assist---lunar-calendar-lookup--conversion)
    - [Lunar Calendar Conversion & Lookup](#lunar-calendar-conversion--lookup)
    - [Create Lunar Calendar Events](#create-lunar-calendar-events)
  - [Interactive Smart Home Chatbot](#interactive-smart-home-chatbot)
  - [Voice Assist - Send Messages & Media](#voice-assist---send-messages--media)
  - [Voice Assist - Internet Knowledge Search](#voice-assist---internet-knowledge-search)
  - [Voice Assist - YouTube Search & Playback](#voice-assist---youtube-search--playback)
  - [Voice Assist - Favorite YouTube Channels](#voice-assist---favorite-youtube-channels)
  - [Voice Assist - Smart Fan Control](#voice-assist---smart-fan-control)
  - [Voice Assist - Smart AC Control](#voice-assist---smart-ac-control)
  - [Voice Assist - Weather Forecast](#voice-assist---weather-forecast)
  - [Voice Assist - Music Control](#voice-assist---music-control)
  - [Voice Assist - Device Location & Find](#voice-assist---device-location--find)
  - [Device State Synchronization](#device-state-synchronization)
  - [Additional Tutorials](#additional-tutorials)
    - [How to write custom system instructions for Voice Assist](#how-to-write-custom-system-instructions-for-voice-assist)
    - [Play new videos from favorite YouTube channels](#play-new-videos-from-favorite-youtube-channels)
    - [Monitor unavailable devices](#monitor-unavailable-devices)
    - [Auto-switch iOS Themes](#auto-switch-ios-themes)
    - [Device location lookup guide](#device-location-lookup-guide)

---

## Installation & Setup Guide

Installing blueprints from this repository follows a straightforward workflow. Because many blueprints share identical prerequisites (such as friendly-name alias resolution, Pyscript helper scripts, or Assist tool configuration), shared setup steps are documented in modular blocks below so you only need to configure them once.

### Universal Blueprint Installation Workflow

Every blueprint in this repository can be installed and activated using the following 3 steps:

1. **Import the Blueprint:**
   - Click the **Import Blueprint** badge under any blueprint section to open the import dialog directly in your Home Assistant instance via [My Home Assistant](https://my.home-assistant.io/).
   - _Alternative (Manual):_ In Home Assistant, navigate to **Settings > Automations & Scenes > Blueprints > Add Blueprint** (bottom right), paste the raw GitHub URL of the blueprint `.yaml` file, and click **Preview** followed by **Import Blueprint**.

2. **Create the Script or Automation:**
   - In **Settings > Automations & Scenes > Blueprints**, locate the imported blueprint and click **Create Script** (or **Create Automation**).
   - Configure the required inputs (e.g., selecting your entities, sensors, or helper scripts).
   - Click **Save**. **Do not alter the default script name / entity ID** if companion blueprints or scripts reference it.

3. **Configure as an Assist Tool (Essential for Voice Assist Blueprints):**
   - **Expose to Assist:** In **Settings > Voice Assistants**, ensure the newly created script is exposed to your Assist pipeline or LLM Conversation Agent.
   - **Restore LLM Description (Crucial Step):** When Home Assistant saves a script through the UI, it can overwrite the blueprint's carefully crafted description with a generic line. To restore it:
     1. Open your saved script in the Home Assistant Script Editor.
     2. Click the three dots (`⋮`) in the top-right corner and select **Edit in YAML**.
     3. Locate and delete the `description: ...` line.
     4. Click **Save Script**. Home Assistant will automatically revert to using the blueprint's native, optimized description, enabling your LLM (such as Gemini) to accurately understand when and how to call the tool.

---

### Shared Dependency Modules

Many blueprints share one or more common configuration components. Set up the modules required for the blueprints you intend to use.

#### Module 1: Entity Aliases Sensor (Friendly-Name Lookup)

Several Voice Assist blueprints (including Smart Scheduling, Camera Snapshot, Fan/AC Control, YouTube playback, and Device Location) rely on friendly-name alias resolution so you can refer to devices by natural names (e.g., "standing fan", "ceiling light", "living room AC") rather than rigid entity IDs.

1. Add the following `shell_command` and `template` sensor configuration to your Home Assistant `configuration.yaml`:

   ```yaml
   # configuration.yaml

   shell_command:
     get_entity_alias: >-
       jq '[.data.entities[] | select(.options.conversation.should_expose == true) | {entity_id, aliases: (if has("aliases_v2") then ((if (.aliases_v2 | type) == "array" then .aliases_v2 else [] end) | map(select(. != null and . != ""))) else (if (.aliases | type) == "array" then .aliases else [] end) end)} | select(.aliases | length > 0)]' ./.storage/core.entity_registry

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

2. Restart Home Assistant (or reload YAML configuration).
3. Ensure that any entities you want the assistant to control are **exposed to Assist** and have aliases configured in their entity settings.

#### Module 2: Pyscript Integration & Helper Scripts

Advanced features such as persistent multi-device scheduling, universal memory, lunar calendar calculations, YouTube searches, and interactive messaging (Telegram/Zalo) use lightweight Python backend scripts powered by the **Pyscript** integration.

1. **Install Pyscript:**
   - Install **Pyscript Python Scripting** via [HACS](https://hacs.xyz/) (Home Assistant Community Store).
   - Restart Home Assistant.
2. **Configure Pyscript in `configuration.yaml`:**
   - Ensure imports and global `hass` access are enabled:

   ```yaml
   # configuration.yaml
   pyscript:
     allow_all_imports: true
     hass_is_global: true
   ```

   _Note: If using Telegram, Zalo, or YouTube features, add their respective tokens/keys under `pyscript:` or reference them via `!secret` as documented below._

3. **Deploy the Required Scripts to `config/pyscript/`:**
   - In your Home Assistant `config/` directory, locate or create the `pyscript/` folder.
   - Copy the required script(s) from this repository's [`scripts/`](scripts/) folder into your `config/pyscript/` directory based on what you are installing:
     - [`scripts/common_utilities.py`](scripts/common_utilities.py) — Core utility functions (required by Smart Scheduling, Memory Tool Local, Telegram, Zalo).
     - [`scripts/memory.py`](scripts/memory.py) — Memory engine (required by Memory Tool).
     - [`scripts/date_conversion_tool.py`](scripts/date_conversion_tool.py) — Lunar/Solar conversion engine (required by Lunar Calendar).
     - [`scripts/telegram_bot_handle_tool.py`](scripts/telegram_bot_handle_tool.py) — Telegram bot engine.
     - [`scripts/zalo_bot_handle_tool.py`](scripts/zalo_bot_handle_tool.py) — Zalo bot engine.
     - [`scripts/youtube_data_tool.py`](scripts/youtube_data_tool.py) — YouTube Data API tool.
4. **Install Python Dependencies (When Required):**
   - If using Telegram, Zalo, or YouTube scripts, copy [`scripts/requirements.txt`](scripts/requirements.txt) into your `config/pyscript/` folder. Pyscript will automatically install the necessary packages (`h2`, `google-api-python-client`).
5. **Reload Pyscript:**
   - Navigate to **Developer Tools > YAML** and click **Pyscript Python Scripting** reload (or restart Home Assistant).

#### Module 3: Specialized Integrations & External Services

Some blueprints connect to specific Home Assistant services or third-party APIs:

- **AI Task Entity (Image Analysis):**
  - Used by: _File Content Analyzer_ (and camera snapshots / chatbot image recognition).
  - Go to **Settings > System > General** and configure an **AI Task** conversation model (e.g. Gemini).
- **Google Generative AI with Google Search:**
  - Used by: _Internet Knowledge Search_.
  - Requires Google Generative AI (Gemini) integration. In your conversation agent settings, enable the **Google Search** tool and increase the maximum token limit to at least **16,384 tokens**.
- **Calendar Integrations (Read/Write):**
  - Used by: _Create Calendar Events_, _Create Lunar Calendar Events_, and _Calendar Events Lookup_.
  - Make sure your Google Calendar or local calendar entity has write permissions enabled for event creation.
- **Music Assistant:**
  - Used by: _Music Control_.
  - Requires the [Music Assistant](https://music-assistant.io/) integration to be installed and active.
- **Device Tracking & Notifications:**
  - Used by: _Device Location & Find_.
  - Expose your **Bermuda Device Tracker** or **Home Assistant Mobile App** tracker to Assist. For phone ringing, ensure notification and critical alert permissions are enabled on the target mobile device.

---

### Blueprint Dependency Matrix

Use this quick reference table to find the exact requirements for each blueprint:

| Blueprint                                                                | Type                 | Companion Blueprints Needed                                                                                                                      | Required Modules                                                                                                                    | Python Scripts & Secrets                                                                     |
| ------------------------------------------------------------------------ | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| [Smart Scheduling & Timers](#voice-assist---smart-scheduling--timers)    | Script + Automations | Controller (`devices_schedules_controller_full_llm.yaml`) + Core (`devices_schedules.yaml`) + Restart (`devices_schedules_restart_handler.yaml`) | [Module 1](#module-1-entity-aliases-sensor-friendly-name-lookup), [Module 2](#module-2-pyscript-integration--helper-scripts)        | `common_utilities.py`                                                                        |
| [Memory Tool (LLM)](#voice-assist---memory--information-retrieval)       | Script               | None                                                                                                                                             | [Module 2](#module-2-pyscript-integration--helper-scripts)                                                                          | `memory.py`                                                                                  |
| [Memory Tool (Local)](#voice-assist---memory--information-retrieval)     | Automation           | None                                                                                                                                             | [Module 2](#module-2-pyscript-integration--helper-scripts)                                                                          | `memory.py`, `common_utilities.py`                                                           |
| [Camera Image Analysis](#voice-assist---camera-image-analysis)           | Scripts              | Snapshot (`camera_snapshot_full_llm.yaml`) + Analyzer (`file_content_analyzer_full_llm.yaml`)                                                    | [Module 1](#module-1-entity-aliases-sensor-friendly-name-lookup), [Module 3](#module-3-specialized-integrations--external-services) | AI Task entity, `/media` storage folder                                                      |
| [Create Calendar Events](#create-calendar-events)                        | Script               | None                                                                                                                                             | [Module 3](#module-3-specialized-integrations--external-services)                                                                   | Calendar with Read/Write access                                                              |
| [Calendar Events Lookup](#calendar-events-lookup)                        | Script               | None                                                                                                                                             | None                                                                                                                                | Configured Calendar entity                                                                   |
| [Lunar Calendar Conversion & Lookup](#lunar-calendar-conversion--lookup) | Script               | None                                                                                                                                             | [Module 2](#module-2-pyscript-integration--helper-scripts)                                                                          | `date_conversion_tool.py`                                                                    |
| [Create Lunar Calendar Events](#create-lunar-calendar-events)            | Script               | None                                                                                                                                             | [Module 2](#module-2-pyscript-integration--helper-scripts), [Module 3](#module-3-specialized-integrations--external-services)       | `date_conversion_tool.py`, Calendar with Read/Write access                                   |
| [Interactive Chatbot (Telegram)](#interactive-smart-home-chatbot)        | Automation           | Optional: Analyzer (`file_content_analyzer_full_llm.yaml`)                                                                                       | [Module 2](#module-2-pyscript-integration--helper-scripts)                                                                          | `telegram_bot_handle_tool.py`, `common_utilities.py`, `requirements.txt`, Telegram Bot Token |
| [Interactive Chatbot (Zalo)](#interactive-smart-home-chatbot)            | Automation           | Optional: Analyzer (`file_content_analyzer_full_llm.yaml`)                                                                                       | [Module 2](#module-2-pyscript-integration--helper-scripts)                                                                          | `zalo_bot_handle_tool.py`, `common_utilities.py`, `requirements.txt`, Zalo Bot Token         |
| [Send to Telegram](#voice-assist---send-messages--media)                 | Script               | None                                                                                                                                             | [Module 2](#module-2-pyscript-integration--helper-scripts)                                                                          | `telegram_bot_handle_tool.py`, `requirements.txt`, Telegram Bot Token                        |
| [Send to Zalo](#voice-assist---send-messages--media)                     | Script               | None                                                                                                                                             | [Module 2](#module-2-pyscript-integration--helper-scripts)                                                                          | `zalo_bot_handle_tool.py`, `requirements.txt`, Zalo Bot Token                                |
| [Internet Knowledge Search](#voice-assist---internet-knowledge-search)   | Script               | None                                                                                                                                             | [Module 3](#module-3-specialized-integrations--external-services)                                                                   | Gemini Agent with Google Search & 16k+ tokens                                                |
| [YouTube Search & Playback](#voice-assist---youtube-search--playback)    | Scripts              | Search (`advanced_youtube_search_full_llm.yaml`) + Player (`play_youtube_video_full_llm.yaml`)                                                   | [Module 1](#module-1-entity-aliases-sensor-friendly-name-lookup), [Module 2](#module-2-pyscript-integration--helper-scripts)        | `youtube_data_tool.py`, `requirements.txt`, YouTube API Key, TV YouTube App                  |
| [Favorite YouTube Channels](#voice-assist---favorite-youtube-channels)   | Scripts              | Info Getter (`get_youtube_video_info_full_llm.yaml`) + Player (`play_youtube_video_full_llm.yaml`)                                               | [Module 1](#module-1-entity-aliases-sensor-friendly-name-lookup), [Module 2](#module-2-pyscript-integration--helper-scripts)        | `youtube_data_tool.py`, `requirements.txt`, YouTube API Key, TV YouTube App                  |
| [Smart Fan Control](#voice-assist---smart-fan-control)                   | Script               | None                                                                                                                                             | [Module 1](#module-1-entity-aliases-sensor-friendly-name-lookup)                                                                    | Fan entities exposed to Assist                                                               |
| [Smart AC Control](#voice-assist---smart-ac-control)                     | Script               | None                                                                                                                                             | [Module 1](#module-1-entity-aliases-sensor-friendly-name-lookup)                                                                    | Climate entity exposed to Assist                                                             |
| [Weather Forecast](#voice-assist---weather-forecast)                     | Script               | None                                                                                                                                             | None                                                                                                                                | Weather entity with hourly & daily forecasts                                                 |
| [Music Control](#voice-assist---music-control)                           | Script               | None                                                                                                                                             | [Module 3](#module-3-specialized-integrations--external-services)                                                                   | Music Assistant integration                                                                  |
| [Device Location & Find](#voice-assist---device-location--find)          | Scripts              | Location Lookup (`device_location_lookup_full_llm.yaml`) + Ringing (`device_ringing_full_llm.yaml`)                                              | [Module 1](#module-1-entity-aliases-sensor-friendly-name-lookup), [Module 3](#module-3-specialized-integrations--external-services) | Bermuda / Mobile app tracker, HA Companion App notifications                                 |
| [Device State Synchronization](#device-state-synchronization)            | Automation           | None                                                                                                                                             | None                                                                                                                                | Controllable switch/light entities                                                           |

---

## Voice Assist - Smart Scheduling & Timers

Want to turn on the AC for 30 minutes and have it turn off automatically? Or dim the bedroom lights after an hour?
This blueprint transforms Voice Assist into a true time management assistant. You can use natural voice commands to **create, extend, pause, resume, or cancel** schedules for any device.

**Key Features:**

- **Natural Language Understanding:** Just say "Turn on the fan for 1 hour", no rigid syntax required.
- **Comprehensive Management:** Full support for creating, extending, pausing, resuming, and canceling schedules.
- **Reliable & Persistent:** All schedules are saved and **automatically restored** if Home Assistant restarts. No more lost timers due to power outages.
- **Versatile Control:** Supports most device types: Lights (brightness, color), Covers (open/close/position), Fans (speed/oscillation), Climate, Vacuums, Media Players, etc.
- **Smart Recognition:** Automatically identifies devices by the friendly aliases you use daily.
- **Detailed Feedback:** Ask "Are there any running schedules?" and the assistant will list devices and remaining times clearly.

**Example Voice Commands:**

- "Turn on the living room lights to 50% warm white for 2 hours."
- "Open the bedroom curtains for 15 minutes to air out the room, then close them."
- "Extend the kids' room fan timer by 30 minutes."
- "Pause the garden watering schedule."
- "Which devices are currently on a timer?"

**Use Cases:**

- **Battery Protection:** "Charge phone for 2 hours then turn off socket" - Helps you charge overnight without worrying about battery degradation.
- **Hands-Free Cooking:** "Turn off the hood in 20 minutes" - Perfect when you've finished cooking and want to go for a walk.
- **Sleep Comfort:** "Turn the fan to the lowest speed for 1 hour then turn off" - Avoid waking up cold or with a dry throat.

**Prerequisites & Setup:**

- Requires [Module 1: Entity Aliases Sensor](#module-1-entity-aliases-sensor-friendly-name-lookup) configured in `configuration.yaml` for friendly device name resolution.
- Requires [Module 2: Pyscript Integration](#module-2-pyscript-integration--helper-scripts) with [`scripts/common_utilities.py`](scripts/common_utilities.py) placed in `config/pyscript/`.
- Install all 3 blueprints below (Controller script, Core script, and Restart automation).
- Expose the Controller script to Assist and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow) (keep default name, delete `description:` in YAML edit).

1. **Controller Blueprint (LLM):** Processes voice commands and coordinates actions.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevices_schedules_controller_full_llm.yaml)
2. **Core Schedule Blueprint:** Responsible for creating and managing the schedules.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevices_schedules.yaml)
3. **Restore Blueprint:** Automatically restores active schedules when Home Assistant restarts.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevices_schedules_restart_handler.yaml)

---

## Voice Assist - Memory & Information Retrieval

Forget where you parked the car? Keep forgetting the Wi-Fi password for guests? Let Voice Assist become your "Second Brain".

**Key Features:**

- **Remember Everything:** From small details like "Keys are in the desk drawer" to important reminders like "The customer ID for store ABC".
- **Smart Retrieval:** No need to remember exact keywords. Just ask "Where is the car?" or "What's the Wi-Fi pass?", and the assistant will find the most relevant info.
- **Flexible Scopes:**
  - **Personal (User):** For your personal details (e.g., clothing sizes, dietary preferences).
  - **Household:** Shared with the whole family (e.g., gate code, trash schedule).
  - **Temporary (Session):** Only remembered for the current conversation.
- **Auto-Cleanup:** Set expiration dates for short-term memories (e.g., parking spot at the mall).

**Example Voice Commands:**

- "Remember the guest Wi-Fi password is `guestshere123`."
- "Save my parking spot as B2 column D5, remember for 1 day only."
- "Remind me the doctor's phone number is 0912345678."
- "Find where the car is parked."
- "What was the guest Wi-Fi password?"

**Use Cases:**

- **Finding Lost Items:** "Where is the passport?" - A lifesaver when you need it urgently and can't remember which drawer it's in.
- **Complex Info:** Store long Wi-Fi passwords or bank account numbers so you can provide them instantly when guests ask.
- **Shopping Assistant:** Save clothing/shoe sizes for your spouse/kids to order online accurately without asking again.

**Prerequisites & Setup:**

- Requires [Module 2: Pyscript Integration](#module-2-pyscript-integration--helper-scripts) with [`scripts/memory.py`](scripts/memory.py) placed in `config/pyscript/` (the Local version also requires [`scripts/common_utilities.py`](scripts/common_utilities.py)).
- **LLM Version:** Expose the created script to Assist and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow) (delete `description:` in YAML edit).
- **Local Version:** Configured as an automation; customize trigger phrases in settings if needed.

_Choose the version you want to use:_

**LLM Version (Multi-language):**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fmemory_tool_full_llm.yaml)

**Local Version (English only, works offline):**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fmemory_tool_local.yaml)

---

## Voice Assist - Camera Image Analysis

Turn your security cameras into "smart eyes" for your virtual assistant. No need to open the app and check every angle-just let Voice Assist look for you.

**Key Features:**

- **Visual Intelligence:** Voice Assist can "see" images from your cameras and describe in detail what is happening.
- **Comprehensive View:** Supports connecting multiple cameras at once (gate, yard, living room...) for a complete overview.
- **Instant Response:** Captures and analyzes the image the moment you ask.

**Example Voice Commands:**

- "Check the gate camera, is anyone standing there?"
- "Check if the cat is in the front yard or the backyard?"
- "Look to see if the garage door is closed."
- "Is there any strange car in the yard?"

**Use Cases:**

- **Delivery Check:** "Is there a package at the door?" when you're on the 3rd floor and too lazy to run down.
- **Anxiety Relief:** Already in bed but suddenly panicked "Is the gate closed?", just ask Assistant to check for you.
- **Pet Monitor:** Check if your pet is sleeping nicely or digging up the garden.

**Prerequisites & Setup:**

- Requires [Module 1: Entity Aliases Sensor](#module-1-entity-aliases-sensor-friendly-name-lookup) for camera friendly-name resolution.
- Requires an **AI Task** entity configured under **Settings > System > General** (see [Module 3](#module-3-specialized-integrations--external-services)).
- Ensure the capture storage directory exists (default is `/media`).
- Install both blueprints below, expose the scripts to Assist, and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow).

1. **Snapshot Blueprint:** Takes a picture from the requested camera.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fcamera_snapshot_full_llm.yaml)
2. **Analyzer Blueprint (LLM):** Sends the snapshot to the language model for analysis and response.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ffile_content_analyzer_full_llm.yaml)

---

## Voice Assist - Calendar & Event Management

Effortlessly manage your personal schedule using natural voice commands, making organization simpler and more intuitive.

### Create Calendar Events

Organize your schedule by voice as if you're conversing with an assistant. This blueprint automates event creation for all your reminders, meetings, and trips directly into your calendar.

**Key Features:**

- **Intuitive Language Recognition:** Automatically parses dates, times, and durations from your spoken commands.
- **Rapid Event Creation:** Add events to your calendar without manual input.
- **Seamless Integration:** Works perfectly with Google Calendars already configured in Home Assistant.

**Example Voice Commands:**

- "Schedule a haircut for tomorrow at 2 PM."
- "Set up a 3-hour meeting tomorrow at 9 AM."
- "Add an event this Saturday to visit family."

**Use Cases:**

- **Plan Anytime:** Quickly create reminders and appointments while driving, cooking, or when a sudden idea strikes.
- **Never Miss Out:** Automate adding important family or work events to your calendar without manual input.

**Prerequisites & Setup:**

- Requires a Calendar entity configured with Read/Write permissions (see [Module 3](#module-3-specialized-integrations--external-services)).
- Expose the created script to Assist and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow) (delete `description:` in YAML edit).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fcreate_calendar_event_full_llm.yaml)

### Calendar Events Lookup

Inquire about and retrieve information regarding existing events in your calendar, such as birthdays, appointments, or anniversaries.

**Example Voice Commands:**

- "What events are happening this week?"
- "What's on the calendar for this month?"

**Use Cases:**

- **Before Leaving Home:** Quickly check your schedule for the day or week without needing to open your calendar app on your phone.
- **Confirm Plans:** Easily verify to ensure no double-bookings or missed important events.

**Prerequisites & Setup:**

- Select your target calendar entities in the blueprint input settings.
- Expose the created script to Assist and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow) (delete `description:` in YAML edit).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fcalendar_events_lookup_full_llm.yaml)

---

## Voice Assist - Lunar Calendar Lookup & Conversion

Bring traditional culture into your smart home. Lookup Lunar dates, check auspicious days, or countdown to Tet right on Home Assistant.

### Lunar Calendar Conversion & Lookup

A powerful Solar-Lunar calendar conversion tool that works completely **Offline** (no internet needed), ensuring instant response speeds.

**Key Features:**

- **Fast & Private:** Processed locally, independent of external APIs.
- **In-Depth Information:** Provides full Can Chi (Year/Month/Day stems and branches), Solar Terms, and Lucky Hours.
- **Good/Bad Day Advice:** Know immediately what to do or avoid according to customs.
- **Event Countdown:** Always know exactly how many days are left until Lunar New Year or major holidays.

**Example Voice Commands:**

- "What is today's lunar date?"
- "Is this Sunday a good or bad day?"
- "How many days left until Tet?"
- "Convert November 20th solar to lunar."

**Use Cases:**

- **Feng Shui & Spirituality:** Plan important events (weddings, groundbreakings, grand openings) based on auspicious days/hours.
- **Traditional Observances:** Keep track of the 1st and 15th of the lunar month, or memorial days to prepare offerings.

**Prerequisites & Setup:**

- Requires [Module 2: Pyscript Integration](#module-2-pyscript-integration--helper-scripts) with [`scripts/date_conversion_tool.py`](scripts/date_conversion_tool.py) placed in `config/pyscript/`.
- Expose the created script to Assist and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow) (delete `description:` in YAML edit).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdate_lookup_and_conversion_full_llm.yaml)

### Create Lunar Calendar Events

Automatically add important events based on the Lunar calendar (memorials, anniversaries, etc.) to your calendar, ensuring you never miss a traditional date.

**Note:** This blueprint is designed for **manual execution** or via automation, requiring users to fill in information directly through the Home Assistant UI. It **does not support voice commands** via Voice Assist.

**Key Features:**

- **Automatic Conversion:** Calculates and creates events on the corresponding solar date each year.
- **Accurate & Convenient:** No more manual conversions or forgetting important traditional dates.

**Use Cases:**

- **Never Miss Memorials:** Ensure you never miss important family memorials or ceremonies.
- **Lunar Birthdays:** Automatically get reminders for anniversaries or birthdays that are celebrated based on the lunar calendar for loved ones.

**Prerequisites & Setup:**

- Requires [Module 2: Pyscript Integration](#module-2-pyscript-integration--helper-scripts) with [`scripts/date_conversion_tool.py`](scripts/date_conversion_tool.py) placed in `config/pyscript/`.
- Requires a Calendar entity with Read/Write permissions (see [Module 3](#module-3-specialized-integrations--external-services)).
- Designed for manual UI execution or automations (does not require Assist exposure).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fcreate_lunar_events.yaml)

---

## Interactive Smart Home Chatbot

Don't just command; converse with your home. Create Telegram or Zalo Bots to control your home remotely with contextual understanding and smart responses.

**Key Features:**

- **Two-Way Conversation:** The Bot doesn't just receive commands but can ask clarifying questions (e.g., "Which room do you want the AC on in?")
- **Image Recognition:** Send a photo of a broken device or an unknown plant, and the bot will analyze and respond.
- **Anywhere, Anytime Control:** Turn off lights, open gates, or check cameras directly from your familiar chat interface.

**Use Cases:**

- **Remote Check-ins:** On your way to work and can't remember if you turned off the stove/lights? Just message the bot to check.
- **Silent Monitoring:** Want to know if your kids are home yet (via device status) without bothering them? Ask the bot instead of calling.

**Prerequisites & Setup:**

- Requires [Module 2: Pyscript Integration](#module-2-pyscript-integration--helper-scripts) with [`scripts/common_utilities.py`](scripts/common_utilities.py), [`scripts/requirements.txt`](scripts/requirements.txt), and the corresponding bot handler ([`scripts/telegram_bot_handle_tool.py`](scripts/telegram_bot_handle_tool.py) or [`scripts/zalo_bot_handle_tool.py`](scripts/zalo_bot_handle_tool.py)) placed in `config/pyscript/`.
- Add your bot token (`telegram_bot_token` or `zalo_bot_token`) to `configuration.yaml` and `secrets.yaml` under `pyscript:`.
- **For Telegram:** Disable Privacy Mode via BotFather or make the bot a group admin.
- **For Image Analysis (Optional):** Install the File Content Analyzer blueprint and configure an AI Task entity (see [Module 3](#module-3-specialized-integrations--external-services)).

_Install the webhook blueprint for your chosen platform. For image analysis, also install the Analyzer blueprint._

**Webhook for Telegram:**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ftelegram_bot_webhook.yaml)

**Webhook for Zalo (Official Account):**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fzalo_bot_webhook.yaml)

**(Optional) Image Analyzer Blueprint:**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ffile_content_analyzer_full_llm.yaml)

---

## Voice Assist - Send Messages & Media

Driving or hands messy? Use your voice to send messages and share content with loved ones via Telegram/Zalo. The Telegram blueprint supports text, map locations, images, audio, documents, videos, and voice messages. The Zalo blueprint supports text, map locations, images, stickers, and AAC voice messages.

**Key Features:**

- **Hands-Free Messaging:** Dictate your message, and Assistant will send it immediately.
- **Telegram Map Pins:** Send a precise location using latitude/longitude or a Google Maps URL containing coordinates. The blueprint sends the summary first, followed by the map pin.
- **Media Sharing:** Send local images, MP3/M4A audio, documents, MPEG-4 videos, and OGG/Opus, MP3, or M4A voice messages using paths under `local/` or `/media/`.
- **Zalo Media:** Send local images, stickers by Zalo sticker ID, or voice messages from a public HTTPS URL ending in `.aac`. Zalo voice messages support one-to-one chats only and have no caption.
- **Image Reporting:** Command to take a photo from a security camera and send it directly to a family chat group.

**Example Voice Commands:**

- "Send a list of good restaurants in Nha Trang to the Telegram family group."
- "Send the Thang Long Citadel map pin to the Telegram family group using this Google Maps link."
- "Send the monthly report PDF and the meeting recording to the Telegram family group."
- "Take a photo from the gate camera and send it to the chat group."
- "Send a Zalo sticker with ID `your-sticker-id` to my Zalo chat."
- "Send this AAC voice message to Zalo: `https://your-public-host.example/audio.aac`"

**Use Cases:**

- **Driving Safety:** "Message my wife I'll be home in 30 minutes" - Send important updates without taking your hands off the wheel, focusing on driving.
- **Urgent Notifications:** Running late? "Message mom I'm on my way home" - Quickly inform without typing.
- **Capture Moments:** "Take a photo from the yard camera and send it to the family group" - Instantly share interesting images.
- **Rich Updates:** Send reports, recordings, videos, or voice messages alongside a concise summary.

**Prerequisites & Setup:**

- Requires [Module 2: Pyscript Integration](#module-2-pyscript-integration--helper-scripts) with [`scripts/requirements.txt`](scripts/requirements.txt) and either [`scripts/telegram_bot_handle_tool.py`](scripts/telegram_bot_handle_tool.py) or [`scripts/zalo_bot_handle_tool.py`](scripts/zalo_bot_handle_tool.py) placed in `config/pyscript/`.
- Add your bot token (`telegram_bot_token` or `zalo_bot_token`) to `configuration.yaml` and `secrets.yaml` under `pyscript:`.
- Expose the script to Assist and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow) (delete `description:` in YAML edit).

_Install the blueprint for the platform you want to send messages to:_

For Telegram map pins, use coordinates or a Google Maps URL that contains coordinates. A plain address or shortened Maps URL requires a separate geocoding step.

For Zalo, provide a sticker ID from `stickers.zaloapp.com` or a public HTTPS `.aac` URL for a voice message. Zalo voice messages are limited to one-to-one chats and do not support captions.

**Send to Telegram:**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fsend_to_telegram_full_llm.yaml)

**Send to Zalo (Official Bot):**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fsend_to_zalo_bot_full_llm.yaml)

---

## Voice Assist - Internet Knowledge Search

Don't let Assistant just toggle lights. Turn it into a living encyclopedia, ready to answer any question with up-to-date data from Google.

**Note:** This feature is only applicable to Gemini, as it is integrated with Google Search to access and provide up-to-date information.

**Key Features:**

- **Infinite Knowledge:** Access Google's massive database to answer everything from history and geography to current news.
- **Smart Summarization:** No reading through long lists of links. Assistant synthesizes and provides concise, to-the-point answers.
- **Real-time Updates:** Know today's gold price, last night's football scores, or trending events on social media.

**Example Voice Commands:**

- "What is the entry score for Hanoi University of Science and Technology this year?"
- "Summarize the main events of the last World Cup final."
- "What is the current price of iPhone 17 Pro Max?"
- "Recipe for authentic Northern beef Pho."

**Use Cases:**

- **Family Arbitrator:** Arguing with your spouse about something? "What's the gold price today?" - Settle debates quickly.
- **Quick Fact-Check:** Cooking and forgot a recipe? "Recipe for flan using a rice cooker?" - Look it up instantly without pausing your cooking.
- **Convenience Anytime:** Driving or hands full? Still ask about the weather, news, history, etc.

**Prerequisites & Setup:**

- Exclusively designed for Google Generative AI (Gemini).
- Requires a Conversation Agent configured with the **Google Search** tool enabled and maximum tokens set to at least **16,384** (see [Module 3](#module-3-specialized-integrations--external-services)).
- Expose the script to Assist and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow) (delete `description:` in YAML edit).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fadvanced_google_search_full_llm.yaml)

---

## Voice Assist - YouTube Search & Playback

Transform your TV into a smart home cinema. No remote needed, no typing required-just say what you want to watch.

**Key Features:**

- **Understands Your Intent:** Find videos by describing content ("relaxing morning music," "VinFast car review") instead of rigid keywords.
- **Smart Selection:** Automatically choose the most relevant video (high views, good quality) to play.
- **Learn & Entertain:** Find lecture videos for your kids or music videos for your parents in an instant.

**Example Voice Commands:**

- "Play some soft instrumental music for reading."
- "Find a documentary about the Battle of Dien Bien Phu."
- "Show me the latest iPhone 17 Pro Max review."

**Use Cases:**

- **Child Soothing:** "Play Baby Shark" instantly to calm a crying baby without hunting for the remote.
- **Elderly Friendly:** Grandparents who can't type or see well can just ask to listen to their favorite traditional opera.
- **Work Focus:** "Play Lofi Chill music" to set the mood for work without touching your computer.

**Prerequisites & Setup:**

- Requires [Module 1: Entity Aliases Sensor](#module-1-entity-aliases-sensor-friendly-name-lookup) for TV/media player friendly-name resolution.
- Requires [Module 2: Pyscript Integration](#module-2-pyscript-integration--helper-scripts) with [`scripts/youtube_data_tool.py`](scripts/youtube_data_tool.py) and [`scripts/requirements.txt`](scripts/requirements.txt) placed in `config/pyscript/`.
- Configure your `youtube_api_key` in `configuration.yaml` and `secrets.yaml` under `pyscript:`.
- Target TV or streaming device must have the official YouTube app installed.
- Install both blueprints below, expose the scripts to Assist, and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow).

1. **Search Blueprint (LLM):** Analyzes the query and finds the right video.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fadvanced_youtube_search_full_llm.yaml)
2. **Player Blueprint:** Gets the video info and plays it on the media player.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fplay_youtube_video_full_llm.yaml)

---

## Voice Assist - Favorite YouTube Channels

Are you a die-hard fan of "MrBeast" or "Linus Tech Tips"? This blueprint ensures you never miss the latest videos from your favorite creators.

**Key Features:**

- **Stay Updated:** Automatically check your subscribed channels for new content.
- **Instant Playback:** A command like "Are there new videos?" will automatically play the latest release on your TV.
- **Proactive Notifications:** Receive messages as soon as your favorite channels upload new content.

**Example Voice Commands:**

- "Does Outdoor Boys have anything new?"
- "Play the latest video from Gordon Ramsay."

**Use Cases:**

- **Never Miss Your Favorite Creator:** Get notified automatically when your favorite YouTube channels (streamers, vloggers...) upload new videos, no manual checking needed.
- **Personalized Entertainment:** Just woke up? "Is there anything new on VTV News?" for updates, or "Play the latest video from FAPTV" to relax.

[**View the detailed guide**](/home_assistant_play_favorite_youtube_channel_videos_en.md)

**Prerequisites & Setup:**

- Requires [Module 1: Entity Aliases Sensor](#module-1-entity-aliases-sensor-friendly-name-lookup) for TV/media player friendly-name resolution.
- Requires [Module 2: Pyscript Integration](#module-2-pyscript-integration--helper-scripts) with [`scripts/youtube_data_tool.py`](scripts/youtube_data_tool.py) and [`scripts/requirements.txt`](scripts/requirements.txt) placed in `config/pyscript/`.
- Configure your `youtube_api_key` in `configuration.yaml` and `secrets.yaml` under `pyscript:`.
- Target TV or streaming device must have the official YouTube app installed.
- Install both blueprints below, expose the scripts to Assist, and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow).

1. **Info Getter Blueprint (LLM):** Checks the channel and gets the latest video info.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fget_youtube_video_info_full_llm.yaml)
2. **Player Blueprint:** Gets the video info and plays it on the media player (can be reused from the blueprint above).
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fplay_youtube_video_full_llm.yaml)

---

## Voice Assist - Smart Fan Control

Feeling hot? Just say the word, and your fan will speed up. This blueprint is a comprehensive upgrade, combining speed and oscillation control into a single tool.

**Why use this Blueprint instead of the built-in HassFanSetSpeed?**

Although Home Assistant already supports basic fan control, this blueprint offers a more natural and powerful experience:

- **2-in-1 Combination:** Controls both speed and oscillation in a single command, which the default tool cannot do.
- **Relative Adjustment:** Supports commands like "increase speed" or "decrease speed" instead of only setting fixed levels.
- **Smart Recognition:** Integrates advanced alias lookup, allowing you to refer to fans by your preferred names (e.g., "Standing fan," "Ceiling fan") without changing the original entity name.

**Key Features:**

- **Flexible Adjustment:** Increase/decrease speed by a specific percentage, custom steps, or desired level.
- **Comprehensive Control:** Turn oscillation on/off and adjust airflow simultaneously.
- **Synchronized Control:** Command a specific fan or all fans in the house.

**Example Voice Commands:**

- "Increase the living room fan to maximum and turn on oscillation."
- "Reduce the ceiling fan speed a bit."
- "Turn on oscillation for all fans."
- "Set the table fan to 50%."

**Use Cases:**

- **Comfort from Bed/Sofa:** Adjust the airflow to suit the room's temperature without leaving your comfy spot.
- **Quick "Breeze" Setup:** Quickly set a "breeze" mode (low speed and oscillation) for the bedroom before going to sleep.

**Prerequisites & Setup:**

- Requires [Module 1: Entity Aliases Sensor](#module-1-entity-aliases-sensor-friendly-name-lookup) configured in `configuration.yaml`.
- Expose your fan entities to Assist with custom aliases if desired.
- Expose the script to Assist and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow) (delete `description:` in YAML edit).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ffan_speed_and_oscillation_control_full_llm.yaml)

---

## Voice Assist - Smart AC Control

Maintain fresh air and ideal temperatures in your home using just your voice. This blueprint gives you comprehensive control over your air conditioner, from operating modes and temperature to fan speed.

**Why use this Blueprint instead of built-in features?**

Home Assistant's default actions (`HassClimateSetTemperature`, `HassTurnOn/Off`) primarily focus on turning devices on/off or setting the temperature. They **do not support fan speed control** and are limited in handling flexible mode switching (Cool, Dry, Heat...) within a single command.

This blueprint solves these limitations entirely:

- **All-in-One Control (Mode + Fan + Temp):** You can issue a complete command like _"Turn on the AC to 24 degrees, cool mode, max fan speed"_, and the system handles it perfectly in a **single turn**.
- **Smart Logic:**
  - **Auto-rounding:** If the device only supports 1-degree steps, but you say "24.5 degrees", the script automatically rounds it instead of erroring out.
  - **Unit Handling:** Automatically detects and handles Fahrenheit/Celsius conversions, ensuring safety with min/max limits.
  - **Pre-check:** Validates if the requested temperature is within the device's allowed range before sending the command.
- **Alias Support:** Identifies devices accurately via your custom friendly aliases, working better than the default mechanism in complex situations.

**Key Features:**

- **Mode Control:** Easily switch between cooling, heating, dry, fan-only, or auto modes.
- **Temperature Control:** Set precise temperatures with smart safety mechanisms.
- **Fan Speed Adjustment:** Set fan speed to preset levels (low, medium, high) or qualitative values like "maximum," "minimum."
- **Multi-Device Handling:** Control one or multiple air conditioners simultaneously.

**Example Voice Commands:**

- "Set the living room AC to 24 degrees and max fan speed."
- "Change the bedroom AC to dry mode."
- "Increase the hallway AC temperature to 26 degrees."
- "Turn off all air conditioners."

**Use Cases:**

- **"Night Mode":** When you're sleeping and feel too cold or hot, just say a command to adjust it without opening your eyes to find the remote or being blinded by your phone screen.
- **Elderly & Child Friendly:** Instead of remembering complex symbols on the remote (snowflake, water drop...), family members can just use natural commands: _"Turn on dry mode"_.
- **Totally Hands-Free:** Just got home with your hands full? Simply say: _"Turn on the AC to 20 degrees, max wind"_ to enjoy cool air instantly without manual operation.

**Prerequisites & Setup:**

- Requires a smart air conditioner (climate entity) integrated into Home Assistant.
- Requires [Module 1: Entity Aliases Sensor](#module-1-entity-aliases-sensor-friendly-name-lookup) configured in `configuration.yaml`.
- Expose your climate entities to Assist with custom aliases if desired.
- Expose the script to Assist and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow) (delete `description:` in YAML edit).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fac_mode_and_fan_control_full_llm.yaml)

---

## Voice Assist - Weather Forecast

Retrieve home weather forecasts for specific periods (hourly or daily) using natural voice commands.

**Key Features:**

- **Detailed Info:** Supports both hourly and daily forecasts.
- **Flexible Queries:** Ask about the weather for today, tomorrow, the weekend, or specific times like "this afternoon" or "tomorrow night".
- **Smart Averaging:** Automatically summarizes data to provide concise responses (e.g., average temperature, most frequent condition).

**Example Voice Commands:**

- "What's the weather like today?"
- "Will it rain this afternoon?"
- "What's the forecast for this weekend?"

**Credit:**

- Special thanks to the original blueprint from [TheFes/ha-blueprints](https://github.com/TheFes/ha-blueprints). This version has been refined and optimized specifically for use with Gemini.

**Prerequisites & Setup:**

- Configure a weather entity that provides both hourly and daily forecasts in the blueprint inputs.
- Expose the script to Assist and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow) (delete `description:` in YAML edit).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fweather_forecast_full_llm.yaml)

---

## Voice Assist - Music Control

Control music via Music Assistant using voice commands. Supports searching by track, album, artist, playlist, and radio.

**Key Features:**

- **Smart Search:** Finds and plays the exact content you request.
- **Broad Support:** Works with tracks, albums, artists, playlists, and radio stations.
- **Flexible Customization:** Supports selecting playback areas, specific players, and shuffle mode.

**Example Voice Commands:**

- "Play music by Queen in the living room."
- "Start the 'Chill Hits' playlist and turn on shuffle."
- "Play the song 'Bohemian Rhapsody'."

**Credit:**

- Special thanks to the original blueprint from [music-assistant/voice-support](https://github.com/music-assistant/voice-support). This version has been refined and optimized specifically for use with Gemini.

**Prerequisites & Setup:**

- Requires the **Music Assistant** integration configured in Home Assistant (see [Module 3](#module-3-specialized-integrations--external-services)).
- Expose the script to Assist and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow) (delete `description:` in YAML edit).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fcontrol_music_full_llm.yaml)

---

## Voice Assist - Device Location & Find

"Where's my phone?" - The classic morning question. Let Assistant help you find it instantly.

**Key Features:**

- **Indoor Positioning:** Tells you which room your phone is in (based on Bluetooth/Wi-Fi signals).
- **Trigger Ringing:** Make your phone ring loudly, even if it's on silent mode.
- **Multi-Device Support:** Find iPhones, Androids, iPads, or any device with the Home Assistant app installed.

**Example Voice Commands:**

- "Where is Dad's phone right now?"
- "Make the iPad ring, I can't find it."

**Use Cases:**

- **The "Silent Mode" Nightmare:** Phone fell in the sofa, and it's on silent? Assistant will make it ring loudly instantly.
- **Morning Rush:** Late for work and can't find your car keys or phone? Just ask to locate which room they are in.

[**View the detailed guide**](/home_assistant_device_location_lookup_guide_en.md)

**Prerequisites & Setup:**

- Requires [Module 1: Entity Aliases Sensor](#module-1-entity-aliases-sensor-friendly-name-lookup) for device friendly-name resolution.
- Expose Bermuda Device Tracker or Mobile App Device Tracker entities to Assist (only one tracker per physical device; see [guide](/home_assistant_device_location_lookup_guide_en.md)).
- For ringing: Target mobile device must have Home Assistant Companion App with notification permissions (and Critical Alerts on iOS).
- Install both blueprints below, expose the scripts to Assist, and follow the [Assist Tool Setup](#universal-blueprint-installation-workflow).

1. **Location Finder Blueprint (LLM):** Processes the request and finds the device's location.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevice_location_lookup_full_llm.yaml)
2. **Ringing Blueprint (LLM):** Triggers the device to ring.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevice_ringing_full_llm.yaml)

---

## Device State Synchronization

Seamlessly synchronize the `on/off` state between multiple devices, acting like a virtual two-way staircase switch for enhanced control.

**Use Cases:**

- **Old House, Smart Switches:** Flexibly control lights in stairwells or hallways from multiple switches, including mechanical or wireless ones.
- **Group Lighting:** Flipping one physical switch activates all lights in an area (ceiling light, accent lights, decorative lights) simultaneously, instantly creating the desired ambiance.

**Prerequisites & Setup:**

- Target entities must support `homeassistant.turn_on` and `homeassistant.turn_off`.
- Standard automation blueprint; select the linked entities in the UI and save.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Flink_multiple_devices.yaml)

---

## Additional Tutorials

### [How to write custom system instructions for Voice Assist](/home_assistant_voice_instructions_en.md)

### [Play new videos from favorite YouTube channels](/home_assistant_play_favorite_youtube_channel_videos_en.md)

### [Monitor unavailable devices](/home_assistant_unavailable_devices_en.md)

### [Auto-switch iOS Themes](/home_assistant_ios_themes_en.md)

### [Device location lookup guide](/home_assistant_device_location_lookup_guide_en.md)

---

**If you find these blueprints helpful, please share them with the Home Assistant community! Be sure to follow along for more unique blueprints coming soon!**
