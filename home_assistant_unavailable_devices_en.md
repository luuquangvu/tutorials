# Monitoring & Notifying Unavailable Devices

This guide helps you automatically monitor and receive notifications whenever any device in Home Assistant becomes "Unavailable" or "Unknown".

## Step 1: Create a Monitoring Sensor

We will create a smart `binary_sensor` that automatically scans your entire system for faulty devices, while allowing you to exclude (ignore) unimportant ones.

### 1.1. Create a Label for Management

To avoid false alarms from devices you don't care about, create a label to mark them.

1. Go to **Settings** > **Devices & Services** > **Labels**.
2. Create a new label named: `ignored`

![image](images/20250426_GwdtEl.png)

### 1.2. Assign the Label to Ignored Devices

Assign the `ignored` label to any device or entity you **do not** want to be notified about when it goes offline.

![image](images/20250426_oj1S9U.png)

### 1.3. Configure Template Sensor

Add the following code to your `configuration.yaml` file. This sensor automatically filters out devices with the `ignored` label, as well as button or scene entities which naturally don't have a connection state.

```yaml
template:
  - binary_sensor:
      - name: Unavailable Devices
        unique_id: unavailable_devices
        device_class: problem
        icon: >-
          {% set raw_items = (this.attributes.raw if (this is defined and this and this.attributes is defined and 'raw' in this.attributes) else []) %}
          {{ iif((raw_items | length > 0), 'mdi:alert-circle', 'mdi:check-circle') }}
        state: >-
          {% set raw_items = (this.attributes.raw if (this is defined and this and this.attributes is defined and 'raw' in this.attributes) else []) %}
          {{ raw_items | length > 0 }}
        attributes:
          devices: >-
            {% set raw_items = (this.attributes.raw if (this is defined and this and this.attributes is defined and 'raw' in this.attributes) else []) %}
            {{ raw_items | map('device_id') | reject('none') | unique | map('device_attr', 'name') | list }}
          entities: >-
            {% set raw_items = (this.attributes.raw if (this is defined and this and this.attributes is defined and 'raw' in this.attributes) else []) %}
            {{ raw_items }}
          raw: >-
            {% set ignored_domains = ['button', 'event', 'input_button', 'scene', 'stt', 'tts', 'zone'] %}
            {% set ignored_integrations = ['browser_mod', 'demo', 'group', 'mobile_app', 'private_ble_device'] %}
            {% set ignored_label = 'ignored' %}
            {% set ignored_integration_entities = namespace(entities=[]) %}
            {% for integration in ignored_integrations %}
              {% set ignored_integration_entities.entities = ignored_integration_entities.entities + integration_entities(integration) %}
            {% endfor %}
            {% set current_entity = this.entity_id if (this is defined and this and this.entity_id is defined) else 'binary_sensor.unavailable_devices' %}
            {% set candidates = states
              | selectattr('state', 'eq', 'unavailable')
              | rejectattr('entity_id', 'eq', current_entity)
              | rejectattr('domain', 'in', ignored_domains)
              | rejectattr('entity_id', 'in', ignored_integration_entities.entities)
              | map(attribute='entity_id')
              | list %}
            {% set ns = namespace(final=[]) %}
            {% for entity_id in candidates %}
              {% set dev_id = device_id(entity_id) %}
              {% if ignored_label not in labels(entity_id) and (not dev_id or ignored_label not in labels(dev_id)) %}
                {% set ns.final = ns.final + [entity_id] %}
              {% endif %}
            {% endfor %}
            {{ ns.final }}
```

_After saving the file, please **Restart** Home Assistant (or reload Template Entities) to apply the changes._

## Step 2: Create Automation Notifications

The automations below will send a notification when an issue occurs, and automatically clear the notification when the issue is resolved.

### Option 1: Persistent Notification (on Home Assistant Dashboard)

```yaml
alias: "System: Notify Unavailable Devices (Persistent)"
description: ""
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.unavailable_devices
    attribute: entities
conditions:
  - condition: template
    value_template: "{{ trigger.to_state is not none and trigger.to_state.state not in ['unavailable', 'unknown'] }}"
actions:
  - variables:
      entities: "{{ state_attr(trigger.entity_id, 'entities') | default([], true) }}"
      devices: "{{ state_attr(trigger.entity_id, 'devices') | default([], true) }}"
      notify_tag: "{{ 'tag_' ~ (this.attributes.id | default(this.entity_id.split('.')[1] | default('unavailable_devices', true), true)) }}"
  - if:
      - condition: template
        value_template: "{{ entities | length > 0 }}"
    then:
      - action: persistent_notification.create
        data:
          notification_id: "{{ notify_tag }}"
          title: "Devices Unavailable"
          message: |-
            ### {{ devices | length }} devices ({{ entities | length }} entities) are having issues.

            **Devices:**
            {% for device in devices %}- {{ device }}
            {% endfor %}

            **Entity Details:**
            {% for entity in entities %}- {{ entity }}
            {% endfor %}
    else:
      - action: persistent_notification.dismiss
        data:
          notification_id: "{{ notify_tag }}"
mode: queued
max: 10
```

### Option 2: Mobile App Notification

```yaml
alias: "System: Notify Unavailable Devices (Mobile)"
description: ""
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.unavailable_devices
    attribute: entities
conditions:
  - condition: template
    value_template: "{{ trigger.to_state is not none and trigger.to_state.state not in ['unavailable', 'unknown'] }}"
actions:
  - variables:
      entities: "{{ state_attr(trigger.entity_id, 'entities') | default([], true) }}"
      devices: "{{ state_attr(trigger.entity_id, 'devices') | default([], true) }}"
      notify_tag: "{{ 'tag_' ~ (this.attributes.id | default(this.entity_id.split('.')[1] | default('unavailable_devices_mobile', true), true)) }}"
  - if:
      - condition: template
        value_template: "{{ entities | length > 0 }}"
    then:
      - action: notify.mobile_app_iphone # Replace with your phone's notification action (e.g. notify.mobile_app_<your_phone>)
        data:
          title: "Devices Lost Connection"
          message: >-
            {{ devices | length }} devices ({{ entities | length }} entities) are currently unavailable.
          data:
            tag: "{{ notify_tag }}"
            url: /lovelace/system # (Optional) Path to your system dashboard
    else:
      - action: notify.mobile_app_iphone # Replace with your phone's notification action
        data:
          message: clear_notification
          data:
            tag: "{{ notify_tag }}"
mode: queued
max: 10
```

## Step 3: Dashboard Display (Optional)

You can add this Markdown card to your dashboard. It will automatically hide when the system is healthy and only appear when there are faulty devices.

```yaml
type: markdown
title: Unavailable Devices
content: |-
  {% set entities = state_attr('binary_sensor.unavailable_devices', 'entities') | default([], true) -%}
  {% set devices = state_attr('binary_sensor.unavailable_devices', 'devices') | default([], true) -%}

  **Overview:** {{ devices | length }} devices - {{ entities | length }} entities.

  ---
  **Device List:**
  {% for device in devices %}- **{{ device }}**
  {% endfor %}

  **Entity Details:**
  {% for entity in entities %}- `{{ entity }}`
  {% endfor %}
visibility:
  - condition: state
    entity: binary_sensor.unavailable_devices
    state: "on"
```
