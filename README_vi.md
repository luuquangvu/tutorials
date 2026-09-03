# Bộ sưu tập Blueprint và Hướng dẫn độc đáo cho Home Assistant

**[🇺🇸 English](README.md) | 🇻🇳 Tiếng Việt**

> [!TIP]
> **[Blueprints Updater](https://github.com/luuquangvu/blueprints-updater)**: Một tích hợp cực kỳ hữu ích giúp tự động cập nhật các blueprint trong bộ sưu tập này. Khi bạn cài đặt nhiều blueprint từ nhiều nguồn khác nhau, việc theo dõi cập nhật từ các tác giả trở nên khó khăn - tích hợp này sẽ giải quyết vấn đề đó cho bạn hoàn toàn tự động.

<!-- MD028/no-blanks-blockquote: Blank line inside blockquote -->

> [!NOTE]
> **Gần đây, Google đã cắt giảm đáng kể API Gemini miễn phí, khiến nó gần như không thể đáp ứng nhu cầu sử dụng của Home Assistant. Các bạn có thể tham khảo [một giải pháp thay thế hoàn toàn miễn phí tại đây](https://github.com/luuquangvu/ha-addons).**

_Tất cả blueprint trong bộ sưu tập này tương thích với hầu hết các mô hình LLM cục bộ (local) và trực tuyến (online), tuy nhiên chúng được tinh chỉnh để hoạt động tối ưu nhất với các mô hình **Gemini Flash**. Các mô hình ngôn ngữ khác có thể cần điều chỉnh nhỏ để đạt hiệu quả tương tự._

> [!IMPORTANT]
> **Bước cài đặt quan trọng:** Vui lòng tham khảo phần [Hướng dẫn Cài đặt & Thiết lập](#hướng-dẫn-cài-đặt--thiết-lập) bên dưới trước khi cấu hình blueprint. Nhiều blueprint sử dụng các thành phần phụ trợ chung như cảm biến bí danh (Entity Aliases), script hỗ trợ Pyscript hoặc cấu hình công cụ Assist để hoạt động chính xác.

Biến Home Assistant thành một trợ lý cá nhân thực thụ với bộ sưu tập blueprint và hướng dẫn chi tiết. Mọi kịch bản đều đã được kiểm chứng trong thực tế, đi kèm giải thích rõ ràng, ví dụ lệnh thoại và mẹo triển khai để bạn có thể áp dụng ngay cho ngôi nhà thông minh của mình.

---

## Mục lục

- [Bộ sưu tập Blueprint và Hướng dẫn độc đáo cho Home Assistant](#bộ-sưu-tập-blueprint-và-hướng-dẫn-độc-đáo-cho-home-assistant)
  - [Mục lục](#mục-lục)
  - [Hướng dẫn Cài đặt & Thiết lập](#hướng-dẫn-cài-đặt--thiết-lập)
    - [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung)
    - [Các Mô-đun Phụ thuộc Dùng chung](#các-mô-đun-phụ-thuộc-dùng-chung)
      - [Mô-đun 1: Cảm biến Bí danh Thực thể (Tra cứu Tên gọi Thân thiện)](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện)
      - [Mô-đun 2: Tích hợp Pyscript & Script Hỗ trợ](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ)
      - [Mô-đun 3: Các Tích hợp & Dịch vụ Chuyên biệt](#mô-đun-3-các-tích-hợp--dịch-vụ-chuyên-biệt)
    - [Bảng Tra cứu Điều kiện Tiên quyết](#bảng-tra-cứu-điều-kiện-tiên-quyết)
  - [Voice Assist - Hẹn giờ & Lên lịch Thông minh](#voice-assist---hẹn-giờ--lên-lịch-thông-minh)
  - [Voice Assist - Ghi nhớ và Truy xuất Thông tin](#voice-assist---ghi-nhớ-và-truy-xuất-thông-tin)
  - [Voice Assist - Phân tích Hình ảnh Camera](#voice-assist---phân-tích-hình-ảnh-camera)
  - [Voice Assist - Quản lý Lịch trình & Sự kiện](#voice-assist---quản-lý-lịch-trình--sự-kiện)
    - [Tạo Sự kiện Lịch](#tạo-sự-kiện-lịch)
    - [Tra cứu Sự kiện trong Lịch](#tra-cứu-sự-kiện-trong-lịch)
  - [Voice Assist - Tra cứu & Chuyển đổi Lịch Âm](#voice-assist---tra-cứu--chuyển-đổi-lịch-âm)
    - [Tra cứu & chuyển đổi Lịch Âm](#tra-cứu--chuyển-đổi-lịch-âm)
    - [Tạo Sự kiện theo Lịch Âm](#tạo-sự-kiện-theo-lịch-âm)
  - [Chatbot Tương tác & Điều khiển Nhà thông minh](#chatbot-tương-tác--điều-khiển-nhà-thông-minh)
  - [Voice Assist - Gửi Tin nhắn & Nội dung](#voice-assist---gửi-tin-nhắn--nội-dung)
  - [Voice Assist - Tra cứu Thông tin Internet](#voice-assist---tra-cứu-thông-tin-internet)
  - [Voice Assist - Tìm kiếm & Phát Video YouTube](#voice-assist---tìm-kiếm--phát-video-youtube)
  - [Voice Assist - Theo dõi Kênh YouTube Yêu thích](#voice-assist---theo-dõi-kênh-youtube-yêu-thích)
  - [Voice Assist - Điều khiển Quạt Thông minh](#voice-assist---điều-khiển-quạt-thông-minh)
  - [Voice Assist - Điều khiển Điều hòa Thông minh](#voice-assist---điều-khiển-điều-hòa-thông-minh)
  - [Voice Assist - Dự báo Thời tiết](#voice-assist---dự-báo-thời-tiết)
  - [Voice Assist - Điều khiển Nhạc](#voice-assist---điều-khiển-nhạc)
  - [Voice Assist - Định vị & Tìm kiếm Thiết bị](#voice-assist---định-vị--tìm-kiếm-thiết-bị)
  - [Đồng bộ Trạng thái Thiết bị](#đồng-bộ-trạng-thái-thiết-bị)
  - [Hướng dẫn Thêm](#hướng-dẫn-thêm)
    - [Tùy chỉnh chỉ dẫn hệ thống cho Voice Assist](#tùy-chỉnh-chỉ-dẫn-hệ-thống-cho-voice-assist)
    - [Phát video mới từ kênh YouTube yêu thích](#phát-video-mới-từ-kênh-youtube-yêu-thích)
    - [Theo dõi các thiết bị mất kết nối](#theo-dõi-các-thiết-bị-mất-kết-nối)
    - [Tự động chuyển đổi giao diện](#tự-động-chuyển-đổi-giao-diện)
    - [Hướng dẫn cài đặt tìm kiếm vị trí thiết bị](#hướng-dẫn-cài-đặt-tìm-kiếm-vị-trí-thiết-bị)

---

## Hướng dẫn Cài đặt & Thiết lập

Việc cài đặt blueprint từ kho lưu trữ này rất dễ dàng và theo một quy trình chuẩn. Vì nhiều blueprint có chung các bước chuẩn bị (như nhận diện tên gọi thân mật qua bí danh alias, script chạy qua Pyscript hoặc cấu hình công cụ cho Assist), các thiết lập dùng chung được gom thành các mô-đun bên dưới để bạn chỉ cần cấu hình một lần duy nhất cho toàn bộ hệ thống Home Assistant.

### Quy trình Cài đặt Blueprint Chung

Mọi blueprint trong kho này đều có thể cài đặt và kích hoạt qua 3 bước sau:

1. **Nhập (Import) Blueprint vào Home Assistant:**
   - Nhấn vào huy hiệu (badge) **Import Blueprint** trong từng mục để mở hộp thoại nhập trực tiếp vào Home Assistant qua [My Home Assistant](https://my.home-assistant.io/).
   - _Cách thủ công:_ Trong Home Assistant, vào **Cài đặt > Tự động hóa & Cảnh > Bản thiết kế (Blueprints) > Thêm bản thiết kế** (góc dưới bên phải), dán đường dẫn URL file `.yaml` thô từ GitHub, nhấn **Xem trước** và chọn **Nhập bản thiết kế**.

2. **Tạo Kịch bản (Script) hoặc Tự động hóa (Automation):**
   - Vào **Cài đặt > Tự động hóa & Cảnh > Bản thiết kế**, tìm blueprint vừa nhập và nhấn **Tạo kịch bản** (hoặc **Tạo tự động hóa**).
   - Điền các thông số cần thiết (chọn thực thể, cảm biến hoặc script phụ trợ).
   - Nhấn **Lưu**. **Không đổi tên mặc định của script / entity ID** nếu các blueprint hoặc script khác cần tham chiếu đến nó.

3. **Cấu hình làm công cụ cho Assist (Rất quan trọng đối với các công cụ Voice Assist):**
   - **Bộc lộ cho Assist:** Vào **Cài đặt > Trợ lý giọng nói**, đảm bảo script vừa tạo đã được bộc lộ (expose) cho Assist hoặc Conversation Agent của bạn.
   - **Khôi phục Mô tả LLM (Bước quan trọng nhất):** Khi bạn lưu script qua giao diện người dùng, Home Assistant có thể ghi đè phần mô tả chi tiết bằng một dòng ngắn chung chung. Để khôi phục:
     1. Mở script đã lưu trong Trình chỉnh sửa Kịch bản của Home Assistant.
     2. Nhấn vào dấu ba chấm (`⋮`) ở góc trên bên phải và chọn **Chỉnh sửa trong YAML**.
     3. Tìm và xóa dòng `description: ...`.
     4. Nhấn **Lưu kịch bản**. Home Assistant sẽ tự động lấy lại phần mô tả gốc đầy đủ từ blueprint, giúp các mô hình AI (như Gemini) hiểu chính xác mục đích và cách gọi công cụ.

---

### Các Mô-đun Phụ thuộc Dùng chung

Nhiều blueprint cần một hoặc nhiều thành phần cấu hình chung sau đây. Hãy thiết lập các mô-đun tương ứng với blueprint bạn muốn dùng.

#### Mô-đun 1: Cảm biến Bí danh Thực thể (Tra cứu Tên gọi Thân thiện)

Nhiều blueprint Voice Assist (như Hẹn giờ thông minh, Chụp ảnh camera, Điều khiển Quạt/Điều hòa, Phát video YouTube và Định vị thiết bị) sử dụng cơ chế tra cứu bí danh (alias) để bạn có thể gọi tên thiết bị tự nhiên (ví dụ: "quạt cây", "đèn trần", "điều hòa phòng ngủ") thay vì phải nhớ chính xác mã `entity_id`.

1. Thêm cấu hình `shell_command` và cảm biến `template` sau vào file `configuration.yaml` của bạn:

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

2. Khởi động lại Home Assistant (hoặc tải lại cấu hình YAML).
3. Đảm bảo các thiết bị bạn muốn điều khiển đã được **bộc lộ cho Assist** và có đặt bí danh (alias) trong cài đặt thực thể.

#### Mô-đun 2: Tích hợp Pyscript & Script Hỗ trợ

Các tính năng nâng cao như hẹn giờ đa thiết bị bền bỉ, bộ nhớ thông minh, tính toán lịch âm, tìm kiếm YouTube và gửi tin nhắn bot tương tác (Telegram/Zalo) sử dụng các script Python nhẹ chạy qua tích hợp **Pyscript**.

1. **Cài đặt Pyscript:**
   - Cài đặt **Pyscript Python Scripting** qua [HACS](https://hacs.xyz/).
   - Khởi động lại Home Assistant.
2. **Cấu hình Pyscript trong `configuration.yaml`:**
   - Kích hoạt quyền import thư viện và quyền truy cập biến `hass` toàn cục:

   ```yaml
   # configuration.yaml
   pyscript:
     allow_all_imports: true
     hass_is_global: true
   ```

   _Lưu ý: Nếu dùng Telegram, Zalo hoặc YouTube, thêm các token/key tương ứng bên dưới mục `pyscript:` hoặc tham chiếu qua `!secret` như hướng dẫn bên dưới._

3. **Sao chép các script cần thiết vào `config/pyscript/`:**
   - Trong thư mục `config/` của Home Assistant, tìm hoặc tạo thư mục con `pyscript/`.
   - Sao chép các file từ thư mục [`scripts/`](scripts/) trong kho lưu trữ này vào `config/pyscript/` tùy theo blueprint bạn cài:
     - [`scripts/common_utilities.py`](scripts/common_utilities.py) — Các hàm tiện ích cốt lõi (cần cho Hẹn giờ, Bộ nhớ cục bộ, Telegram, Zalo).
     - [`scripts/memory.py`](scripts/memory.py) — Bộ máy ghi nhớ (cần cho Bộ nhớ Memory Tool).
     - [`scripts/date_conversion_tool.py`](scripts/date_conversion_tool.py) — Chuyển đổi Âm - Dương lịch (cần cho Lịch âm).
     - [`scripts/telegram_bot_handle_tool.py`](scripts/telegram_bot_handle_tool.py) — Bộ xử lý bot Telegram.
     - [`scripts/zalo_bot_handle_tool.py`](scripts/zalo_bot_handle_tool.py) — Bộ xử lý bot Zalo.
     - [`scripts/youtube_data_tool.py`](scripts/youtube_data_tool.py) — Công cụ gọi YouTube Data API.
4. **Cài đặt Thư viện Phụ thuộc (Khi cần):**
   - Nếu sử dụng script Telegram, Zalo hoặc YouTube, sao chép file [`scripts/requirements.txt`](scripts/requirements.txt) vào thư mục `config/pyscript/`. Pyscript sẽ tự động tải về các gói cần thiết (`h2`, `google-api-python-client`).
5. **Tải lại Pyscript:**
   - Vào **Công cụ phát triển > YAML** và nhấn tải lại **Pyscript Python Scripting** (hoặc khởi động lại Home Assistant).

#### Mô-đun 3: Các Tích hợp & Dịch vụ Chuyên biệt

Một số blueprint yêu cầu kết nối tới các dịch vụ tích hợp sẵn hoặc API bên ngoài:

- **Thực thể AI Task (Phân tích hình ảnh):**
  - Sử dụng cho: _Phân tích nội dung file / hình ảnh_ (và ảnh chụp camera / bot tương tác nhận diện hình ảnh).
  - Vào **Cài đặt > Hệ thống > Chung** và cấu hình một mô hình tác vụ **AI Task** (ví dụ: Gemini).
- **Google Generative AI tích hợp Google Search:**
  - Sử dụng cho: _Tra cứu thông tin Internet_.
  - Yêu cầu tích hợp Google Generative AI (Gemini). Trong cài đặt Conversation Agent, bật công cụ **Google Search** và tăng giới hạn token tối đa lên ít nhất **16.384 token**.
- **Tích hợp Lịch (Quyền Đọc/Ghi):**
  - Sử dụng cho: _Tạo sự kiện lịch_, _Tạo sự kiện lịch âm_ và _Tra cứu sự kiện lịch_.
  - Đảm bảo thực thể Google Calendar hoặc Lịch cục bộ có quyền ghi để tạo sự kiện mới.
- **Music Assistant:**
  - Sử dụng cho: _Điều khiển Nhạc_.
  - Cần cài đặt và cấu hình sẵn tích hợp [Music Assistant](https://music-assistant.io/).
- **Theo dõi Vị trí Thiết bị & Thông báo:**
  - Sử dụng cho: _Định vị & Tìm kiếm thiết bị_.
  - Bộc lộ thực thể **Bermuda Device Tracker** hoặc **Home Assistant Mobile App** cho Assist. Để đổ chuông, bật quyền thông báo và cảnh báo quan trọng (Critical Alerts) trên điện thoại mục tiêu.

---

### Bảng Tra cứu Điều kiện Tiên quyết

Bảng tóm tắt nhanh các thành phần cần chuẩn bị cho từng blueprint:

| Blueprint                                                                          | Loại                   | Blueprint Đi kèm Cần thiết                                                                                          | Mô-đun Bắt buộc                                                                                                                     | Script Python & Bí mật Cần có                                                                |
| ---------------------------------------------------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| [Hẹn giờ & Lên lịch Thông minh](#voice-assist---hẹn-giờ--lên-lịch-thông-minh)      | Kịch bản + Tự động hóa | Điều khiển (Controller) + Lõi (`devices_schedules.yaml`) + Khởi động lại (`devices_schedules_restart_handler.yaml`) | [Mô-đun 1](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện), [Mô-đun 2](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ)  | `common_utilities.py`                                                                        |
| [Ghi nhớ và Truy xuất (LLM)](#voice-assist---ghi-nhớ-và-truy-xuất-thông-tin)       | Kịch bản               | Không                                                                                                               | [Mô-đun 2](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ)                                                                              | `memory.py`                                                                                  |
| [Ghi nhớ và Truy xuất (Cục bộ)](#voice-assist---ghi-nhớ-và-truy-xuất-thông-tin)    | Tự động hóa            | Không                                                                                                               | [Mô-đun 2](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ)                                                                              | `memory.py`, `common_utilities.py`                                                           |
| [Phân tích Hình ảnh Camera](#voice-assist---phân-tích-hình-ảnh-camera)             | Kịch bản               | Chụp ảnh (Snapshot) + Phân tích (`file_content_analyzer_full_llm.yaml`)                                             | [Mô-đun 1](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện), [Mô-đun 3](#mô-đun-3-các-tích-hợp--dịch-vụ-chuyên-biệt) | Thực thể AI Task, thư mục `/media`                                                           |
| [Tạo Sự kiện Lịch](#tạo-sự-kiện-lịch)                                              | Kịch bản               | Không                                                                                                               | [Mô-đun 3](#mô-đun-3-các-tích-hợp--dịch-vụ-chuyên-biệt)                                                                             | Lịch có quyền Đọc/Ghi                                                                        |
| [Tra cứu Sự kiện trong Lịch](#tra-cứu-sự-kiện-trong-lịch)                          | Kịch bản               | Không                                                                                                               | Không                                                                                                                               | Thực thể Lịch đã cấu hình                                                                    |
| [Tra cứu & Chuyển đổi Lịch Âm](#tra-cứu--chuyển-đổi-lịch-âm)                       | Kịch bản               | Không                                                                                                               | [Mô-đun 2](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ)                                                                              | `date_conversion_tool.py`                                                                    |
| [Tạo Sự kiện theo Lịch Âm](#tạo-sự-kiện-theo-lịch-âm)                              | Kịch bản               | Không                                                                                                               | [Mô-đun 2](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ), [Mô-đun 3](#mô-đun-3-các-tích-hợp--dịch-vụ-chuyên-biệt)                     | `date_conversion_tool.py`, Lịch có quyền Đọc/Ghi                                             |
| [Chatbot Tương tác (Telegram)](#chatbot-tương-tác--điều-khiển-nhà-thông-minh)      | Tự động hóa            | Tùy chọn: Phân tích (`file_content_analyzer_full_llm.yaml`)                                                         | [Mô-đun 2](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ)                                                                              | `telegram_bot_handle_tool.py`, `common_utilities.py`, `requirements.txt`, Token Bot Telegram |
| [Chatbot Tương tác (Zalo)](#chatbot-tương-tác--điều-khiển-nhà-thông-minh)          | Tự động hóa            | Tùy chọn: Phân tích (`file_content_analyzer_full_llm.yaml`)                                                         | [Mô-đun 2](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ)                                                                              | `zalo_bot_handle_tool.py`, `common_utilities.py`, `requirements.txt`, Token Bot Zalo         |
| [Gửi Tin nhắn Telegram](#voice-assist---gửi-tin-nhắn--nội-dung)                    | Kịch bản               | Không                                                                                                               | [Mô-đun 2](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ)                                                                              | `telegram_bot_handle_tool.py`, `requirements.txt`, Token Bot Telegram                        |
| [Gửi Tin nhắn Zalo](#voice-assist---gửi-tin-nhắn--nội-dung)                        | Kịch bản               | Không                                                                                                               | [Mô-đun 2](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ)                                                                              | `zalo_bot_handle_tool.py`, `requirements.txt`, Token Bot Zalo                                |
| [Tra cứu Thông tin Internet](#voice-assist---tra-cứu-thông-tin-internet)           | Kịch bản               | Không                                                                                                               | [Mô-đun 3](#mô-đun-3-các-tích-hợp--dịch-vụ-chuyên-biệt)                                                                             | Agent Gemini có Google Search & tối thiểu 16k token                                          |
| [Tìm kiếm & Phát YouTube](#voice-assist---tìm-kiếm--phát-video-youtube)            | Kịch bản               | Tìm kiếm + Phát (`play_youtube_video_full_llm.yaml`)                                                                | [Mô-đun 1](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện), [Mô-đun 2](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ)  | `youtube_data_tool.py`, `requirements.txt`, Khóa YouTube API, Ứng dụng YouTube trên TV       |
| [Theo dõi Kênh YouTube Yêu thích](#voice-assist---theo-dõi-kênh-youtube-yêu-thích) | Kịch bản               | Lấy thông tin + Phát (`play_youtube_video_full_llm.yaml`)                                                           | [Mô-đun 1](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện), [Mô-đun 2](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ)  | `youtube_data_tool.py`, `requirements.txt`, Khóa YouTube API, Ứng dụng YouTube trên TV       |
| [Điều khiển Quạt Thông minh](#voice-assist---điều-khiển-quạt-thông-minh)           | Kịch bản               | Không                                                                                                               | [Mô-đun 1](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện)                                                          | Thực thể quạt bộc lộ cho Assist                                                              |
| [Điều khiển Điều hòa Thông minh](#voice-assist---điều-khiển-điều-hòa-thông-minh)   | Kịch bản               | Không                                                                                                               | [Mô-đun 1](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện)                                                          | Thực thể điều hòa bộc lộ cho Assist                                                          |
| [Dự báo Thời tiết](#voice-assist---dự-báo-thời-tiết)                               | Kịch bản               | Không                                                                                                               | Không                                                                                                                               | Thực thể thời tiết có dự báo theo giờ & ngày                                                 |
| [Điều khiển Nhạc](#voice-assist---điều-khiển-nhạc)                                 | Kịch bản               | Không                                                                                                               | [Mô-đun 3](#mô-đun-3-các-tích-hợp--dịch-vụ-chuyên-biệt)                                                                             | Tích hợp Music Assistant                                                                     |
| [Định vị & Tìm kiếm Thiết bị](#voice-assist---định-vị--tìm-kiếm-thiết-bị)          | Kịch bản               | Tìm vị trí + Đổ chuông (`device_ringing_full_llm.yaml`)                                                             | [Mô-đun 1](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện), [Mô-đun 3](#mô-đun-3-các-tích-hợp--dịch-vụ-chuyên-biệt) | Thiết bị theo dõi Bermuda / Mobile app, Thông báo ứng dụng HA Companion                      |
| [Đồng bộ Trạng thái Thiết bị](#đồng-bộ-trạng-thái-thiết-bị)                        | Tự động hóa            | Không                                                                                                               | Không                                                                                                                               | Các thực thể công tắc / đèn điều khiển được                                                  |

---

## Voice Assist - Hẹn giờ & Lên lịch Thông minh

Bạn muốn bật điều hòa trong 30 phút rồi tự tắt? Hay muốn đèn ngủ tự động giảm độ sáng sau 1 tiếng?
Blueprint này biến Voice Assist thành một trợ lý quản lý thời gian thực thụ. Bạn có thể ra lệnh giọng nói tự nhiên để **tạo, gia hạn, tạm dừng, tiếp tục hoặc hủy** lịch trình cho bất kỳ thiết bị nào.

**Tính năng nổi bật:**

- **Hiểu ngôn ngữ tự nhiên:** Chỉ cần nói "Bật quạt 1 tiếng nữa tắt", không cần đúng cú pháp cứng nhắc.
- **Quản lý toàn diện:** Hỗ trợ đầy đủ các lệnh như tạo mới, gia hạn thêm giờ, tạm dừng lịch đang chạy hoặc hủy bỏ.
- **Bền bỉ & Tin cậy:** Mọi lịch trình đều được lưu lại và **tự động khôi phục** nếu Home Assistant khởi động lại. Bạn không lo bị mất hẹn giờ khi mất điện.
- **Điều khiển đa dạng:** Hỗ trợ hầu hết các loại thiết bị: Đèn (độ sáng, màu), Rèm (đóng/mở/vị trí), Quạt (tốc độ/tuốc năng), Điều hòa, Robot hút bụi, Media Player, v.v.
- **Nhận diện thông minh:** Tự động nhận diện thiết bị qua tên gọi thân mật (alias) mà bạn hay dùng.
- **Phản hồi chi tiết:** Khi hỏi "Có lịch nào đang chạy không?", trợ lý sẽ liệt kê rõ ràng tên thiết bị và thời gian còn lại.

**Ví dụ lệnh thoại:**

- "Bật đèn phòng khách màu vàng 50% trong 2 tiếng."
- "Mở rèm phòng ngủ 15 phút để thoáng khí rồi đóng lại."
- "Gia hạn thêm 30 phút cho quạt phòng bé."
- "Tạm dừng lịch tưới cây."
- "Có thiết bị nào đang hẹn giờ không?"

**Ứng dụng thực tế:**

- **Bảo vệ Pin:** "Sạc điện thoại 2 tiếng rồi tắt ổ cắm" - Giúp bạn sạc qua đêm mà không lo chai pin.
- **Nấu nướng rảnh tay:** "Bật hút mùi 20 phút nữa tắt" - Khi bạn kho cá xong và muốn ra ngoài đi dạo.
- **Giấc ngủ ngon:** "Bật quạt số nhỏ nhất trong 1 tiếng rồi tắt hẳn" - Tránh bị lạnh hoặc khô họng khi về sáng.

**Điều kiện tiên quyết & Cài đặt:**

- Cần cấu hình [Mô-đun 1: Cảm biến Bí danh Thực thể](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện) trong `configuration.yaml` để nhận diện tên thiết bị thân mật.
- Cần cài đặt [Mô-đun 2: Tích hợp Pyscript](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ) và đặt file [`scripts/common_utilities.py`](scripts/common_utilities.py) vào thư mục `config/pyscript/`.
- Cài đặt đủ 3 blueprint bên dưới (Script điều khiển, Script lõi và Tự động hóa khôi phục).
- Bộc lộ script Điều khiển cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung) (giữ nguyên tên mặc định, xóa dòng `description:` khi sửa YAML).

1. **Blueprint Điều khiển (LLM):** Xử lý lệnh thoại và điều phối hành động.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevices_schedules_controller_full_llm.yaml)
2. **Blueprint Lõi Lịch trình:** Chịu trách nhiệm tạo và quản lý các lịch trình.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevices_schedules.yaml)
3. **Blueprint Khôi phục:** Tự động khôi phục các lịch trình đang hoạt động khi Home Assistant khởi động lại.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevices_schedules_restart_handler.yaml)

---

## Voice Assist - Ghi nhớ và Truy xuất Thông tin

Bạn hay quên mật khẩu Wi-Fi? Hay không nhớ đã để xe ở cột nào dưới hầm? Hãy để Voice Assist làm "bộ não thứ hai" của bạn.

**Tính năng nổi bật:**

- **Ghi nhớ mọi thứ:** Từ những việc nhỏ nhặt như "Chìa khóa để ở ngăn kéo bàn" đến những nhắc nhở cần thiết như "Mã số khách hàng của cửa hàng ABC".
- **Truy xuất thông minh:** Không cần nhớ từ khóa chính xác. Chỉ cần hỏi "Xe đậu ở đâu?" hay "Pass wifi là gì?", trợ lý sẽ tự tìm thông tin liên quan nhất.
- **Phân loại linh hoạt:**
  - **Cá nhân (User):** Dành cho thông tin riêng (ví dụ: size quần áo, thực đơn ăn kiêng).
  - **Gia đình (Household):** Chia sẻ cho cả nhà (ví dụ: mật khẩu cổng, lịch đổ rác).
  - **Tạm thời (Session):** Chỉ nhớ trong lúc trò chuyện.
- **Tự động dọn dẹp:** Thiết lập thời gian tự hủy cho các ghi nhớ ngắn hạn (ví dụ: vị trí đỗ xe tại trung tâm thương mại).

**Ví dụ lệnh thoại:**

- "Ghi nhớ mật khẩu Wi-Fi khách là `khachdenchoi123`."
- "Lưu lại vị trí đỗ xe là hầm B2 cột D5, nhớ trong 1 ngày thôi."
- "Nhắc tôi số điện thoại của bác sĩ là 0912345678."
- "Tìm xem xe đang đỗ ở đâu?"
- "Mật khẩu Wi-Fi khách là gì nhỉ?"

**Ứng dụng thực tế:**

- **Truy tìm đồ thất lạc:** "Hộ chiếu cất ở đâu?" - Cứu cánh cho những lúc cần gấp mà không nhớ đã cất ở ngăn kéo nào.
- **Thông tin lắt léo:** Lưu mật khẩu Wifi dài ngoằng hoặc số tài khoản ngân hàng để khi khách hỏi là có ngay.
- **Trợ lý mua sắm:** Lưu size quần áo, giày dép của vợ/chồng/con để order online chính xác mà không cần hỏi lại.

**Điều kiện tiên quyết & Cài đặt:**

- Cần cài đặt [Mô-đun 2: Tích hợp Pyscript](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ) và đặt file [`scripts/memory.py`](scripts/memory.py) vào thư mục `config/pyscript/` (phiên bản Cục bộ cần thêm cả [`scripts/common_utilities.py`](scripts/common_utilities.py)).
- **Phiên bản LLM:** Bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung) (xóa dòng `description:` khi sửa YAML).
- **Phiên bản Cục bộ:** Cấu hình dưới dạng tự động hóa, tùy chỉnh các cụm từ kích hoạt nếu muốn.

_Tùy chọn phiên bản bạn muốn sử dụng:_

**Phiên bản LLM (Đa ngôn ngữ):**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fmemory_tool_full_llm.yaml)

**Phiên bản Local (Chỉ tiếng Anh, hoạt động offline):**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fmemory_tool_local.yaml)

---

## Voice Assist - Phân tích Hình ảnh Camera

Biến camera an ninh thành "đôi mắt" thông minh cho trợ lý ảo. Không cần mở ứng dụng soi từng góc, hãy để Voice Assist nhìn giúp bạn.

**Tính năng nổi bật:**

- **Thị giác máy tính:** Voice Assist có thể "xem" hình ảnh từ camera và mô tả chi tiết những gì đang diễn ra.
- **Quan sát toàn diện:** Hỗ trợ kết nối nhiều camera cùng lúc (cổng, sân, phòng khách...) để có cái nhìn bao quát.
- **Phản hồi tức thì:** Chụp ảnh và phân tích ngay tại thời điểm bạn hỏi.

**Ví dụ lệnh thoại:**

- "Xem camera cổng có ai đang đứng đó không?"
- "Kiểm tra xem con mèo đang ở sân trước hay sân sau?"
- "Nhìn xem cửa gara đã đóng chưa?"
- "Ngoài sân có xe lạ nào không?"

**Ứng dụng thực tế:**

- **Shipper đến:** "Xem có gói hàng nào trước cửa không?" khi bạn đang ở tầng 3 ngại chạy xuống.
- **Trị bệnh "Hay lo":** Đã lên giường đắp chăn nhưng chợt giật mình "Cổng đã đóng chưa?", chỉ cần hỏi để Assistant nhìn giúp.
- **Trông chừng "Boss":** Xem thú cưng đang ngủ ngoan hay đang đào bới ngoài vườn.

**Điều kiện tiên quyết & Cài đặt:**

- Cần cấu hình [Mô-đun 1: Cảm biến Bí danh Thực thể](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện) để nhận diện tên camera.
- Cần cấu hình thực thể tác vụ **AI Task** trong **Cài đặt > Hệ thống > Chung** (xem [Mô-đun 3](#mô-đun-3-các-tích-hợp--dịch-vụ-chuyên-biệt)).
- Đảm bảo thư mục lưu trữ ảnh tồn tại (mặc định là `/media`).
- Cài đặt cả 2 blueprint bên dưới, bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung).

1. **Blueprint Chụp ảnh:** Chụp lại hình ảnh từ camera được yêu cầu.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fcamera_snapshot_full_llm.yaml)
2. **Blueprint Phân tích (LLM):** Gửi ảnh chụp cho mô hình ngôn ngữ để phân tích và trả lời.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ffile_content_analyzer_full_llm.yaml)

---

## Voice Assist - Quản lý Lịch trình & Sự kiện

Quản lý lịch trình cá nhân của bạn bằng giọng nói một cách tự nhiên và hiệu quả.

### Tạo Sự kiện Lịch

Sắp xếp lịch trình bằng giọng nói như đang trò chuyện với trợ lý. Blueprint tự động hóa việc tạo sự kiện cho mọi lời nhắc, cuộc họp hay chuyến du lịch vào lịch của bạn.

**Tính năng nổi bật:**

- **Nhận diện ngôn ngữ tự nhiên:** Tự động phân tích ngày, giờ, và thời lượng từ câu lệnh của bạn.
- **Tạo sự kiện nhanh:** Thêm sự kiện vào lịch mà không cần nhập liệu thủ công.
- **Tích hợp liền mạch:** Hoạt động hoàn hảo với Lịch Google đã được cấu hình trong Home Assistant.

**Ví dụ lệnh thoại:**

- "Tạo lịch 2 giờ chiều mai đi cắt tóc."
- "Lên lịch 9 giờ sáng mai họp trong 3 tiếng."
- "Thêm lịch thứ bảy này về quê."

**Ứng dụng thực tế:**

- **Lên kế hoạch mọi lúc:** Nhanh chóng tạo lời nhắc, lịch hẹn khi đang lái xe, nấu ăn hoặc ngay cả khi vừa nảy ra một ý tưởng bất chợt.
- **Không bỏ lỡ:** Tự động hóa việc thêm các sự kiện quan trọng của gia đình hay công việc vào lịch mà không cần thao tác tay.

**Điều kiện tiên quyết & Cài đặt:**

- Yêu cầu thực thể Lịch có quyền Đọc/Ghi (xem [Mô-đun 3](#mô-đun-3-các-tích-hợp--dịch-vụ-chuyên-biệt)).
- Bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung) (xóa dòng `description:` khi sửa YAML).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fcreate_calendar_event_full_llm.yaml)

### Tra cứu Sự kiện trong Lịch

Hỏi và nhận thông tin về các sự kiện đã có trong lịch của bạn như sinh nhật, cuộc hẹn, ngày kỷ niệm.

**Ví dụ lệnh thoại:**

- "Tuần này có lịch gì không?"
- "Tháng này có sự kiện gì đáng chú ý không?"

**Ứng dụng thực tế:**

- **Trước khi ra khỏi nhà:** Nhanh chóng kiểm tra lịch trình trong ngày hoặc tuần mà không cần mở ứng dụng lịch trên điện thoại.
- **Xác nhận kế hoạch:** Dễ dàng kiểm tra để đảm bảo không trùng lịch hoặc bỏ lỡ các sự kiện quan trọng.

**Điều kiện tiên quyết & Cài đặt:**

- Chọn các thực thể lịch cần tra cứu trong phần cài đặt blueprint.
- Bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung) (xóa dòng `description:` khi sửa YAML).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fcalendar_events_lookup_full_llm.yaml)

---

## Voice Assist - Tra cứu & Chuyển đổi Lịch Âm

Mang văn hóa truyền thống vào ngôi nhà thông minh. Tra cứu ngày âm, xem ngày tốt xấu hay đếm ngược đến Tết ngay trên Home Assistant.

### Tra cứu & chuyển đổi Lịch Âm

Công cụ chuyển đổi lịch Âm - Dương mạnh mẽ, hoạt động hoàn toàn **Offline** (không cần internet), đảm bảo tốc độ phản hồi tức thì.

**Tính năng nổi bật:**

- **Siêu tốc & Riêng tư:** Xử lý nội bộ, không phụ thuộc vào API bên ngoài.
- **Thông tin chuyên sâu:** Cung cấp đầy đủ Can Chi (Giáp Thìn, Ất Tỵ...), Tiết khí, Giờ hoàng đạo.
- **Tư vấn ngày tốt/xấu:** Biết ngay hôm nay nên làm gì, kiêng gì theo phong tục.
- **Đếm ngược sự kiện:** Luôn biết chính xác còn bao nhiêu ngày nữa đến Tết Nguyên Đán hay các ngày lễ lớn.

**Ví dụ lệnh thoại:**

- "Hôm nay là bao nhiêu âm?"
- "Chủ nhật tuần này là ngày tốt hay xấu?"
- "Còn bao nhiêu ngày nữa đến Tết?"
- "Đổi ngày 20/11 dương lịch sang âm lịch."

**Ứng dụng thực tế:**

- **Phong thủy & Tâm linh:** Lên kế hoạch cho các công việc trọng đại (cưới hỏi, động thổ, khai trương) dựa trên ngày tốt/xấu, giờ hoàng đạo.
- **Văn hóa truyền thống:** Theo dõi các ngày rằm, mùng 1, ngày giỗ chạp để chuẩn bị đồ cúng lễ tươm tất.

**Điều kiện tiên quyết & Cài đặt:**

- Cần cài đặt [Mô-đun 2: Tích hợp Pyscript](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ) và đặt file [`scripts/date_conversion_tool.py`](scripts/date_conversion_tool.py) vào thư mục `config/pyscript/`.
- Bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung) (xóa dòng `description:` khi sửa YAML).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdate_lookup_and_conversion_full_llm.yaml)

### Tạo Sự kiện theo Lịch Âm

Tự động thêm các sự kiện quan trọng tính theo lịch Âm (giỗ, ngày kỷ niệm, cưới hỏi...) vào lịch của bạn.

**Lưu ý:** Blueprint này được thiết kế để **chạy thủ công** hoặc thông qua tự động hóa, yêu cầu người dùng điền thông tin trực tiếp qua giao diện Home Assistant. Nó **không hỗ trợ lệnh thoại** qua Voice Assist.

**Tính năng nổi bật:**

- **Chuyển đổi tự động:** Tự động tính toán và tạo sự kiện vào ngày dương lịch tương ứng hàng năm.
- **Chính xác & Tiện lợi:** Không còn phải tự quy đổi thủ công hay sợ quên các ngày lễ truyền thống.

**Ứng dụng thực tế:**

- **Nhớ ngày giỗ chạp:** Đảm bảo không bao giờ bỏ lỡ các ngày giỗ, cúng bái quan trọng của gia đình.
- **Sinh nhật âm lịch:** Tự động nhắc nhở các ngày kỷ niệm, sinh nhật tính theo lịch âm của người thân.

**Điều kiện tiên quyết & Cài đặt:**

- Cần cài đặt [Mô-đun 2: Tích hợp Pyscript](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ) và đặt file [`scripts/date_conversion_tool.py`](scripts/date_conversion_tool.py) vào thư mục `config/pyscript/`.
- Yêu cầu thực thể Lịch có quyền Đọc/Ghi (xem [Mô-đun 3](#mô-đun-3-các-tích-hợp--dịch-vụ-chuyên-biệt)).
- Chạy thủ công qua giao diện hoặc tự động hóa (không yêu cầu bộc lộ cho Assist).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fcreate_lunar_events.yaml)

---

## Chatbot Tương tác & Điều khiển Nhà thông minh

Đừng chỉ ra lệnh, hãy trò chuyện với ngôi nhà của bạn. Tạo Bot Telegram hoặc Zalo để điều khiển nhà từ xa với khả năng hiểu ngữ cảnh và phản hồi thông minh.

**Tính năng nổi bật:**

- **Hội thoại hai chiều:** Bot không chỉ nhận lệnh mà còn biết hỏi lại để làm rõ ý bạn (ví dụ: "Bạn muốn bật điều hòa phòng nào?").
- **Nhận diện hình ảnh:** Gửi ảnh một thiết bị hỏng hay một loài cây lạ, bot sẽ phân tích và trả lời bạn.
- **Điều khiển mọi lúc mọi nơi:** Tắt đèn, mở cổng hay kiểm tra camera ngay trên giao diện chat quen thuộc.

**Ứng dụng thực tế:**

- **Kiểm tra từ xa:** Đang trên đường đi làm chợt không nhớ đã tắt bếp/tắt đèn chưa? Chỉ cần nhắn tin hỏi bot.
- **Giám sát "thầm lặng":** Muốn biết con đã về nhà chưa (qua trạng thái thiết bị) mà không làm phiền? Hỏi bot thay vì gọi điện.

**Điều kiện tiên quyết & Cài đặt:**

- Cần cài đặt [Mô-đun 2: Tích hợp Pyscript](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ) với các file [`scripts/common_utilities.py`](scripts/common_utilities.py), [`scripts/requirements.txt`](scripts/requirements.txt) và bộ xử lý bot tương ứng ([`scripts/telegram_bot_handle_tool.py`](scripts/telegram_bot_handle_tool.py) hoặc [`scripts/zalo_bot_handle_tool.py`](scripts/zalo_bot_handle_tool.py)) trong thư mục `config/pyscript/`.
- Điền token của bot (`telegram_bot_token` hoặc `zalo_bot_token`) vào `configuration.yaml` và `secrets.yaml` trong mục `pyscript:`.
- **Với Telegram:** Tắt chế độ riêng tư (Privacy Mode) qua BotFather hoặc cấp quyền admin cho bot trong nhóm chat.
- **Với Phân tích Hình ảnh (Tùy chọn):** Cài đặt thêm blueprint Phân tích và cấu hình thực thể AI Task (xem [Mô-đun 3](#mô-đun-3-các-tích-hợp--dịch-vụ-chuyên-biệt)).

_Cài đặt blueprint webhook cho nền tảng bạn chọn. Để phân tích hình ảnh, cài thêm blueprint Phân tích._

**Webhook cho Telegram:**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ftelegram_bot_webhook.yaml)

**Webhook cho Zalo (Official Account):**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fzalo_bot_webhook.yaml)

**(Tùy chọn) Blueprint Phân tích Hình ảnh:**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ffile_content_analyzer_full_llm.yaml)

---

## Voice Assist - Gửi Tin nhắn & Nội dung

Đang lái xe hoặc tay dính dầu mỡ? Hãy dùng giọng nói để gửi tin nhắn và chia sẻ nội dung tới người thân qua Telegram/Zalo. Blueprint Telegram hỗ trợ tin nhắn văn bản, ghim vị trí, hình ảnh, âm thanh, tài liệu, video và tin nhắn thoại. Blueprint Zalo hỗ trợ văn bản, ghim vị trí, hình ảnh, sticker và tin nhắn thoại AAC.

**Tính năng nổi bật:**

- **Nhắn tin rảnh tay:** Đọc nội dung tin nhắn và Assistant sẽ gửi đi ngay lập tức.
- **Ghim vị trí Telegram:** Gửi vị trí chính xác bằng vĩ độ/kinh độ hoặc liên kết Google Maps có chứa tọa độ. Blueprint sẽ gửi phần tóm tắt trước, sau đó gửi ghim vị trí.
- **Chia sẻ nội dung đa phương tiện:** Gửi hình ảnh, âm thanh MP3/M4A, tài liệu, video MPEG-4 và tin nhắn thoại OGG/Opus, MP3 hoặc M4A từ đường dẫn `local/` hoặc `/media/`.
- **Nội dung Zalo:** Gửi hình ảnh từ `local/` hoặc `/media/`, sticker bằng ID Zalo, hoặc tin nhắn thoại từ URL HTTPS công khai kết thúc bằng `.aac`. Tin nhắn thoại Zalo chỉ hỗ trợ cuộc trò chuyện 1-1 và không có chú thích.
- **Báo cáo hình ảnh:** Ra lệnh chụp ảnh từ camera an ninh và gửi ngay vào nhóm chat gia đình.

**Ví dụ lệnh thoại:**

- "Gửi danh sách quán ăn ngon ở Nha Trang lên nhóm Telegram gia đình."
- "Gửi ghim vị trí Hoàng Thành Thăng Long lên nhóm Telegram bằng liên kết Google Maps này."
- "Gửi báo cáo PDF tháng này và bản ghi âm cuộc họp lên nhóm Telegram gia đình."
- "Chụp ảnh camera cổng gửi vào nhóm chat."
- "Gửi sticker Zalo có ID `your-sticker-id` vào cuộc trò chuyện Zalo của tôi."
- "Gửi tin nhắn thoại AAC này qua Zalo: `https://your-public-host.example/audio.aac`"

**Ứng dụng thực tế:**

- **An toàn khi lái xe:** "Nhắn cho vợ là anh về muộn khoảng 30 phút" - Gửi thông báo quan trọng mà không cần rời tay khỏi vô lăng, tập trung lái xe.
- **Thông báo khẩn:** Về nhà muộn? "Gửi tin nhắn cho mẹ là con đang trên đường về" - Nhanh chóng thông báo mà không cần gõ phím.
- **Chia sẻ khoảnh khắc:** "Chụp ảnh camera sân gửi vào nhóm gia đình" - Chia sẻ ngay lập tức những hình ảnh thú vị.
- **Cập nhật đầy đủ:** Gửi báo cáo, bản ghi âm, video hoặc tin nhắn thoại kèm phần tóm tắt ngắn gọn.

**Điều kiện tiên quyết & Cài đặt:**

- Cần cài đặt [Mô-đun 2: Tích hợp Pyscript](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ) với file [`scripts/requirements.txt`](scripts/requirements.txt) và bộ xử lý bot ([`scripts/telegram_bot_handle_tool.py`](scripts/telegram_bot_handle_tool.py) hoặc [`scripts/zalo_bot_handle_tool.py`](scripts/zalo_bot_handle_tool.py)) trong `config/pyscript/`.
- Điền token của bot vào `configuration.yaml` và `secrets.yaml` trong mục `pyscript:`.
- Bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung) (xóa dòng `description:` khi sửa YAML).

_Cài đặt blueprint cho nền tảng bạn muốn gửi tin đến:_

Để gửi ghim vị trí Telegram, hãy dùng tọa độ hoặc liên kết Google Maps có chứa tọa độ. Địa chỉ thuần văn bản hoặc liên kết Maps rút gọn cần có bước mã hóa địa chỉ riêng.

Để gửi nội dung qua Zalo, hãy cung cấp ID sticker từ `stickers.zaloapp.com` hoặc URL HTTPS công khai của tệp `.aac`. Tin nhắn thoại Zalo chỉ gửi được trong cuộc trò chuyện 1-1 và không hỗ trợ chú thích.

**Gửi đến Telegram:**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fsend_to_telegram_full_llm.yaml)

**Gửi đến Zalo (Official Bot):**
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fsend_to_zalo_bot_full_llm.yaml)

---

## Voice Assist - Tra cứu Thông tin Internet

Đừng để Assistant chỉ biết tắt/bật đèn. Hãy biến nó thành một cuốn bách khoa toàn thư sống, sẵn sàng giải đáp mọi thắc mắc của bạn với dữ liệu cập nhật từ Google.

**Lưu ý:** Tính năng này chỉ áp dụng cho Gemini, vì nó được tích hợp với Google Tìm kiếm để truy cập và cung cấp thông tin cập nhật.

**Tính năng nổi bật:**

- **Kiến thức vô tận:** Truy cập kho dữ liệu khổng lồ của Google để trả lời mọi câu hỏi từ lịch sử, địa lý đến tin tức thời sự.
- **Tóm tắt thông minh:** Không đọc một danh sách link dài dòng. Assistant sẽ tổng hợp và trả lời ngắn gọn, súc tích đúng trọng tâm.
- **Cập nhật realtime:** Biết được giá vàng hôm nay, kết quả bóng đá tối qua hay sự kiện đang hot trên mạng xã hội.

**Ví dụ lệnh thoại:**

- "Điểm chuẩn Đại học Bách Khoa Hà Nội năm nay là bao nhiêu?"
- "Tóm tắt diễn biến chính của trận chung kết World Cup vừa rồi."
- "Giá iPhone 17 Pro Max hiện tại là bao nhiêu?"
- "Công thức nấu món Phở bò chuẩn vị Bắc."

**Ứng dụng thực tế:**

- **Trọng tài gia đình:** Đang cãi nhau với vợ/chồng về một vấn đề gì đó? "Giá vàng hôm nay là bao nhiêu?" - Giải quyết tranh luận nhanh gọn.
- **Fact-check nhanh:** Đang nấu ăn mà quên công thức? "Công thức làm bánh flan bằng nồi cơm điện?" - Tra cứu ngay mà không cần dừng tay.
- **Tiện ích mọi lúc:** Đang lái xe hay bận tay vẫn có thể hỏi về thời tiết, tin tức, lịch sử...

**Điều kiện tiên quyết & Cài đặt:**

- Được thiết kế riêng cho Google Generative AI (Gemini).
- Yêu cầu cấu hình Conversation Agent với công cụ **Google Search** được kích hoạt và giới hạn token tối thiểu là **16.384** (xem [Mô-đun 3](#mô-đun-3-các-tích-hợp--dịch-vụ-chuyên-biệt)).
- Bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung) (xóa dòng `description:` khi sửa YAML).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fadvanced_google_search_full_llm.yaml)

---

## Voice Assist - Tìm kiếm & Phát Video YouTube

Biến TV của bạn thành rạp chiếu phim thông minh. Không cần remote, không cần gõ phím, chỉ cần nói những gì bạn muốn xem.

**Tính năng nổi bật:**

- **Hiểu ý người xem:** Tìm video theo mô tả nội dung ("nhạc thư giãn buổi sáng", "review xe VinFast") thay vì từ khóa cứng nhắc.
- **Chọn lọc thông minh:** Tự động chọn video phù hợp nhất (nhiều view, chất lượng cao) để phát.
- **Học tập & Giải trí:** Tìm video bài giảng cho con hoặc video ca nhạc cho bố mẹ chỉ trong tích tắc.

**Ví dụ lệnh thoại:**

- "Mở video nhạc không lời nhẹ nhàng để đọc sách."
- "Tìm phim tài liệu về chiến thắng Điện Biên Phủ."
- "Xem review iPhone 17 Pro Max mới nhất."

**Ứng dụng thực tế:**

- **Dỗ trẻ:** "Mở Baby Shark" ngay lập tức để dỗ bé đang khóc mà không cần tìm remote.
- **Thân thiện với người lớn tuổi:** Ông bà muốn nghe Cải lương/Chèo nhưng mắt kém ngại gõ phím tìm kiếm, chỉ cần nói là có.
- **Tập trung làm việc:** "Mở nhạc Lofi Chill" để tạo không gian làm việc mà không cần thao tác trên máy tính.

**Điều kiện tiên quyết & Cài đặt:**

- Cần cấu hình [Mô-đun 1: Cảm biến Bí danh Thực thể](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện) để nhận diện tên TV / media player.
- Cần cài đặt [Mô-đun 2: Tích hợp Pyscript](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ) với các file [`scripts/youtube_data_tool.py`](scripts/youtube_data_tool.py) và [`scripts/requirements.txt`](scripts/requirements.txt) đặt trong `config/pyscript/`.
- Cấu hình khóa `youtube_api_key` trong `configuration.yaml` và `secrets.yaml` ở mục `pyscript:`.
- TV hoặc thiết bị phát mục tiêu cần cài đặt ứng dụng YouTube chính thức.
- Cài đặt cả 2 blueprint bên dưới, bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung).

1. **Blueprint Tìm kiếm (LLM):** Phân tích câu hỏi và tìm kiếm video phù hợp.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fadvanced_youtube_search_full_llm.yaml)
2. **Blueprint Phát video:** Lấy thông tin video và phát trên media player.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fplay_youtube_video_full_llm.yaml)

---

## Voice Assist - Theo dõi Kênh YouTube Yêu thích

Bạn là fan cứng của "Trực Tiếp Game" hay "MixiGaming"? Blueprint này giúp bạn không bao giờ bỏ lỡ video mới nhất từ các idol.

**Tính năng nổi bật:**

- **Cập nhật liên tục:** Tự động kiểm tra các kênh bạn theo dõi.
- **Phát ngay lập tức:** Lệnh "Có video mới không?" sẽ tự động phát video vừa ra lò lên TV.
- **Thông báo chủ động:** Nhận tin nhắn ngay khi kênh yêu thích đăng tải nội dung mới.

**Ví dụ lệnh thoại:**

- "Kênh Khoai Lang Thang có gì mới không?"
- "Mở video mới nhất của HOA BAN FOOD"

**Ứng dụng thực tế:**

- **Không bỏ lỡ idol:** Tự động thông báo khi kênh YouTube yêu thích của bạn (streamer, vlogger...) đăng tải video mới, không cần phải kiểm tra thủ công.
- **Giải trí theo gu:** Vừa thức dậy đã có thể nói "Kênh VTV Thời sự có gì mới không?" để cập nhật tin tức hoặc "Mở video mới nhất của FAPTV" để thư giãn.

[**Xem hướng dẫn chi tiết**](/home_assistant_play_favorite_youtube_channel_videos_vi.md)

**Điều kiện tiên quyết & Cài đặt:**

- Cần cấu hình [Mô-đun 1: Cảm biến Bí danh Thực thể](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện) để nhận diện tên TV / media player.
- Cần cài đặt [Mô-đun 2: Tích hợp Pyscript](#mô-đun-2-tích-hợp-pyscript--script-hỗ-trợ) với các file [`scripts/youtube_data_tool.py`](scripts/youtube_data_tool.py) và [`scripts/requirements.txt`](scripts/requirements.txt) đặt trong `config/pyscript/`.
- Cấu hình khóa `youtube_api_key` trong `configuration.yaml` và `secrets.yaml` ở mục `pyscript:`.
- TV hoặc thiết bị phát mục tiêu cần cài đặt ứng dụng YouTube chính thức.
- Cài đặt cả 2 blueprint bên dưới, bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung).

1. **Blueprint Lấy thông tin (LLM):** Kiểm tra kênh và lấy thông tin video mới nhất.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fget_youtube_video_info_full_llm.yaml)
2. **Blueprint Phát video:** Lấy thông tin video và phát trên media player (có thể tái sử dụng từ blueprint ở trên).
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fplay_youtube_video_full_llm.yaml)

---

## Voice Assist - Điều khiển Quạt Thông minh

Nóng quá? Chỉ cần than thở một câu, quạt sẽ tự tăng tốc. Blueprint này là phiên bản nâng cấp toàn diện, kết hợp điều khiển tốc độ và tuốc năng (quay) trong một công cụ duy nhất.

**Tại sao nên dùng Blueprint này thay vì tính năng có sẵn (Built-in HassFanSetSpeed)?**

Mặc dù Home Assistant đã hỗ trợ điều khiển quạt cơ bản, nhưng blueprint này mang lại trải nghiệm tự nhiên và mạnh mẽ hơn:

- **Kết hợp 2 trong 1:** Điều khiển cả tốc độ và chế độ quay (oscillation) trong cùng một câu lệnh, điều mà công cụ mặc định chưa làm được.
- **Điều chỉnh tương đối:** Hỗ trợ các lệnh "tăng số", "giảm số" thay vì chỉ cài đặt mức cố định.
- **Nhận diện thông minh:** Tích hợp tra cứu alias nâng cao, giúp bạn gọi tên quạt theo ý thích (ví dụ "Quạt cây", "Quạt trần") mà không cần đổi tên entity gốc.

**Tính năng nổi bật:**

- **Điều chỉnh linh hoạt:** Tăng/giảm tốc độ theo phần trăm, bước nhảy tùy chỉnh hoặc mức độ mong muốn.
- **Kiểm soát toàn diện:** Bật/tắt tuốc năng và chỉnh gió cùng lúc.
- **Đồng bộ:** Ra lệnh cho một quạt cụ thể hoặc tất cả quạt trong nhà.

**Ví dụ lệnh thoại:**

- "Tăng quạt phòng khách lên mạnh nhất và cho quay đi."
- "Giảm tốc độ quạt trần xuống một chút."
- "Bật tuốc năng cho tất cả quạt."
- "Đặt quạt bàn mức 50%."

**Ứng dụng thực tế:**

- **Thoải mái trên giường/sofa:** Điều chỉnh gió cho phù hợp với nhiệt độ phòng mà không cần rời khỏi vị trí thoải mái.
- **Tạo "gió thoảng" nhanh:** Thiết lập nhanh chế độ "gió thoảng" (tốc độ thấp và quay) cho phòng ngủ khi đi ngủ.

**Điều kiện tiên quyết & Cài đặt:**

- Cần cấu hình [Mô-đun 1: Cảm biến Bí danh Thực thể](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện) trong `configuration.yaml`.
- Bộc lộ các thực thể quạt cho Assist kèm bí danh (alias) mong muốn.
- Bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung) (xóa dòng `description:` khi sửa YAML).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Ffan_speed_and_oscillation_control_full_llm.yaml)

---

## Voice Assist - Điều khiển Điều hòa Thông minh

Giữ không khí trong lành và nhiệt độ lý tưởng trong nhà chỉ bằng giọng nói. Blueprint này giúp bạn kiểm soát máy điều hòa một cách toàn diện, từ chế độ hoạt động, nhiệt độ đến tốc độ quạt.

**Tại sao nên dùng Blueprint này thay vì tính năng có sẵn (Built-in)?**

Các action mặc định của Home Assistant (`HassClimateSetTemperature`, `HassTurnOn/Off`) thường chỉ tập trung vào việc bật/tắt hoặc chỉnh nhiệt độ. Chúng **không hỗ trợ chỉnh tốc độ gió (fan speed)** và rất hạn chế trong việc chuyển đổi linh hoạt giữa các chế độ (Cool, Dry, Heat...) trong cùng một câu lệnh.

Blueprint này giải quyết triệt để các hạn chế đó:

- **Điều khiển Toàn diện (Mode + Fan + Temp):** Bạn có thể ra lệnh trọn gói: _"Bật máy lạnh 24 độ, chế độ mát, gió to nhất"_ và hệ thống sẽ thực hiện chính xác chỉ trong **một lần xử lý**.
- **Logic thông minh:**
  - **Tự động làm tròn:** Nếu máy chỉ hỗ trợ tăng giảm 1 độ nhưng bạn lỡ nói "24.5 độ", script sẽ tự làm tròn thay vì báo lỗi.
  - **Xử lý đơn vị:** Tự động nhận diện và xử lý khi người dùng nói độ F (Fahrenheit) cho máy dùng độ C (Celsius) và ngược lại, đảm bảo an toàn với các giới hạn min/max.
  - **Kiểm tra trước khi lệnh:** Tự động kiểm tra xem nhiệt độ có nằm trong ngưỡng cho phép (min/max) của thiết bị không trước khi gửi lệnh.
- **Hỗ trợ Alias:** Tìm kiếm thiết bị chính xác qua tên gọi tắt (alias) mà bạn tự định nghĩa, hoạt động tốt hơn cơ chế mặc định trong các tình huống phức tạp.

**Tính năng nổi bật:**

- **Kiểm soát chế độ:** Chuyển đổi giữa các chế độ làm mát, sưởi ấm, hút ẩm, chỉ quạt hoặc tự động.
- **Điều chỉnh nhiệt độ:** Cài đặt nhiệt độ chính xác với các cơ chế bảo vệ thông minh.
- **Điều chỉnh tốc độ quạt:** Thiết lập tốc độ quạt linh hoạt (thấp, trung, cao, tự động...).
- **Xử lý nhiều thiết bị:** Điều khiển một hoặc nhiều điều hòa cùng lúc.

**Ví dụ lệnh thoại:**

- "Bật điều hòa phòng khách 24 độ và gió mạnh nhất."
- "Chuyển điều hòa phòng ngủ sang chế độ hút ẩm."
- "Tăng nhiệt độ điều hòa hành lang lên 26 độ."
- "Tắt tất cả điều hòa."

**Ứng dụng thực tế:**

- **Chế độ "Đêm khuya":** Khi đang ngủ mà cảm thấy quá lạnh hoặc quá nóng, bạn chỉ cần nói buông quơ để điều chỉnh mà không cần mở mắt tìm remote hay bị lóa mắt bởi màn hình điện thoại.
- **Thân thiện với người lớn tuổi & trẻ nhỏ:** Thay vì phải nhớ các biểu tượng rắc rối trên remote (bông tuyết, giọt nước, hình mặt trời...), người nhà chỉ cần ra lệnh bằng tiếng Việt tự nhiên: _"Bật chế độ hút ẩm"_.
- **Rảnh tay tuyệt đối:** Vừa đi làm về, tay xách nách mang, chỉ cần nói một câu: _"Bật máy lạnh 20 độ gió to nhất"_ để tận hưởng không khí mát lạnh ngay lập tức mà không cần thao tác thủ công.

**Điều kiện tiên quyết & Cài đặt:**

- Yêu cầu điều hòa thông minh (thực thể climate) đã tích hợp trong Home Assistant.
- Cần cấu hình [Mô-đun 1: Cảm biến Bí danh Thực thể](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện) trong `configuration.yaml`.
- Bộc lộ các thực thể điều hòa cho Assist kèm bí danh (alias) mong muốn.
- Bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung) (xóa dòng `description:` khi sửa YAML).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fac_mode_and_fan_control_full_llm.yaml)

---

## Voice Assist - Dự báo Thời tiết

Tra cứu dự báo thời tiết tại nhà cho các khoảng thời gian cụ thể (theo giờ hoặc theo ngày) bằng giọng nói.

**Tính năng nổi bật:**

- **Thông tin chi tiết:** Hỗ trợ dự báo theo giờ (hourly) hoặc theo ngày (daily).
- **Linh hoạt:** Hỏi về thời tiết hôm nay, ngày mai, cuối tuần, hoặc một thời điểm cụ thể như "chiều nay", "tối mai".
- **Tính toán trung bình:** Tự động tổng hợp dữ liệu để trả lời ngắn gọn (ví dụ: nhiệt độ trung bình, tình trạng phổ biến nhất).

**Ví dụ lệnh thoại:**

- "Thời tiết hôm nay thế nào?"
- "Chiều nay có mưa không?"
- "Dự báo thời tiết cuối tuần này."

**Credit:**

- Gửi lời cảm ơn đặc biệt đến blueprint gốc từ [TheFes/ha-blueprints](https://github.com/TheFes/ha-blueprints). Phiên bản này đã được tinh chỉnh và tối ưu hóa riêng cho Gemini.

**Điều kiện tiên quyết & Cài đặt:**

- Cấu hình thực thể thời tiết hỗ trợ cả dự báo theo giờ và theo ngày trong các tham số blueprint.
- Bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung) (xóa dòng `description:` khi sửa YAML).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fweather_forecast_full_llm.yaml)

---

## Voice Assist - Điều khiển Nhạc

Điều khiển âm nhạc qua Music Assistant bằng giọng nói. Hỗ trợ tìm kiếm theo bài hát, album, nghệ sĩ, danh sách phát và radio.

**Tính năng nổi bật:**

- **Tìm kiếm thông minh:** Tìm và phát chính xác nội dung bạn yêu cầu.
- **Hỗ trợ đa dạng:** Làm việc với track, album, artist, playlist và radio.
- **Tùy chỉnh linh hoạt:** Hỗ trợ chọn khu vực phát (area), thiết bị phát (player) và chế độ trộn bài (shuffle).

**Ví dụ lệnh thoại:**

- "Phát nhạc của Sơn Tùng M-TP ở phòng khách."
- "Bật playlist Nhạc Trẻ Remix và cho trộn bài."
- "Phát bài hát Lối Nhỏ."

**Credit:**

- Gửi lời cảm ơn đặc biệt đến blueprint gốc từ [music-assistant/voice-support](https://github.com/music-assistant/voice-support). Phiên bản này đã được tinh chỉnh và tối ưu hóa riêng cho Gemini.

**Điều kiện tiên quyết & Cài đặt:**

- Yêu cầu tích hợp **Music Assistant** đã được cấu hình trong Home Assistant (xem [Mô-đun 3](#mô-đun-3-các-tích-hợp--dịch-vụ-chuyên-biệt)).
- Bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung) (xóa dòng `description:` khi sửa YAML).

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fcontrol_music_full_llm.yaml)

---

## Voice Assist - Định vị & Tìm kiếm Thiết bị

"Điện thoại mình đâu rồi?" - Câu hỏi kinh điển mỗi sáng. Hãy để Assistant giúp bạn tìm nó ngay lập tức.

**Tính năng nổi bật:**

- **Định vị trong nhà:** Cho biết điện thoại đang ở phòng nào (dựa trên sóng Bluetooth/Wi-Fi).
- **Kích hoạt chuông:** Bắt điện thoại đổ chuông ầm ĩ kể cả khi đang để chế độ im lặng.
- **Hỗ trợ đa thiết bị:** Tìm iPhone, Android, iPad hay bất kỳ thiết bị nào có cài app Home Assistant.

**Ví dụ lệnh thoại:**

- "Tìm xem điện thoại của bố đang ở đâu?"
- "Làm cho cái iPad đổ chuông đi, mình tìm không thấy."

**Ứng dụng thực tế:**

- **Ác mộng "Chế độ im lặng":** Điện thoại rơi đâu đó trong khe sofa mà lại đang tắt chuông? Assistant sẽ bắt nó đổ chuông ầm ĩ ngay lập tức.
- **Vội đi làm:** Sáng ra muộn giờ mà không thấy chìa khóa xe hay điện thoại đâu, chỉ cần hỏi để định vị phòng nào.

[**Xem hướng dẫn chi tiết**](/home_assistant_device_location_lookup_guide_vi.md)

**Điều kiện tiên quyết & Cài đặt:**

- Cần cấu hình [Mô-đun 1: Cảm biến Bí danh Thực thể](#mô-đun-1-cảm-biến-bí-danh-thực-thể-tra-cứu-tên-gọi-thân-thiện) để nhận diện tên thiết bị.
- Bộc lộ thực thể Bermuda Device Tracker hoặc Mobile App Device Tracker cho Assist (mỗi thiết bị vật lý chỉ gán một bộ theo dõi; xem [hướng dẫn chi tiết](/home_assistant_device_location_lookup_guide_vi.md)).
- Với tính năng đổ chuông: Thiết bị di động mục tiêu cần cài ứng dụng Home Assistant Companion và cấp quyền thông báo (bật Critical Alerts trên iOS).
- Cài đặt cả 2 blueprint bên dưới, bộc lộ script cho Assist và làm theo [Quy trình Cài đặt Blueprint Chung](#quy-trình-cài-đặt-blueprint-chung).

1. **Blueprint Tìm vị trí (LLM):** Xử lý yêu cầu và tìm vị trí thiết bị.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevice_location_lookup_full_llm.yaml)
2. **Blueprint Đổ chuông (LLM):** Kích hoạt thiết bị đổ chuông.
   [![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Fdevice_ringing_full_llm.yaml)

---

## Đồng bộ Trạng thái Thiết bị

Đồng bộ trạng thái `on/off` giữa nhiều thiết bị, hoạt động tương tự như một công tắc cầu thang hai chiều ảo.

**Ứng dụng thực tế:**

- **Nhà cũ dùng công tắc thông minh:** Bật/tắt đèn ở cầu thang hoặc hành lang linh hoạt từ nhiều công tắc, kể cả công tắc cơ hoặc không dây.
- **Ánh sáng theo nhóm:** Bật một công tắc vật lý sẽ kích hoạt toàn bộ đèn trong khu vực (đèn trần, đèn hắt, đèn trang trí) cùng lúc, tạo không gian ngay lập tức.

**Điều kiện tiên quyết & Cài đặt:**

- Các thực thể mục tiêu phải hỗ trợ `homeassistant.turn_on` và `homeassistant.turn_off`.
- Blueprint tự động hóa tiêu chuẩn; chỉ cần chọn các thực thể liên kết trên giao diện và lưu lại.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fluuquangvu%2Ftutorials%2Fblob%2Fmain%2Flink_multiple_devices.yaml)

---

## Hướng dẫn Thêm

### [Tùy chỉnh chỉ dẫn hệ thống cho Voice Assist](/home_assistant_voice_instructions_vi.md)

### [Phát video mới từ kênh YouTube yêu thích](/home_assistant_play_favorite_youtube_channel_videos_vi.md)

### [Theo dõi các thiết bị mất kết nối](/home_assistant_unavailable_devices_vi.md)

### [Tự động chuyển đổi giao diện](/home_assistant_ios_themes_vi.md)

### [Hướng dẫn cài đặt tìm kiếm vị trí thiết bị](/home_assistant_device_location_lookup_guide_vi.md)

---

**Nếu bạn thấy bộ sưu tập này hữu ích, đừng ngần ngại chia sẻ với cộng đồng Home Assistant nhé! Hãy theo dõi để cập nhật thêm nhiều blueprint độc đáo khác trong tương lai!**
