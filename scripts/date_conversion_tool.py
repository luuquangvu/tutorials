"""
Download from: https://www.informatik.uni-leipzig.de/~duc/amlich/AL.py

(c) 2006 Ho Ngoc Duc.
Astronomical algorithms
from the book "Astronomical Algorithms" by Jean Meeus, 1998
"""

import datetime
import math
from typing import Any


@pyscript_compile  # noqa: F821
def jd_from_date(dd: int, mm: int, yy: int) -> int:
    """Compute the Julian day number for a given Gregorian date."""
    a = int((14 - mm) / 12.0)
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    jd = (
        dd
        + int((153 * m + 2) / 5.0)
        + 365 * y
        + int(y / 4.0)
        - int(y / 100.0)
        + int(y / 400.0)
        - 32045
    )
    if jd < 2299161:
        jd = dd + int((153 * m + 2) / 5.0) + 365 * y + int(y / 4.0) - 32083
    return jd


@pyscript_compile  # noqa: F821
def jd_to_date(jd: int) -> list[int]:
    """Convert a Julian day number to a Gregorian date [day, month, year]."""
    if jd > 2299160:
        a = jd + 32044
        b = int((4 * a + 3) / 146097.0)
        c = a - int((b * 146097) / 4.0)
    else:
        b = 0
        c = jd + 32082

    d = int((4 * c + 3) / 1461.0)
    e = c - int((1461 * d) / 4.0)
    m = int((5 * e + 2) / 153.0)
    day = e - int((153 * m + 2) / 5.0) + 1
    month = m + 3 - 12 * int(m / 10.0)
    year = b * 100 + d - 4800 + int(m / 10.0)
    return [day, month, year]


@pyscript_compile  # noqa: F821
def new_moon(k: int) -> float:
    """Compute the Julian date of the k-th new moon since 1900-01-01."""
    t = k / 1236.85
    t2 = t * t
    t3 = t2 * t
    dr = math.pi / 180.0
    jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * t2 - 0.000000155 * t3
    jd1 = jd1 + 0.00033 * math.sin((166.56 + 132.87 * t - 0.009173 * t2) * dr)
    m = 359.2242 + 29.10535608 * k - 0.0000333 * t2 - 0.00000347 * t3
    mpr = 306.0253 + 385.81691806 * k + 0.0107306 * t2 + 0.00001236 * t3
    f = 21.2964 + 390.67050646 * k - 0.0016528 * t2 - 0.00000239 * t3
    c1 = (0.1734 - 0.000393 * t) * math.sin(m * dr) + 0.0021 * math.sin(2 * dr * m)
    c1 = c1 - 0.4068 * math.sin(mpr * dr) + 0.0161 * math.sin(dr * 2 * mpr)
    c1 = c1 - 0.0004 * math.sin(dr * 3 * mpr)
    c1 = c1 + 0.0104 * math.sin(dr * 2 * f) - 0.0051 * math.sin(dr * (m + mpr))
    c1 = c1 - 0.0074 * math.sin(dr * (m - mpr)) + 0.0004 * math.sin(dr * (2 * f + m))
    c1 = (
        c1 - 0.0004 * math.sin(dr * (2 * f - m)) - 0.0006 * math.sin(dr * (2 * f + mpr))
    )
    c1 = (
        c1
        + 0.0010 * math.sin(dr * (2 * f - mpr))
        + 0.0005 * math.sin(dr * (2 * mpr + m))
    )
    if t < -11:
        deltat = (
            0.001
            + 0.000839 * t
            + 0.0002261 * t2
            - 0.00000845 * t3
            - 0.000000081 * t * t3
        )
    else:
        deltat = -0.000278 + 0.000265 * t + 0.000262 * t2
    jd_new = jd1 + c1 - deltat
    return jd_new


@pyscript_compile  # noqa: F821
def sun_longitude(jdn: float) -> float:
    """Compute the true longitude of the sun for a given Julian date."""
    t = (jdn - 2451545.0) / 36525.0
    t2 = t * t
    dr = math.pi / 180.0
    m = 357.52910 + 35999.05030 * t - 0.0001559 * t2 - 0.00000048 * t * t2
    l0 = 280.46645 + 36000.76983 * t + 0.0003032 * t2
    dl = (1.914600 - 0.004817 * t - 0.000014 * t2) * math.sin(dr * m)
    dl += (0.019993 - 0.000101 * t) * math.sin(dr * 2 * m) + 0.000290 * math.sin(
        dr * 3 * m
    )
    longitude = l0 + dl
    longitude = longitude * dr
    longitude = longitude - math.pi * 2 * (int(longitude / (math.pi * 2)))
    return longitude


@pyscript_compile  # noqa: F821
def get_sun_longitude(day_number: int, time_zone: int) -> int:
    """Compute the solar term index (0-11) for midnight of a given Julian day."""
    return int(sun_longitude(day_number - 0.5 - time_zone / 24.0) / math.pi * 6)


@pyscript_compile  # noqa: F821
def get_new_moon_day(k: int, time_zone: int) -> int:
    """Compute the Julian day of the k-th new moon for a specific time zone."""
    return int(new_moon(k) + 0.5 + time_zone / 24.0)


@pyscript_compile  # noqa: F821
def get_lunar_month_11(yy: int, time_zone: int) -> int:
    """Find the start of the 11th lunar month for a given Gregorian year."""
    off = jd_from_date(31, 12, yy) - 2415021.0
    k = int(off / 29.530588853)
    nm = get_new_moon_day(k, time_zone)
    sun_long = get_sun_longitude(nm, time_zone)
    if sun_long >= 9:
        nm = get_new_moon_day(k - 1, time_zone)
    return nm


