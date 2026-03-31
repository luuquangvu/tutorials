# Hướng dẫn chi tiết cài đặt Voice Assist phát video Youtube lên Smart TV

Hướng dẫn này cho phép bạn sử dụng Home Assistant Voice để phát các video mới nhất từ các kênh YouTube yêu thích lên Smart TV của mình.

## Giới thiệu & Tính năng chính

- **Mục đích:** Tự động phát video mới ra mắt gần đây từ một kênh YouTube bất kỳ mà bạn yêu thích.
- **Hỗ trợ LLM:** Chỉ hoạt động với các LLM như Google hoặc OpenAI.
- **Hỗ trợ Alias:** Bạn có thể tạo nhiều biệt danh (alias) cho tên kênh để dễ gọi tên hơn.

### Hạn chế

- Không hỗ trợ tìm kiếm các video cũ từ một kênh.
- Không hỗ trợ tìm kiếm một video bất kỳ trong toàn bộ YouTube (chỉ tìm video mới nhất của kênh đã theo dõi).
- Yêu cầu cần có một Smart TV hoặc thiết bị media player đã tích hợp vào Home Assistant.

![image](images/20250528_210348.jpg)

## Bước 1: Lấy thông tin video từ các kênh YouTube yêu thích

### 1.1. Cài đặt tích hợp Feedparser

Feedparser là một integration giúp Home Assistant đọc các nguồn cấp dữ liệu RSS/Atom, bao gồm cả feed video của YouTube.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=custom-components&repository=feedparser&category=Integration)

