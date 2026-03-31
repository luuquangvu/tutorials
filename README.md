# Unique Home Assistant Blueprints & Tutorials

**[ 🇺🇸 English | [🇻🇳 Tiếng Việt](README_vi.md) ]**

> [!TIP]
> **[Blueprints Updater](https://github.com/luuquangvu/blueprints-updater)**: A highly useful integration that automatically updates blueprints in this collection. When you have many blueprints from different sources, keeping track of updates can be challenging - this integration handles it for you automatically.

**Google has recently significantly cut back on the free Gemini API, making it almost impossible to meet the usage needs of Home Assistant. You can find [a completely free alternative solution here](https://github.com/luuquangvu/ha-addons).**

_All blueprints in this collection are fine-tuned to work best with **Gemini Flash** models. Other models may require minor adjustments to behave as expected._

Transform Home Assistant into a fully-fledged personal teammate with this curated collection of blueprints and guides. Every scenario has been proven in real homes, backed by clear explanations, example voice prompts, and deployment tips so you can bring each idea to life right away.

---

## Table of Contents

- [Unique Home Assistant Blueprints \& Tutorials](#unique-home-assistant-blueprints--tutorials)
  - [Table of Contents](#table-of-contents)
  - [Voice Assist - Smart Scheduling \& Timers](#voice-assist---smart-scheduling--timers)
  - [Voice Assist - Memory \& Information Retrieval](#voice-assist---memory--information-retrieval)
  - [Voice Assist - Camera Image Analysis](#voice-assist---camera-image-analysis)
  - [Voice Assist - Calendar \& Event Management](#voice-assist---calendar--event-management)
    - [Create Calendar Events](#create-calendar-events)
    - [Calendar Events Lookup](#calendar-events-lookup)
  - [Voice Assist - Lunar Calendar Lookup \& Conversion](#voice-assist---lunar-calendar-lookup--conversion)
    - [Lunar Calendar Conversion \& Lookup](#lunar-calendar-conversion--lookup)
    - [Create Lunar Calendar Events](#create-lunar-calendar-events)
  - [Interactive Smart Home Chatbot](#interactive-smart-home-chatbot)
  - [Voice Assist - Send Messages \& Images](#voice-assist---send-messages--images)
  - [Voice Assist - Internet Knowledge Search](#voice-assist---internet-knowledge-search)
  - [Voice Assist - YouTube Search \& Playback](#voice-assist---youtube-search--playback)
  - [Voice Assist - Favorite YouTube Channels](#voice-assist---favorite-youtube-channels)
  - [Voice Assist - Smart Fan Control](#voice-assist---smart-fan-control)
  - [Voice Assist - Smart AC Control](#voice-assist---smart-ac-control)
  - [Voice Assist - Weather Forecast](#voice-assist---weather-forecast)
  - [Voice Assist - Music Control](#voice-assist---music-control)
  - [Voice Assist - Device Location \& Find](#voice-assist---device-location--find)
  - [Voice Assist - Traffic Fine Lookup](#voice-assist---traffic-fine-lookup)
  - [Automatic Traffic Fine Notifications](#automatic-traffic-fine-notifications)
  - [Device State Synchronization](#device-state-synchronization)
  - [Obsolete Blueprints](#obsolete-blueprints)
    - [Voice Assist - Smart Fan Control (Legacy)](#voice-assist---smart-fan-control-legacy)
    - [Voice Assist - Device Control Timer (Legacy)](#voice-assist---device-control-timer-legacy)
  - [Additional Tutorials](#additional-tutorials)
    - [How to write custom system instructions for Voice Assist](#how-to-write-custom-system-instructions-for-voice-assist)
    - [Play new videos from favorite YouTube channels](#play-new-videos-from-favorite-youtube-channels)
    - [Monitor unavailable devices](#monitor-unavailable-devices)
    - [Auto-switch iOS Themes](#auto-switch-ios-themes)
    - [Device location lookup guide](#device-location-lookup-guide)

---

**Note:** Please make sure to read each blueprint's description and follow its instructions when installing or updating.

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

For full functionality, you need to install **all 3 blueprints**:

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
- **Smart Retrieval:** No need to remember exact keywords. Just ask "Where is the car?" or "What's the wifi pass?", and the assistant will find the most relevant info.
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
- "Check if the cat is in the front yard or the back yard?"
- "Look to see if the garage door is closed."
- "Is there any strange car in the yard?"

**Use Cases:**

- **Delivery Check:** "Is there a package at the door?" when you're on the 3rd floor and too lazy to run down.
- **Anxiety Relief:** Already in bed but suddenly panicked "Is the gate closed?", just ask Assistant to check for you.
- **Pet Monitor:** Check if your pet is sleeping nicely or digging up the garden.

To use this feature, you need to install **both blueprints**:

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

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fcreate_calendar_event_full_llm.yaml)

### Calendar Events Lookup

Inquire about and retrieve information regarding existing events in your calendar, such as birthdays, appointments, or anniversaries.

**Example Voice Commands:**

- "What events are happening this week?"
- "What's on the calendar for this month?"

**Use Cases:**

- **Before Leaving Home:** Quickly check your schedule for the day or week without needing to open your calendar app on your phone.
- **Confirm Plans:** Easily verify to ensure no double-bookings or missed important events.

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

_Install the webhook blueprint for your chosen platform. For image analysis, also install the Analyzer blueprint._

**Webhook for Telegram:**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ftelegram_bot_webhook.yaml)

**Webhook for Zalo (Official Account):**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fzalo_bot_webhook.yaml)

**Webhook for Zalo (Custom Bot):**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fzalo_custom_bot_webhook.yaml)

**(Optional) Image Analyzer Blueprint:**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ffile_content_analyzer_full_llm.yaml)

---

## Voice Assist - Send Messages & Images

Driving or hands messy? Use your voice to send messages, share your location, or send camera images to loved ones via Telegram/Zalo.

**Key Features:**

- **Hands-Free Messaging:** Dictate your message, and Assistant will send it immediately.
- **Smart Sharing:** Automatically attach Google Maps links when you mention a location.
- **Image Reporting:** Command to take a photo from a security camera and send it directly to a family chat group.

**Example Voice Commands:**

- "Send a list of good restaurants in Nha Trang to the Telegram family group."
- "Send the Thang Long Citadel location via Zalo to my wife."
- "Take a photo from the gate camera and send it to the chat group."

**Use Cases:**

- **Driving Safety:** "Message my wife I'll be home in 30 minutes" - Send important updates without taking your hands off the wheel, focusing on driving.
- **Urgent Notifications:** Running late? "Message mom I'm on my way home" - Quickly inform without typing.
- **Capture Moments:** "Take a photo from the yard camera and send it to the family group" - Instantly share interesting images.

_Install the blueprint for the platform you want to send messages to:_

**Send to Telegram:**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fsend_to_telegram_full_llm.yaml)

**Send to Zalo (Official Bot):**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fsend_to_zalo_bot_full_llm.yaml)

**Send to Zalo (Custom Bot):**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fsend_to_zalo_custom_bot_full_llm.yaml)

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
- **Convenience Anytime:** Driving or hands full? Still ask about weather, news, history, etc.

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

To use this feature, you need to install **both blueprints**:

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

To use this feature, you need to install **both blueprints**:

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

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ffan_speed_and_oscillation_control_full_llm.yaml)

---

## Voice Assist - Smart AC Control

Maintain fresh air and ideal temperatures in your home using just your voice. This blueprint gives you comprehensive control over your air conditioner, from operating modes and temperature to fan speed.

**Why use this Blueprint instead of built-in features?**

Home Assistant's default actions (`HassClimateSetTemperature`, `HassTurnOn/Off`) primarily focus on turning devices on/off or setting the temperature. They **do not support fan speed control** and are limited in handling flexible mode switching (Cool, Dry, Heat...) within a single command.

This blueprint solves these limitations entirely:

- **All-in-One Control (Mode + Fan + Temp):** You can issue a complete command like _"Turn on the AC to 24 degrees, cool mode, max fan speed"_, and the system handles it perfectly in a **single turn**.
- **Smart Logic:**
  - **Auto-rounding:** If the device only supports 1-degree steps but you say "24.5 degrees", the script automatically rounds it instead of erroring out.
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

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fac_mode_and_fan_control_full_llm.yaml)

---

## Voice Assist - Weather Forecast

Retrieve home weather forecasts for specific periods (hourly or daily) using natural voice commands.

**Key Features:**

- **Detailed Info:** Supports both hourly and daily forecasts.
- **Flexible Queries:** Ask about weather for today, tomorrow, the weekend, or specific times like "this afternoon" or "tomorrow night".
- **Smart Averaging:** Automatically summarizes data to provide concise responses (e.g., average temperature, most frequent condition).

**Example Voice Commands:**

- "What's the weather like today?"
- "Will it rain this afternoon?"
- "What's the forecast for this weekend?"

**Credit:**

- Special thanks to the original blueprint from [TheFes/ha-blueprints](https://github.com/TheFes/ha-blueprints). This version has been refined and optimized specifically for use with Gemini.

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

- **The "Silent Mode" Nightmare:** Phone fell in the sofa and it's on silent? Assistant will make it ring loudly instantly.
- **Morning Rush:** Late for work and can't find your car keys or phone? Just ask to locate which room they are in.

[**View the detailed guide**](/home_assistant_device_location_lookup_guide_en.md)

To use this feature, you need to install **both blueprints**:

1. **Location Finder Blueprint (LLM):** Processes the request and finds the device's location.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevice_location_lookup_full_llm.yaml)
2. **Ringing Blueprint (LLM):** Triggers the device to ring.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevice_ringing_full_llm.yaml)

---

## Voice Assist - Traffic Fine Lookup

Drive with peace of mind. Check traffic violation status for any vehicle by voice, using live data from the national traffic police portal.

**Note:** This feature is only applicable to the traffic fine system in Vietnam.

**Key Features:**

- **Real-time Checks:** Instantly query the official database for traffic violations.
- **Any Vehicle:** Check fines for your car, motorbike, or even a vehicle you're considering buying.
- **Proactive Awareness:** Stay informed and avoid accumulating late fees.

**Example Voice Commands:**

- "Check traffic fines for car 30G-123.45."
- "Does motorbike 29-T1 567.89 have any fines?"

**Use Cases:**

- **Periodic Checks:** "Check fines for car 30A-123.45" - Ensure your vehicle has no outstanding violations before inspections or administrative procedures.
- **Proactive Management:** Proactively check your or your family's traffic fine status to handle them promptly and avoid unnecessary complications.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ftraffic_fine_lookup_full_llm.yaml)

---

## Automatic Traffic Fine Notifications

Never miss an important alert. Receive instant notifications the moment a new traffic violation is recorded for your vehicle in the national police system.

**Note:** This feature is only applicable to the traffic fine system in Vietnam.

**Key Features:**

- **Continuous Monitoring:** Periodically scans the system to detect new violations automatically.
- **Instant Alerts:** Get a notification directly to Home Assistant as soon as a fine is detected.
- **Multi-Vehicle Support:** Easily configure to monitor multiple license plates for your entire family.

**Use Cases:**

- **Timely Awareness:** Receive immediate alerts to address traffic fines promptly, preventing accumulating penalties or escalated issues.
- **Proactive Management:** Automatically monitor and manage the traffic fine status for all your household vehicles without manual checks.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ftraffic_fine_notification.yaml)

---

## Device State Synchronization

Seamlessly synchronize the `on/off` state between multiple devices, acting like a virtual two-way staircase switch for enhanced control.

**Use Cases:**

- **Old House, Smart Switches:** Flexibly control lights in stairwells or hallways from multiple switches, including mechanical or wireless ones.
- **Group Lighting:** Flipping one physical switch activates all lights in an area (ceiling light, accent lights, decorative lights) simultaneously, instantly creating the desired ambiance.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Flink_multiple_devices.yaml)

---

## Obsolete Blueprints

**Important Note:** To ensure optimal LLM performance and avoid confusion in tool selection, it is NOT RECOMMENDED to install blueprints in this section concurrently with their corresponding new versions. Always prioritize using the latest and recommended blueprints.

### Voice Assist - Smart Fan Control (Legacy)

**Use the new [Voice Assist - Smart Fan Control](#voice-assist---smart-fan-control) that integrates both speed and oscillation.**

**Fan Speed Control:**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ffan_speed_control_full_llm.yaml)

**Fan Oscillation Control:**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ffan_oscillation_control_full_llm.yaml)

### Voice Assist - Device Control Timer (Legacy)

**Use the new [Voice Assist - Smart Scheduling & Timers](#voice-assist---smart-scheduling--timers) for more features.**

To use this, you need to install **both blueprints**:

1. **Controller Blueprint (LLM):**
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevice_control_timer_full_llm.yaml)
2. **Timer Tool Blueprint:**
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevice_control_tool.yaml)

---

## Additional Tutorials

### [How to write custom system instructions for Voice Assist](/home_assistant_voice_instructions_en.md)

### [Play new videos from favorite YouTube channels](/home_assistant_play_favorite_youtube_channel_videos_en.md)

### [Monitor unavailable devices](/home_assistant_unavailable_devices_en.md)

### [Auto-switch iOS Themes](/home_assistant_ios_themes_en.md)

### [Device location lookup guide](/home_assistant_device_location_lookup_guide_en.md)

---

**If you find these blueprints helpful, please share them with the Home Assistant community! Be sure to follow along for more unique blueprints coming soon!**