@pyscript_compile  # noqa: F821
def get_leap_month_offset(a11: int, time_zone: int) -> int:
    """Calculate the index of the leap month following the 11th lunar month."""
    k = int((a11 - 2415021.076998695) / 29.530588853 + 0.5)
    i = 1
    arc = get_sun_longitude(get_new_moon_day(k + i, time_zone), time_zone)
    while True:
        last = arc
        i += 1
        arc = get_sun_longitude(get_new_moon_day(k + i, time_zone), time_zone)
        if not (arc != last and i < 14):
            break
    return i - 1


@pyscript_compile  # noqa: F821
def solar_to_lunar(dd: int, mm: int, yy: int, time_zone: int = 7) -> list[int]:
    """Convert a Gregorian (Solar) date to its corresponding Lunar date."""
    day_number = jd_from_date(dd, mm, yy)
    k = int((day_number - 2415021.076998695) / 29.530588853)
    month_start = get_new_moon_day(k + 1, time_zone)
    if month_start > day_number:
        month_start = get_new_moon_day(k, time_zone)
    a11 = get_lunar_month_11(yy, time_zone)
    b11 = a11
    if a11 >= month_start:
        lunar_year = yy
        a11 = get_lunar_month_11(yy - 1, time_zone)
    else:
        lunar_year = yy + 1
        b11 = get_lunar_month_11(yy + 1, time_zone)
    lunar_day = day_number - month_start + 1
    diff = int((month_start - a11) / 29.0)
    lunar_leap = 0
    lunar_month = diff + 11
    if b11 - a11 > 365:
        leap_month_diff = get_leap_month_offset(a11, time_zone)
        if diff >= leap_month_diff:
            lunar_month = diff + 10
            if diff == leap_month_diff:
                lunar_leap = 1
    if lunar_month > 12:
        lunar_month = lunar_month - 12
    if lunar_month >= 11 and diff < 4:
        lunar_year -= 1
    return [lunar_day, lunar_month, lunar_year, lunar_leap, day_number]


@pyscript_compile  # noqa: F821
def lunar_to_solar(
    lunar_day: int,
    lunar_month: int,
    lunar_year: int,
    lunar_leap: int,
    time_zone: int = 7,
) -> list[int]:
    """Convert a Lunar date to its corresponding Gregorian (Solar) date."""
    if lunar_month < 11:
        a11 = get_lunar_month_11(lunar_year - 1, time_zone)
        b11 = get_lunar_month_11(lunar_year, time_zone)
    else:
        a11 = get_lunar_month_11(lunar_year, time_zone)
        b11 = get_lunar_month_11(lunar_year + 1, time_zone)
    k = int(0.5 + (a11 - 2415021.076998695) / 29.530588853)
    off = lunar_month - 11
    if off < 0:
        off += 12
    if b11 - a11 > 365:
        leap_off = get_leap_month_offset(a11, time_zone)
        leap_month = leap_off - 2
        if leap_month < 0:
            leap_month += 12
        if lunar_leap != 0 and lunar_month != leap_month:
            return [0, 0, 0]
        elif lunar_leap != 0 or off >= leap_off:
            off += 1
    month_start = get_new_moon_day(k + off, time_zone)
    return jd_to_date(month_start + lunar_day - 1)


@pyscript_compile  # noqa: F821
def get_solar_term(day_number: int, time_zone: int) -> int:
    """Calculate the solar term index (0-23) for a given Julian day."""
    return int((sun_longitude(day_number - 0.5 - time_zone / 24.0) / math.pi) * 12)


"""
Code xử lý truy vấn và trả về kết quả
"""

DAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]

MONTHS = [
    "Giêng",
    "Hai",
    "Ba",
    "Tư",
    "Năm",
    "Sáu",
    "Bảy",
    "Tám",
    "Chín",
    "Mười",
    "Mười Một",
    "Chạp",
]

CAN = ["Giáp", "Ất", "Bính", "Đinh", "Mậu", "Kỷ", "Canh", "Tân", "Nhâm", "Quý"]

CHI = [
    "Tý",
    "Sửu",
    "Dần",
    "Mão",
    "Thìn",
    "Tỵ",
    "Ngọ",
    "Mùi",
    "Thân",
    "Dậu",
    "Tuất",
    "Hợi",
]

AUSPICIOUS_HOURS = [
    "110100101100",
    "001101001011",
    "110011010010",
    "101100110100",
    "001011001101",
    "010010110011",
]

SOLAR_TERM = [
    "Xuân Phân",
    "Thanh Minh",
    "Cốc Vũ",
    "Lập Hạ",
    "Tiểu Mãn",
    "Mang Chủng",
    "Hạ Chí",
    "Tiểu Thử",
    "Đại Thử",
    "Lập Thu",
    "Xử Thử",
    "Bạch Lộ",
    "Thu Phân",
    "Hàn Lộ",
    "Sương Giáng",
    "Lập Đông",
    "Tiểu Tuyết",
    "Đại Tuyết",
    "Đông Chí",
    "Tiểu Hàn",
    "Đại Hàn",
    "Lập Xuân",
    "Vũ Thủy",
    "Kinh Trập",
]

