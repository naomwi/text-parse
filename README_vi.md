# AI Novel Extractor & Translator (Công cụ Trích xuất & Dịch Truyện)

Một ứng dụng desktop viết bằng Python, có chức năng tự động trích xuất, làm sạch, và dịch truyện (Light Novel/Web Novel) từ các nền tảng phổ biến sang tiếng Việt bằng cách sử dụng AI Gemini của Google.

## Các Nền Tảng Hỗ Trợ

*   **Novelpia Global** (`global.novelpia.com/viewer/...`)
*   **Novelpia Main** (`novelpia.com/viewer/...`) - Tự động vượt qua các thẻ ẩn base64 chống trích xuất dữ liệu (anti-scraping)!
*   **Pixiv Novels** (`pixiv.net/novel/show.php?id=...`) - Trích xuất văn bản gốc hoàn chỉnh thông qua API tĩnh của Pixiv.
*   **Pixiv Series** (`pixiv.net/novel/series/...`) - Tự động lấy danh sách truyện và tải toàn bộ series theo thứ tự!

## Yêu Cầu Cài Đặt

1.  **Google Chrome** cần được cài đặt trên máy tính (hỗ trợ Windows).
2.  **Google Gemini API Key**: Bạn cần có một mã API (miễn phí) từ [Google AI Studio](https://aistudio.google.com/).
    *   *Lưu ý: Nếu sử dụng gói API miễn phí, công cụ có thể tự động tạm dừng 60 giây mỗi khi hết hạn mức (rate limit hits) và sau đó tự chạy tiếp.*

## Thiết Lập Ban Đầu

1.  **Giải nén các file** vào một thư mục trên máy tính của bạn.
2.  **Thêm API Key của bạn**:
    *   Mở file `.env` bằng phần mềm Notepad (nếu chưa có, tạo mới file `.env` hoặc đổi tên `.env.example`).
    *   Dán mã key của bạn vào như sau: `GEMINI_API_KEY="AIzaSyYourKeyHere..."`
3.  **Cài đặt & Chạy**:
    *   Nhấp đúp vào file **`Start_GUI.bat`**.
    *   Trong lần chạy đầu tiên, công cụ sẽ tự động cài đặt các thư viện Python cần thiết và trình duyệt Chromium Playwright (quá trình này mất khoảng vài phút).
    *   Sau khi hoàn tất, giao diện phần mềm sẽ tự động bật lên!

## Hướng Dẫn Sử Dụng

1.  **Khởi động ứng dụng**: Nhấp đúp vào file **`Start_GUI.bat`**.
2.  **Điền các thông tin**:
    *   **Start URL**: Dán link của chương ĐẦU TIÊN mà bạn muốn tải.
        *   *Dành cho Pixiv Series*: Dán URL của series (ví dụ: `https://www.pixiv.net/novel/series/15160863`) để tải toàn bộ các chương tự động.
    *   **Max Chapters**: Số lượng tối đa các chương bạn muốn tải.
    *   **Translation Toggle**: Bật (ON) chọn dịch ra tiếng Việt để dự án tạo thêm một file văn bản Tiếng Việt bên cạnh file nguyên bản (Tiếng Nhật/Hàn)!
3.  **Nhấn Start (Bắt đầu)** để bắt đầu trích xuất!

### Lưu ý cho Lần Chạy Đầu Tiên...
Một cửa sổ Google Chrome sẽ tự động bật lên. **Bạn cần truy cập và đăng nhập ngay vào Novelpia hoặc Pixiv trong cửa sổ Chrome này** để ứng dụng có quyền truy cập vào nội dung truyện bằng tài khoản của bạn (rất quan trọng đối với các bộ truyện R-18, hoặc trả phí).
Sau khi đăng nhập, script sẽ tự lưu quy trình và thực hiện các bước còn lại một cách hoàn toàn tự động ở chế độ chạy ngầm!

## Thư Mục Đầu Ra (Output)

Các nội dung trích xuất sẽ nằm ở thư mục `output/` (Mỗi loại truyện sẽ tự động được xếp vào một tiểu mục riêng). Với mỗi chương, bạn sẽ có các file:
*   `Chapter_001_TênChương_id1234_Cleaned.txt` - File text gốc đã được lọc và làm sạch văn bản dạng thô.
*   `Chapter_001_TênChương_id1234_Vietnamese_LN.txt` (Nếu bạn có bật tính năng Dịch vụ "Translate to Vietnamese").

## Xử Lý Sự Cố (Troubleshooting)

*   **"Gemini Rate Limit Hit"**: Gói miễn phí của Gemini giới hạn số lượng request tải về trên mỗi phút. Tool sẽ tự động tạm dừng quy trình 60 giây và khôi phục khi đã hoàn thành. Hãy cập nhật thiết lập thẻ thanh toán API nếu bạn mong muốn có tốc độ extract thần tốc và không giới hạn.
*   **Chrome bị đóng cửa sổ đột ngột**: Hãy đảm bảo rằng bạn đã đóng TẤT CẢ mọi cửa sổ Chrome trên hệ điều hành của mình trước khi khởi động tool vì công cụ này phải can thiệp profile Google vào hệ thống Chromium!
*   **Pixiv không có dữ liệu tải xuống**: Hãy kiểm tra Setting trên trang tài khoản Pixiv xem đã bật nút "Show R-18 Content" hay chưa nếu link tải truyện của bạn có chứa yếu tố giới hạn độ tuổi.
