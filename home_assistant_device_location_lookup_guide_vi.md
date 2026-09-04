# Hướng dẫn Cấu hình Voice Assist để Tìm kiếm Thiết bị

![image](images/20250608_ASxwFa.png)

## Tính năng

- **Định vị:** Voice Assist sẽ cho bạn biết thiết bị có ở nhà không, và cụ thể đang ở phòng nào (nếu hệ thống xác định được).
- **Hỗ trợ BLE đa dạng:** Hoạt động với mọi thiết bị BLE được theo dõi bởi integration [Bermuda BLE Trilateration](https://github.com/agittins/bermuda) (Android, iOS, đồng hồ thông minh, thẻ định vị...).
- **Hỗ trợ thiết bị di động:** Định vị bất kỳ thiết bị nào có cài đặt ứng dụng Home Assistant Companion.
- **Đổ chuông tìm kiếm:** Nếu thiết bị có cài App Home Assistant, Voice Assist có thể kích hoạt đổ chuông ngay cả khi điện thoại đang ở chế độ "Không làm phiền" (Do Not Disturb).
- **Bảo mật:** LLM không truy cập tọa độ GPS thực tế của bạn. Nó chỉ nhận thông tin chung (Ở nhà/Vắng nhà, tên phòng) khi bạn yêu cầu tìm thiết bị.

## Hạn chế

- **Yêu cầu LLM:** Chỉ hoạt động với các trợ lý ảo dựa trên LLM (như Gemini, OpenAI).
- **Thực thể hỗ trợ:** Chỉ hỗ trợ thực thể `device_tracker` từ Bermuda hoặc Mobile App.

## Yêu cầu trước khi cài đặt

- **Bermuda BLE Trilateration:** (Khuyên dùng) Cài đặt qua HACS để có khả năng định vị chính xác theo từng phòng. Hãy đảm bảo các Bluetooth proxy hoặc scanner (ESPHome, Shelly...) đã được gán vào đúng các **Khu vực (Areas)** tương ứng trong Home Assistant để Bermuda có thể xác định tên phòng.
- **Home Assistant Companion App:** Cài trên điện thoại/máy tính bảng để sử dụng tính năng đổ chuông (cần cấp quyền thông báo và thông báo khẩn cấp/critical alerts trên iOS).

## Hướng dẫn Cài đặt

### Bước 1: Công khai (Expose) Device Tracker cho Voice Assist

1. Truy cập **Cài đặt** > **Trợ lý giọng nói** > **Expose**.
2. Chỉ expose **một** thực thể `device_tracker` duy nhất cho mỗi thiết bị vật lý.
3. **Mẹo:** Đặt thêm **Biệt danh (Alias)** cho thiết bị (ví dụ: "Điện thoại của tôi", "Chìa khóa") để gọi tên tự nhiên hơn.

**Lưu ý quan trọng cho người dùng Bermuda:**
Nếu điện thoại của bạn có cả tracker từ Mobile App và Bermuda:

1. **Chỉ expose tracker của Bermuda** cho Voice Assist (để định vị phòng chính xác hơn).
2. **Đảm bảo tên thiết bị / entity ID của Bermuda trùng hoặc chứa tên thiết bị Mobile App**:
   - _Ví dụ:_ Nếu thực thể tracker của Mobile App là `device_tracker.pixel_9`, bạn đặt tên thiết bị Bermuda là `Pixel 9` hoặc `Pixel 9 BLE` (tạo ra `device_tracker.pixel_9_ble`). Blueprint sẽ tự động phát hiện `pixel_9` khớp với thiết bị di động của bạn.
   - _Tại sao?_ Việc này giúp liên kết vị trí phòng chính xác từ Bermuda với action đổ chuông `notify.mobile_app_pixel_9` của Mobile App.

### Bước 2: Tạo Shell Command lấy Alias

Lệnh này giúp hệ thống đọc được các biệt danh bạn đã đặt. Thêm đoạn sau vào `configuration.yaml`:

```yaml
shell_command:
  get_entity_alias: >-
    jq '[.data.entities[] | select(.options.conversation.should_expose == true) | {entity_id, aliases: (if has("aliases_v2") then ((if (.aliases_v2 | type) == "array" then .aliases_v2 else [] end) | map(select(. != null and . != ""))) else (if (.aliases | type) == "array" then .aliases else [] end) end)} | select(.aliases | length > 0)]' ./.storage/core.entity_registry
```

### Bước 3: Tạo Template Sensor

Sensor này lưu trữ thông tin alias để blueprint sử dụng. Thêm vào `configuration.yaml` (dưới mục `template:` hoặc gộp vào cấu hình hiện có):

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

**Sau khi thêm mã:**

1. **Khởi động lại (Restart)** Home Assistant (hoặc reload YAML cấu hình).
2. **Lưu ý:** Nếu sau này bạn thêm hoặc sửa Alias, hãy nhớ reload Template entities (Developer Tools > YAML > Template Entities) hoặc khởi động lại HA.

### Bước 4: Cài đặt Blueprints

#### 1. Blueprint Tìm vị trí (Location Lookup)

Blueprint này xử lý logic để xác định vị trí thiết bị.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevice_location_lookup_full_llm.yaml)

1. Import blueprint.
2. Tạo một **Script** từ blueprint này.
3. Trong cấu hình script, chọn **Template Sensor** (`sensor.assist_entity_ids_and_aliases`) đã tạo ở Bước 3.
4. **Giữ nguyên tên script mặc định** (`Find Device`).
5. **Khôi phục mô tả chuẩn cho LLM (Bước cực kỳ quan trọng):** Sau khi lưu script, bấm vào dấu ba chấm (`⋮`) ở góc trên bên phải, chọn **Edit in YAML**, xóa bỏ dòng `description: ...` rồi bấm **Save Script**. Thao tác này giúp script lấy lại phần mô tả gốc của blueprint, giúp LLM hiểu chính xác mục đích sử dụng kịch bản.
6. **Expose** script này cho Voice Assist.

#### 2. Blueprint Đổ chuông (Ringing)

Blueprint này cho phép Voice Assist kích hoạt thiết bị đổ chuông.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevice_ringing_full_llm.yaml)

1. Import blueprint.
2. Tạo một **Script** từ blueprint này.
3. **Giữ nguyên tên script mặc định** (`Ring Device`).
4. **Khôi phục mô tả chuẩn cho LLM (Bước cực kỳ quan trọng):** Sau khi lưu script, bấm vào dấu ba chấm (`⋮`) ở góc trên bên phải, chọn **Edit in YAML**, xóa bỏ dòng `description: ...` rồi bấm **Save Script**.
5. **Expose** script này cho Voice Assist.

## Ví dụ sử dụng

Sau khi cài đặt xong, hãy thử hỏi Voice Assist:

- "Tìm điện thoại của tôi."
- "iPhone của tôi đang ở đâu?"
- "Đồng hồ của tôi đâu rồi?"
- "Ví tiền đang ở đâu?" (với thẻ tag BLE)
- "Con chó đang ở đâu?" (với thẻ tag đeo cho thú cưng)