# Tý=0, Sửu=1, Dần=2, Mão=3, Thìn=4, Tỵ=5, Ngọ=6, Mùi=7, Thân=8, Dậu=9, Tuất=10, Hợi=11
AUSPICIOUS_DAY_START_CHI = {
    (1, 7): 0,  # Tháng 1, 7 (Dần, Thân) -> Bắt đầu từ Tý (index 0)
    (2, 8): 2,  # Tháng 2, 8 (Mão, Dậu)  -> Bắt đầu từ Dần (index 2)
    (3, 9): 4,  # Tháng 3, 9 (Thìn, Tuất) -> Bắt đầu từ Thìn (index 4)
    (4, 10): 6,  # Tháng 4, 10 (Tỵ, Hợi)  -> Bắt đầu từ Ngọ (index 6)
    (5, 11): 8,  # Tháng 5, 11 (Ngọ, Tý)  -> Bắt đầu từ Thân (index 8)
    (6, 12): 10,  # Tháng 6, 12 (Mùi, Sửu)  -> Bắt đầu từ Tuất (index 10)
}
# Các sao trong chu kỳ Hoàng Đạo / Hắc Đạo
# T: Hoàng Đạo (Tốt), X: Hắc Đạo (Xấu), B: Trung bình (Không tốt không xấu)
# Thanh Long (T), Minh Đường (T), Thiên Hình (B), Chu Tước (X), Kim Quỹ (B), Kim Đường (T),
# Bạch Hổ (X), Ngọc Đường (T), Thiên Lao (B), Nguyên Vũ (X), Tư Mệnh (B), Câu Trận (X)
AUSPICIOUS_DAY_STATUS = ["T", "T", "B", "X", "B", "T", "X", "T", "B", "X", "B", "X"]

# ==============================================================================
# DỮ LIỆU NHỊ THẬP BÁT TÚ
# ==============================================================================