- Xem chi tiết tại: [github.com/custom-components/feedparser](https://github.com/custom-components/feedparser)
- _Lưu ý:_ Tính đến thời điểm `2025-12-10`, tích hợp Feedparser vẫn chưa hỗ trợ `unique_id` một cách đầy đủ để tạo alias dễ dàng qua giao diện. Bạn có thể theo dõi tiến độ tại [pull request này](https://github.com/custom-components/feedparser/pull/143) hoặc tự sửa mã nếu muốn có tính năng này.
- Sau khi cài đặt xong qua HACS, cần **khởi động lại** Home Assistant.

### 1.2. Lấy ID kênh YouTube

Bạn cần ID của kênh YouTube để cấu hình sensor.

1.  Mở Google và tìm kiếm `Get YouTube Channel ID`.
2.  Truy cập một trang bất kỳ (ví dụ: `https://commentpicker.com/youtube-channel-id.php`).
3.  Nhập đường dẫn (URL) của kênh YouTube bạn muốn theo dõi để lấy ID.

![image](images/20250527_FdZbGj.png)

### 1.3. Cấu hình Sensor cho kênh YouTube

Sau khi có ID kênh, thêm cấu hình sensor vào file `config/configuration.yaml`:

```yaml
sensor:
  - platform: feedparser
    name: CHANNEL_NAME YouTube Channel # Đổi CHANNEL_NAME thành tên kênh mong muốn
    feed_url: https://www.youtube.com/feeds/videos.xml?channel_id=XXXXXX # Thay XXXXXX bằng ID kênh vừa lấy
    scan_interval:
      minutes: 30 # Tần suất kiểm tra video mới (mặc định 30 phút)
    inclusions:
      - title
      - link
      - author
      - published
      - media_thumbnail
      - yt_videoid
    date_format: "%Y-%m-%dT%H:%M:%S%z"
```

- **Lưu ý:** Cụm từ "YouTube Channel" trong tên sensor là cố định và quan trọng để LLM nhận diện.
- _Ví dụ cấu hình cho kênh Hoa Ban Food:_

```yaml
sensor:
  - platform: feedparser
    name: Hoa Ban Food YouTube Channel
    feed_url: https://www.youtube.com/feeds/videos.xml?channel_id=UCBhgBmuPFbLLxnejr09lnAQ
    scan_interval:
      minutes: 30
    inclusions:
      - title
      - link
      - author
      - published
      - media_thumbnail
      - yt_videoid
    date_format: "%Y-%m-%dT%H:%M:%S%z"
```

- Lặp lại các bước trên cho tất cả các kênh YouTube bạn muốn theo dõi.
- Sau khi cấu hình xong, **khởi động lại** Home Assistant.

### 1.4. Chia sẻ Sensor với Assist và tạo Alias

Để Voice Assist có thể nhận diện và tương tác với các kênh YouTube của bạn:

1.  Sau khi khởi động lại HA, vào **Settings** > **Voice assistants** > **Expose**.
2.  Tìm và expose các sensor kênh YouTube mới tạo.

![image](images/20250527_gCfAcK.png)

3.  Tạo thêm các **Alias** cho các kênh (ví dụ: "Hoa Ban", "Sơn Tùng") để dễ nhớ hoặc dễ phát âm bằng giọng nói, đặc biệt là với kênh nước ngoài.

![image](images/20250604_VhChze.png)

### 1.5. Cấu hình hỗ trợ Alias cho Assist

Để Assist hiểu được các Alias bạn đã tạo, chúng ta cần một `shell_command` và một `template sensor` chung.

**Thêm vào `configuration.yaml`:**
(Đảm bảo `jq` đã được cài đặt trên hệ thống Home Assistant của bạn)

```yaml
shell_command:
  get_entity_alias: jq '[.data.entities[] | select(.options.conversation.should_expose == true and (.aliases | length > 0)) | {entity_id, aliases}]' ./.storage/core.entity_registry
```

**Thêm vào `configuration.yaml` (dưới mục `template:` hoặc gộp vào cấu hình hiện có):**

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

- Sau khi thêm xong, **khởi động lại** Home Assistant.
- **Lưu ý:** Mỗi khi bạn thay đổi Alias, bạn cần **reload template entities** (từ Developer Tools > YAML) hoặc khởi động lại HA để cập nhật.

## Bước 2: Thêm Kịch bản (Script) cho Assist

### 2.1. Cài đặt Blueprint Get Video Info

Blueprint này giúp Assist lấy thông tin video mới nhất từ kênh YouTube được yêu cầu.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fget_youtube_video_info_full_llm.yaml)

- **Bước làm:**
  1.  Import blueprint.
  2.  Tạo một **Script** mới từ blueprint này.
  3.  Chỉ định Template Sensor (`sensor.assist_entity_ids_and_aliases`) đã tạo ở bước 1.5.
  4.  **Quan trọng:** Giữ nguyên tên Script mặc định.
  5.  Sau khi tạo xong, **Expose** script đó cho Voice Assist.

### 2.2. Cài đặt Blueprint Play Video

Blueprint này có nhiệm vụ phát video đã tìm được lên thiết bị media player của bạn.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fplay_youtube_video_full_llm.yaml)

- **Bước làm:**
  1.  Import blueprint.
  2.  Tạo một **Script** mới từ blueprint này.
  3.  Chỉ định một Smart TV hoặc thiết bị media player sẽ phát video lên.
  4.  **Quan trọng:** Giữ nguyên tên Script mặc định.

![image](images/20250527_JC5AOg.png)

- Sau khi tạo xong, **Expose** script đó cho Voice Assist.

## 3. Ví dụ lệnh thoại

Vậy là xong! Bây giờ bạn có thể thử với một số mẫu câu lệnh sau, hoặc biến tấu theo ý muốn:

- "Hôm nay có video YouTube nào mới không?" -> (Assist trả lời) -> "Mở video XXX nhé" (XXX là một phần nhỏ trong tiêu đề của video).
- "Gần đây [Tên Kênh] có video nào mới không? Hãy phát nó lên TV ngay bây giờ."
- "Tuần này [Tên Kênh 1] và [Tên Kênh 2] có video mới không?" -> (Assist trả lời) -> "Mở video XXX nhé."
- "Tháng này [Tên Kênh 1] hay [Tên Kênh 2] có video nào mới không? Hãy phát nó lên TV ngay bây giờ."

---

**Nếu bạn thấy tính năng này hữu ích, hãy theo dõi để đón chờ thêm những tính năng mới hay ho hơn nữa nhé!**
