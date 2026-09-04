# Guide to Install iOS Themes for Home Assistant

This guide helps you install a beautiful set of iOS themes, automatically switch between Light/Dark modes according to time, and store local backgrounds for faster loading.

## 1. Install Necessary Components

- **HACS:** Ensure you have [HACS](https://github.com/hacs) installed.
- **Themes Configuration:** Ensure your `configuration.yaml` file includes the configuration line to load themes (if not, add it):

  ```yaml
  frontend:
    themes: !include_dir_merge_named themes
  ```

### Install via HACS

1. In Home Assistant, open **HACS**.
2. Search for and download **iOS Themes** ([basnijholt/lovelace-ios-themes](https://github.com/basnijholt/lovelace-ios-themes)).

## 2. Configure Local Backgrounds

This helps backgrounds load faster from your local network instead of downloading from the internet every time you open the app.

1. Use File Editor or VS Code to access your Home Assistant configuration directory.
2. Navigate to the `themes/ios-themes` folder (where HACS downloaded the themes).
3. Copy all `.jpg` image files from there.
4. Paste them into the `www/ios-themes` folder.
   - _If the `www` folder does not exist, create it at the same level as your `configuration.yaml` file._
   - _If the `ios-themes` folder does not exist within `www`, create it._
5. **Restart** Home Assistant to apply the changes.

## 3. Create Automatic Theme Switching (Auto Light/Dark)

### 3.1. Create Helper Entities

You can add the code to `configuration.yaml` or create them via the UI (Settings > Devices & Services > Helpers).

**YAML Code (add to configuration.yaml):**

```yaml
input_select:
  choose_default_theme:
    name: Choose Default Theme
    icon: mdi:palette-outline
    options:
      - iOS Themes
      - Frosted Glass Themes
  ios_themes:
    name: iOS Themes
    icon: mdi:palette
    options:
      - dark-green
      - light-green
      - dark-blue
      - light-blue
      - blue-red
      - orange
      - red

input_boolean:
  ios_themes_dark_mode:
    name: iOS Themes Dark Mode
    icon: mdi:theme-light-dark
  ios_themes_local_backgrounds:
    name: iOS Themes Local Backgrounds
    icon: mdi:cloud
    initial: on
```

### 3.2. Create Automation

**Optimized automation:** This single automation handles everything and only runs when iOS Themes is active to avoid overriding other theme preferences.

```yaml
alias: Auto change iOS themes
description: Automatically switch between Light/Dark themes and select random color
triggers:
  - trigger: sun
    event: sunrise
    id: sun
  - trigger: sun
    event: sunset
    id: sun
  - trigger: state
    entity_id:
      - input_select.ios_themes
      - input_boolean.ios_themes_dark_mode
      - input_boolean.ios_themes_local_backgrounds
    id: apply
conditions:
  - condition: state
    entity_id: input_select.choose_default_theme
    state: iOS Themes
actions:
  - if:
      - condition: trigger
        id: sun
    then:
      - action: input_boolean.turn_{{ 'on' if trigger.event == 'sunset' else 'off' }}
        target:
          entity_id: input_boolean.ios_themes_dark_mode
      - action: input_select.select_option
        target:
          entity_id: input_select.ios_themes
        data:
          option: "{{ state_attr('input_select.ios_themes', 'options') | random }}"
      - stop: Settings updated. Waiting for re-trigger to apply theme.
  - delay: "00:00:01"
  - action: frontend.set_theme
    data:
      name: >-
        {% set is_dark = is_state('input_boolean.ios_themes_dark_mode', 'on') %}
        {% set mode = 'dark' if is_dark else 'light' %}
        {% set color = states('input_select.ios_themes') %}
        {% set suffix = '-alternative' if is_state('input_boolean.ios_themes_local_backgrounds', 'on') else '' %}
        ios-{{ mode }}-mode-{{ color }}{{ suffix }}
mode: restart
```

_Note: If you have Spook installed, you can also use `action: input_select.random` instead of `input_select.select_option`._

## 4. Activate Theme on Your Device

**Most Important Step:** For the automation to change your interface, you must select **Backend-selected** (or **Use default theme**) mode in your user settings.

1. Click on your **User Profile** icon in the bottom-left corner of the sidebar.
2. Under **Theme**, select **Backend-selected** (or **Use default theme**).