TWENTY_EIGHT_MANSIONS = [
    {
        "ten_sao": "Giác Mộc Giao",
        "y_nghia": "Kiết tú; khí sinh trưởng, thuận mở đầu và khởi dựng nhẹ",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Cưới hỏi",
            "Khởi công nhẹ",
            "Dựng cột/cổng",
            "Dựng khung nhà",
            "Mở hàng nhỏ",
            "Xuất hành",
            "Ký kết vừa",
            "Cắt may",
        ],
        "nen_tranh": ["An táng/cải táng", "Xây/sửa mộ phần"],
    },
    {
        "ten_sao": "Cang Kim Long",
        "y_nghia": "Hung tú; dễ sinh tranh chấp, trắc trở đại sự",
        "danh_gia": "Xấu",
        "nen_lam": ["Gieo trồng", "Sắp xếp kho", "Việc vặt trong nhà", "Mua bán nhỏ"],
        "nen_tranh": [
            "Xây dựng/động thổ",
            "Cưới hỏi",
            "An táng",
            "Khai trương lớn",
            "Ký kết quan trọng",
            "Xuất hành xa",
        ],
    },
    {
        "ten_sao": "Đê Thổ Lạc",
        "y_nghia": "Hung tú; khí nặng, bất lợi cho việc lớn",
        "danh_gia": "Xấu",
        "nen_lam": ["Nông tác", "Dọn dẹp", "Tu bổ nhỏ", "Giao dịch nhỏ"],
        "nen_tranh": [
            "Khởi công lớn",
            "Dựng nhà",
            "Hôn lễ",
            "An táng",
            "Khai trương lớn",
            "Nhập trạch",
        ],
    },
    {
        "ten_sao": "Phòng Nhật Thố",
        "y_nghia": "Kiết tú; thuận lễ nghi và tạo tác chính danh",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Tế lễ",
            "Cưới hỏi",
            "Thượng lương/dựng mái",
            "Dời chỗ ở",
            "Nhập trạch",
            "Mở hàng",
            "Cắt may",
        ],
        "nen_tranh": ["Kiện tụng lớn", "Mua đất quy mô"],
    },
    {
        "ten_sao": "Tâm Nguyệt Hồ",
        "y_nghia": "Hung tú; dễ thị phi, hao tổn",
        "danh_gia": "Xấu",
        "nen_lam": [
            "Lễ bái giải hạn",
            "Sửa sang nhỏ",
            "Đi việc ngắn ngày",
            "Chữa bệnh",
        ],
        "nen_tranh": ["Khởi công lớn", "Cưới hỏi", "Kiện tụng", "Khai trương lớn"],
    },
    {
        "ten_sao": "Vĩ Hỏa Hổ",
        "y_nghia": "Kiết tú; cát lợi cầu tài, mưu sự tiến",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Cưới hỏi",
            "Sửa chữa nâng cấp nhà cửa",
            "Lát sân/ngõ",
            "Khai thông mương rãnh nhẹ",
            "Ký kết làm ăn",
        ],
        "nen_tranh": ["May đo lễ phục cầu kỳ", "Phá dỡ lớn vô cớ"],
    },
    {
        "ten_sao": "Cơ Thủy Báo",
        "y_nghia": "Kiết tú; hợp kiến tạo và thủy lợi",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Xây dựng",
            "Đào ao/giếng",
            "Nạo vét mương rãnh",
            "Mở cửa",
            "Khai thông đường nước",
            "Thu tài",
        ],
        "nen_tranh": ["Hôn lễ trọng thể", "Cắt may lễ phục"],
    },
    {
        "ten_sao": "Đẩu Mộc Giải",
        "y_nghia": "Kiết tú; hòa thuận, việc thường dễ thành",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Xây/sửa nhà",
            "Mở cửa",
            "Khai thông nước",
            "Cắt may",
            "Lập khế ước nhỏ",
            "Mở hàng",
        ],
        "nen_tranh": ["An táng lớn", "Phá dỡ ồ ạt"],
    },
    {
        "ten_sao": "Ngưu Kim Ngưu",
        "y_nghia": "Hung tú; trì trệ, bất lợi khai mở",
        "danh_gia": "Xấu",
        "nen_lam": ["Chăn nuôi", "Bảo trì thiết bị", "Dọn dẹp kho", "Kiểm tra an toàn"],
        "nen_tranh": [
            "Cưới hỏi",
            "Xây dựng",
            "Mở cửa/xả nước",
            "Nhập trạch",
            "Mua bán lớn",
        ],
    },
    {
        "ten_sao": "Nữ Thổ Bức",
        "y_nghia": "Hung tú; dễ vướng thị phi/kiện tụng",
        "danh_gia": "Xấu",
        "nen_lam": ["Học nghề/kỹ nghệ", "Bảo trì nhỏ", "Chuẩn bị giấy tờ"],
        "nen_tranh": [
            "Tang sự",
            "Tranh tụng",
            "Cắt may",
            "Mở cửa/xả nước",
            "Khởi công",
        ],
    },
    {
        "ten_sao": "Hư Nhật Thử",
        "y_nghia": "Hung tú; hư hao tản mát, kỵ khai mở",
        "danh_gia": "Xấu",
        "nen_lam": ["Tĩnh tu", "Sắp xếp nội bộ", "Bảo dưỡng nhỏ", "Thu hồi nợ khó"],
        "nen_tranh": [
            "Mở hàng",
            "Xuất hành",
            "Ký kết",
            "Cưới hỏi",
            "Động thổ",
            "An táng",
            "Mở cửa/xả nước",
        ],
    },
    {
        "ten_sao": "Nguy Nguyệt Yến",
        "y_nghia": "Hung tú; tiềm ẩn rủi ro, cần thận trọng",
        "danh_gia": "Xấu",
        "nen_lam": [
            "Kiểm định/nghiệm thu an toàn",
            "Tô trát nhỏ",
            "Công vụ cần kiểm soát rủi ro",
        ],
        "nen_tranh": [
            "Khởi công xây cất",
            "An táng",
            "Hôn lễ",
            "Mở cửa/xả nước",
            "Làm việc trên cao",
            "Ra biển xa",
        ],
    },
    {
        "ten_sao": "Thất Hỏa Trư",
        "y_nghia": "Kiết tú; vượng gia trạch, cát cho cư trú",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Cưới hỏi",
            "Dời ở",
            "Xây dựng/chống thấm",
            "Tế lễ",
            "Đào giếng",
            "Đặt bếp",
            "Nhập trạch",
        ],
        "nen_tranh": ["Làm tang lớn"],
    },
    {
        "ten_sao": "Bích Thủy Dư",
        "y_nghia": "Kiết tú; bền ổn, lợi kiến tạo và tàng trữ",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Cưới hỏi",
            "Xây dựng",
            "An táng/cải táng",
            "Đắp bờ kè",
            "Dựng tường rào",
            "Lập kho",
        ],
        "nen_tranh": ["Phá dỡ không cần thiết"],
    },
    {
        "ten_sao": "Khuê Mộc Lang",
        "y_nghia": "Hung tú; kỵ khai mở lớn, chỉ hợp chỉnh trang",
        "danh_gia": "Xấu",
        "nen_lam": [
            "Cắt may",
            "Sửa cửa/sơn sửa",
            "Thay biển hiệu nhỏ",
            "Xuất hành gần",
        ],
        "nen_tranh": ["Khai trương mở lớn", "Đầu tư mạo hiểm", "Ký hợp đồng dài hạn"],
    },
    {
        "ten_sao": "Lâu Kim Cẩu",
        "y_nghia": "Kiết tú; ổn cho gia sự và sửa sang",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Cưới hỏi",
            "Sửa nhà",
            "Lát sân/ngõ",
            "Làm cổng rào",
            "Dựng chuồng trại",
        ],
        "nen_tranh": ["Phá dỡ lớn", "Chuyển kho quy mô lớn cùng ngày"],
    },
    {
        "ten_sao": "Vị Thổ Trĩ",
        "y_nghia": "Kiết tú; thuận lễ nghi và công vụ",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Cưới hỏi",
            "Xin phép/khai báo",
            "Tuyển dụng",
            "Khởi công công trình công cộng",
            "Mở cửa hàng",
        ],
        "nen_tranh": ["Đầu cơ tư lợi", "Cắt may lễ phục", "An táng"],
    },
    {
        "ten_sao": "Mão Nhật Kê",
        "y_nghia": "Hung tú; dễ rối rắm, hư hỏng",
        "danh_gia": "Xấu",
        "nen_lam": ["Tu sửa nhỏ", "Dọn dẹp", "Kiểm kê", "Giảng dạy/học tập"],
        "nen_tranh": [
            "Động thổ",
            "Đóng giường ghế",
            "Làm mui thuyền",
            "Khai thông hào rãnh",
            "Cưới hỏi",
            "Khai trương",
        ],
    },
    {
        "ten_sao": "Tất Nguyệt Ô",
        "y_nghia": "Kiết tú; đại cát, vạn sự hanh thông",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Khởi công",
            "Xây nhà",
            "Cưới hỏi",
            "An táng",
            "Trổ/dựng cửa",
            "Đào giếng/kênh mương",
            "Khai trương",
            "Xuất hành",
            "Nhập học",
            "Cất nóc",
            "Nhập trạch",
        ],
        "nen_tranh": ["Đi thuyền"],
    },
    {
        "ten_sao": "Chủy Hỏa Hầu",
        "y_nghia": "Hung tú; dễ phát sinh tai ương",
        "danh_gia": "Xấu",
        "nen_lam": ["Kiểm tra an toàn", "Thu hồi/đình chỉ việc rủi ro"],
        "nen_tranh": [
            "Xây dựng",
            "An táng",
            "Cưới hỏi",
            "Mở hàng",
            "Xuất hành",
            "Ký kết mới",
        ],
    },
    {
        "ten_sao": "Sâm Thủy Viên",
        "y_nghia": "Kiết tú; thuận hành, hợp sửa chữa vừa phải",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Đi công vụ xa",
            "Dựng cửa",
            "Sửa chữa nhẹ",
            "Thay lợp mái nhỏ",
            "Mua sắm dụng cụ",
        ],
        "nen_tranh": ["Cưới hỏi", "An táng", "Khởi công lớn", "Vay vốn lớn"],
    },
    {
        "ten_sao": "Tỉnh Mộc Hãn",
        "y_nghia": "Kiết tú; cát với nông canh và kiến tạo",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Tế lễ",
            "Gieo trồng",
            "Động thổ/kiến tạo",
            "Dựng cột trụ",
            "Trồng cây lâu năm",
            "Mở nguồn nước",
        ],
        "nen_tranh": ["Cắt may lễ phục"],
    },
    {
        "ten_sao": "Quỷ Kim Dương",
        "y_nghia": "Hung tú; chỉ hợp việc âm, kỵ hỷ sự",
        "danh_gia": "Xấu",
        "nen_lam": ["An táng/cải táng", "Tu sửa mộ phần", "Tảo mộ"],
        "nen_tranh": ["Cưới hỏi", "Xây dựng", "Xuất hành", "Khai trương", "Ký kết"],
    },
    {
        "ten_sao": "Liễu Thổ Chương",
        "y_nghia": "Hung tú; dễ suy hao, dính kiện tụng",
        "danh_gia": "Xấu",
        "nen_lam": ["Dọn dẹp", "Thanh lý đồ cũ", "Kiểm tra an ninh an toàn"],
        "nen_tranh": [
            "An táng",
            "Xây dựng",
            "Mở cửa/xả nước",
            "Khai trương",
            "Khởi công",
            "Đi xa",
        ],
    },
    {
        "ten_sao": "Tinh Nhật Mã",
        "y_nghia": "Hung tú; động khí mạnh, dễ quá đà",
        "danh_gia": "Xấu",
        "nen_lam": [
            "Trồng trọt",
            "Tuyển dụng",
            "Tổ chức hoạt động vừa",
            "Sửa chữa vệ sinh",
        ],
        "nen_tranh": ["Tang sự", "Mở nước lớn", "Phá dỡ nhiều hạng mục cùng lúc"],
    },
    {
        "ten_sao": "Trương Nguyệt Lộc",
        "y_nghia": "Kiết tú; vui mừng, khai xướng rực rỡ",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Cưới hỏi",
            "Khai trương/mở chợ",
            "Tế lễ",
            "Khởi công",
            "Ký kết",
            "Mở rộng kinh doanh",
        ],
        "nen_tranh": ["Kiện tụng", "Phá bỏ công trình đang dùng tốt"],
    },
    {
        "ten_sao": "Dực Hỏa Xà",
        "y_nghia": "Hung tú; nóng nảy, bất lợi đại sự",
        "danh_gia": "Xấu",
        "nen_lam": [
            "Gieo trồng",
            "Thay cây",
            "Sửa vườn",
            "Kiểm định an toàn điện/nhiệt",
        ],
        "nen_tranh": [
            "Hôn lễ",
            "An táng",
            "Xây dựng cao",
            "Xuất hành xa",
            "Khai trương",
        ],
    },
    {
        "ten_sao": "Chẩn Thủy Dẫn",
        "y_nghia": "Kiết tú; thuận văn thư điền thổ, mưu sự ổn định",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Mua đất",
            "Ký nhận chức",
            "Tuyển dụng/nhập học",
            "Xây dựng",
            "Cưới hỏi",
            "Cắt may",
            "Lập kho",
        ],
        "nen_tranh": ["Chuyển nhà gấp", "Thay đổi lớn đột ngột"],
    },
]

# ==============================================================================
# DỮ LIỆU THẬP NHỊ TRỰC (12 TRỰC)
# ==============================================================================

TWELVE_DAY_OFFICERS = [
    {
        "ten_truc": "Trực Kiến",
        "y_nghia": "Khởi đầu/kiến lập; hợp việc vừa phải hơn là khai mở lớn.",
        "danh_gia": "Trung bình",
        "nen_lam": ["Xuất hành", "Thăm hỏi", "Gặp gỡ", "Ký kết nhỏ", "Cầu tài vừa"],
        "nen_tranh": ["Động thổ", "Xây cất lớn", "An táng", "Mở kho quy mô lớn"],
    },
    {
        "ten_truc": "Trực Trừ",
        "y_nghia": "Trừ bỏ/tẩy uế; thuận loại bỏ điều xấu và làm sạch.",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Giải hạn",
            "Dọn dẹp",
            "Tẩy uế",
            "Chữa bệnh",
            "Cắt tóc",
            "Bỏ điều cũ",
            "Xuất hành",
        ],
        "nen_tranh": ["Khai trương lớn", "Khởi công trọng đại", "Chi xuất tiền lớn"],
    },
    {
        "ten_truc": "Trực Mãn",
        "y_nghia": "Viên mãn/đầy đủ; hợp thu nạp và tổng kết hơn là khởi tạo.",
        "danh_gia": "Trung bình",
        "nen_lam": ["Tế lễ", "Sắp xếp/nhập kho", "Tổng kết", "Nhận hàng"],
        "nen_tranh": ["Cưới hỏi", "Khởi công", "Mở hàng/khai trương"],
    },
    {
        "ten_truc": "Trực Bình",
        "y_nghia": "Cân bằng/yên ổn; hợp việc thường nhật, kém hợp việc lớn.",
        "danh_gia": "Trung bình",
        "nen_lam": ["Giao dịch nhỏ", "Gặp gỡ", "Học hành", "Khám định kỳ"],
        "nen_tranh": ["Khởi sự lớn", "Động thổ", "Công trình hạ tầng nặng"],
    },
    {
        "ten_truc": "Trực Định",
        "y_nghia": "Ổn định/an định; tốt để chốt việc và an vị.",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Ký kết/khế ước",
            "Chốt kế hoạch",
            "An vị",
            "Nhập trạch",
            "Cưới hỏi",
        ],
        "nen_tranh": ["Tranh tụng", "Thưa kiện", "Xuất hành xa"],
    },
    {
        "ten_truc": "Trực Chấp",
        "y_nghia": "Giữ gìn/duy trì; thiên về duy trì bền vững, không hợp khai mở lớn.",
        "danh_gia": "Trung bình",
        "nen_lam": [
            "Tu sửa",
            "Xây bền vững",
            "Trồng cây lâu năm",
            "Tuyển dụng/nhận người",
        ],
        "nen_tranh": [
            "Dời nhà",
            "Mở cửa buôn bán",
            "Xuất/nhập kho lớn",
            "An sàng",
            "Chi tiền lớn",
        ],
    },
    {
        "ten_truc": "Trực Phá",
        "y_nghia": "Phá bỏ/kết liễu; hợp dỡ bỏ cái cũ.",
        "danh_gia": "Xấu",
        "nen_lam": ["Phá dỡ", "Thanh lý", "Kết thúc việc cũ", "Trị bệnh (phá bệnh)"],
        "nen_tranh": [
            "Khởi công",
            "Khai trương",
            "Cưới hỏi",
            "Nhập trạch",
            "Ký hợp đồng mới",
        ],
    },
    {
        "ten_truc": "Trực Nguy",
        "y_nghia": "Nguy nan/cẩn trọng; tốt khi làm việc đòi hỏi tỉ mỉ.",
        "danh_gia": "Trung bình",
        "nen_lam": [
            "Lễ bái",
            "Cầu an",
            "Các việc cần kiểm soát an toàn",
            "Đo đạc/thi công chi tiết",
        ],
        "nen_tranh": [
            "Khai trương",
            "Động thổ",
            "Cưới hỏi",
            "Đi xa mạo hiểm",
            "Việc mạo hiểm sông/biển",
        ],
    },
    {
        "ten_truc": "Trực Thành",
        "y_nghia": "Thành tựu/hoàn tất; rất thuận việc lớn và mừng.",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Khánh thành",
            "Ký kết",
            "Khai trương",
            "Cưới hỏi",
            "Nhập trạch",
            "Nhậm chức",
        ],
        "nen_tranh": ["Kiện tụng", "Cố ý phá dỡ"],
    },
    {
        "ten_truc": "Trực Thu",
        "y_nghia": "Thu nạp/thu hoạch; hợp gom góp cất giữ hơn là mở rộng.",
        "danh_gia": "Trung bình",
        "nen_lam": ["Thu hoạch", "Thu nợ", "Nhập kho", "Cất giữ"],
        "nen_tranh": ["Khai trương", "Khởi công", "Mở rộng mới"],
    },
    {
        "ten_truc": "Trực Khai",
        "y_nghia": "Khai mở/mở mang; đại cát cho các việc mở đầu.",
        "danh_gia": "Tốt",
        "nen_lam": [
            "Khai trương",
            "Khởi công nhẹ",
            "Xuất hành",
            "Đăng ký/ứng cử",
            "Nhận chức",
        ],
        "nen_tranh": ["An táng; kiêng động thổ nặng", "Lợp mái", "Đào giếng"],
    },
    {
        "ten_truc": "Trực Bế",
        "y_nghia": "Đóng lại/kết thúc; kỵ khởi sự.",
        "danh_gia": "Xấu",
        "nen_lam": ["Kết thúc", "Đóng kho", "Lấp hố/đắp đập", "Vá sửa chỗ hư"],
        "nen_tranh": ["Mở hàng", "Khởi công", "Cưới hỏi", "Xuất hành", "Nhậm chức"],
    },
]

FIELD_MAPPING = {
    "weekday_vi": "Thứ (tiếng Việt)",
    "relative_to": "Ngày Dương lịch mốc để so sánh (luôn là ngày hiện tại)",
    "full_solar_date_vi": "Ngày Dương lịch đầy đủ",
    "full_lunar_date_vi": "Ngày Âm lịch đầy đủ",
    "can_chi.calendar": "Lịch dùng để tính Can Chi (solar|lunar)",
    "can_chi.full_can_chi_date_vi": "Ngày Can Chi đầy đủ",
    "auspicious_day.day_type": "Loại ngày (hoang_dao|hac_dao|neutral)",
    "auspicious_day.name": "Tên loại ngày (Hoàng Đạo|Hắc Đạo|trung bình)",
    "ten_truc": "Tên Trực",
    "ten_sao": "Tên Sao",
    "y_nghia": "Ý nghĩa",
    "danh_gia": "Đánh giá",
    "nen_lam": "Nên làm",
    "nen_tranh": "Nên tránh",
}


def validate_date(date: str) -> bool:
    """Validate if a string is in YYYY-MM-DD format."""
    try:
        datetime.date.fromisoformat(date)
        return True
    except ValueError:
        return False


def split_date(date: str) -> tuple[int, int, int]:
    """Split a date string (YYYY-MM-DD) into day, month, and year."""
    current_date = datetime.date.fromisoformat(date)
    return current_date.day, current_date.month, current_date.year


def join_date(day: int, month: int, year: int) -> str:
    """Combine day, month, and year into a YYYY-MM-DD string."""
    return datetime.date(year, month, day).isoformat()


def get_day_of_week(day: int, month: int, year: int) -> int:
    """Get the ISO weekday (0=Monday, 6=Sunday) for a date."""
    return datetime.date(year, month, day).weekday()


def get_twelve_day_officers(jd: int) -> dict[str, Any]:
    """Calculate the Twelve Day Officer (Trực) for a Julian day."""
    st_index = get_solar_term(jd, 7)
    month_chi_list = [
        3,
        4,
        4,
        5,
        5,
        6,
        6,
        7,
        7,
        8,
        8,
        9,
        9,
        10,
        10,
        11,
        11,
        0,
        0,
        1,
        1,
        2,
        2,
        3,
    ]
    month_chi_index = month_chi_list[st_index]
    day_chi_index = (jd + 1) % 12
    duty_index = (day_chi_index - month_chi_index) % 12

    return TWELVE_DAY_OFFICERS[duty_index]


def get_twenty_eight_mansions(jd: int) -> dict[str, Any]:
    """Calculate the Twenty-Eight Mansion (Nhị Thập Bát Tú) for a Julian day."""
    jd_ref = 2451545
    mansion_ref_index = 16
    day_diff = jd - jd_ref
    current_mansion_index = (mansion_ref_index + day_diff) % 28

    return TWENTY_EIGHT_MANSIONS[current_mansion_index]


def get_auspicious_day(lunar_month: int, jd: int) -> dict[str, Any]:
    """Determine if a day is auspicious (Hoàng Đạo) or inauspicious (Hắc Đạo)."""
    chi_of_day_index = (jd + 1) % 12
    start_chi_index = -1
    for months, start_index in AUSPICIOUS_DAY_START_CHI.items():
        if lunar_month in months:
            start_chi_index = start_index
            break

    if start_chi_index == -1:
        return {"day_type": "unknown", "name": "Không xác định"}

    offset = (chi_of_day_index - start_chi_index) % 12

    if AUSPICIOUS_DAY_STATUS[offset] == "T":
        return {"day_type": "hoang_dao", "name": "Ngày Hoàng Đạo"}
    elif AUSPICIOUS_DAY_STATUS[offset] == "X":
        return {"day_type": "hac_dao", "name": "Ngày Hắc Đạo"}
    elif AUSPICIOUS_DAY_STATUS[offset] == "B":
        return {
            "day_type": "neutral",
            "name": "Ngày trung bình (Không tốt không xấu)",
        }
    return {"day_type": "unknown", "name": "Không xác định"}


def get_auspicious_hours(jd: int) -> list:
    """Calculate auspicious hours for a given Julian day based on its earthly branch."""
    chi_of_day = (jd + 1) % 12
    auspicious_hours_pattern = AUSPICIOUS_HOURS[chi_of_day % 6]
    auspicious_hours = []
    for i in range(12):
        if auspicious_hours_pattern[i] == "1":
            hour_name = CHI[i]
            start_hour = (i * 2 + 23) % 24
            end_hour = (i * 2 + 1) % 24
            start_hour = f"{start_hour:02d}:00"
            end_hour = f"{end_hour:02d}:00"
            result: dict[str, Any] = {
                "name": hour_name,
                "start_hour": start_hour,
                "end_hour": end_hour,
            }
            if start_hour == "23:00":
                result["cross_midnight"] = True
            auspicious_hours.append(result)

    return auspicious_hours


def get_number_of_days(date: str) -> int:
    """Calculate the day difference between today and a given date string."""
    start_date = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
    end_date = datetime.datetime.strptime(date, "%Y-%m-%d")
    return (end_date - start_date).days


@service(supports_response="only")  # noqa: F821
def date_conversion_tool(conversion_type: str, date: str, **kwargs) -> dict[str, Any]:
    """
    yaml
    name: Date Conversion Tool
    description: Convert between Solar (Duong lich) and Lunar (Am lich) dates.
    fields:
      conversion_type:
        name: Conversion Type
        description: Direction (s2l = Solar->Lunar, l2s = Lunar->Solar).
        example: s2l
        required: true
        selector:
          select:
            options:
              - label: Solar (Duong lich) to Lunar (Am lich)
                value: s2l
              - label: Lunar (Am lich) to Solar (Duong lich)
                value: l2s
      date:
        name: Date
        description: Date in YYYY-MM-DD.
        example: '"2022-01-01"'
        required: true
        selector:
          date:
      leap_month:
        name: Leap Month
        description: Lunar leap month? Only needed for l2s.
        example: false
        selector:
          boolean:
    """
    if not all([conversion_type, date]):
        return {
            "error": "Missing one or more required arguments: conversion_type, date"
        }

    if conversion_type not in ["s2l", "l2s"]:
        return {"error": "Wrong Conversion Type: conversion_type must be s2l or l2s"}

    if not validate_date(date):
        return {"error": "Invalid date format: YYYY-MM-DD"}

    day, month, year = split_date(date)
    if conversion_type == "s2l":
        try:
            response = {}
            lunar_date = solar_to_lunar(day, month, year)
            days = get_number_of_days(date)
            lunar_month = MONTHS[lunar_date[1] - 1] + (
                " nhuận" if lunar_date[3] == 1 else ""
            )
            can_chi_day = (
                CAN[(lunar_date[4] + 9) % 10] + " " + CHI[(lunar_date[4] + 1) % 12]
            )
            can_chi_month = (
                CAN[(lunar_date[2] * 12 + lunar_date[1] + 3) % 10]
                + " "
                + CHI[(lunar_date[1] + 1) % 12]
            )
            can_chi_year = (
                CAN[(lunar_date[2] + 6) % 10] + " " + CHI[(lunar_date[2] + 8) % 12]
            )
            auspicious_hours = get_auspicious_hours(lunar_date[4])
            auspicious_day = get_auspicious_day(lunar_date[1], lunar_date[4])
            twelve_day_officers = get_twelve_day_officers(lunar_date[4])
            twenty_eight_mansions = get_twenty_eight_mansions(lunar_date[4])
            response["mode"] = "s2l"
            response["solar_date"] = date
            response["lunar_date"] = join_date(
                lunar_date[0], lunar_date[1], lunar_date[2]
            )
            response["weekday_vi"] = f"{DAYS[get_day_of_week(day, month, year)]}"
            response["difference_days"] = abs(days)
            response["difference_direction"] = (
                "days_remaining" if days >= 0 else "days_elapsed"
            )
            response["relative_to"] = datetime.date.today().isoformat()
            response["lunar_date_meta"] = {"leap_month": lunar_date[3] == 1}
            response["full_lunar_date_vi"] = (
                f"{DAYS[get_day_of_week(day, month, year)]} ngày {lunar_date[0]} tháng {lunar_month} năm {can_chi_year}"
            )
            response["can_chi"] = {
                "calendar": "lunar",
                "full_can_chi_date_vi": f"{DAYS[get_day_of_week(day, month, year)]} ngày {can_chi_day} tháng {can_chi_month} năm {can_chi_year}",
            }
            response["solar_term"] = SOLAR_TERM[get_solar_term(lunar_date[4] + 1, 7)]
            response["extras"] = {
                "auspicious_hours": auspicious_hours,
                "auspicious_day": auspicious_day,
                "twelve_day_officers": twelve_day_officers,
                "twenty_eight_mansions": twenty_eight_mansions,
            }
            response["locale"] = "vi-VN"
            response["timezone"] = "Asia/Ho_Chi_Minh"
            response["field_mapping"] = FIELD_MAPPING

            return response
        except Exception as error:
            return {
                "error": f"Error converting Solar date {date} to Lunar date: {error}"
            }
    elif conversion_type == "l2s":
        if day > 30:
            return {"error": "Invalid date: Lunar day must be less than or equal to 30"}
        try:
            response = {}
            leap_month = bool(kwargs.get("leap_month", False))
            is_leap = 1 if leap_month else 0
            solar_date = lunar_to_solar(day, month, year, is_leap)
            if solar_date == [0, 0, 0]:
                return {
                    "error": f"Invalid lunar date: Day {day} Month {month} (Leap: {leap_month}) Year {year} does not exist."
                }
            days = get_number_of_days(
                join_date(solar_date[0], solar_date[1], solar_date[2])
            )
            day_number = jd_from_date(solar_date[0], solar_date[1], solar_date[2])
            can_chi_day = CAN[(day_number + 9) % 10] + " " + CHI[(day_number + 1) % 12]
            can_chi_month = (
                CAN[(year * 12 + month + 3) % 10] + " " + CHI[(month + 1) % 12]
            )
            can_chi_year = CAN[(year + 6) % 10] + " " + CHI[(year + 8) % 12]
            auspicious_hours = get_auspicious_hours(day_number)
            auspicious_day = get_auspicious_day(month, day_number)
            twelve_day_officers = get_twelve_day_officers(day_number)
            twenty_eight_mansions = get_twenty_eight_mansions(day_number)
            response["mode"] = "l2s"
            response["solar_date"] = join_date(
                solar_date[0], solar_date[1], solar_date[2]
            )
            response["lunar_date"] = date
            response["weekday_vi"] = (
                f"{DAYS[get_day_of_week(solar_date[0], solar_date[1], solar_date[2])]}"
            )
            response["difference_days"] = abs(days)
            response["difference_direction"] = (
                "days_remaining" if days >= 0 else "days_elapsed"
            )
            response["relative_to"] = datetime.date.today().isoformat()
            response["lunar_date_meta"] = {"leap_month": leap_month}
            response["full_solar_date_vi"] = (
                f"{DAYS[get_day_of_week(solar_date[0], solar_date[1], solar_date[2])]} ngày {solar_date[0]} tháng {solar_date[1]} năm {solar_date[2]}"
            )
            response["can_chi"] = {
                "calendar": "solar",
                "full_can_chi_date_vi": f"{DAYS[get_day_of_week(solar_date[0], solar_date[1], solar_date[2])]} ngày {can_chi_day} tháng {can_chi_month} năm {can_chi_year}",
            }
            response["solar_term"] = SOLAR_TERM[get_solar_term(day_number + 1, 7)]
            response["extras"] = {
                "auspicious_hours": auspicious_hours,
                "auspicious_day": auspicious_day,
                "twelve_day_officers": twelve_day_officers,
                "twenty_eight_mansions": twenty_eight_mansions,
            }
            response["locale"] = "vi-VN"
            response["timezone"] = "Asia/Ho_Chi_Minh"
            response["field_mapping"] = FIELD_MAPPING
            return response
        except Exception as error:
            return {
                "error": f"Error converting Lunar date {date} {kwargs} to Solar date: {error}"
            }
    else:
        return {"error": "Failed to convert date"}
