# Báo cáo mẫu B01

**MÔ PHỎNG · CẤU HÌNH GIẢ ĐỊNH.** Báo cáo thực tế từ CLI ngày 27/09/2026, phần mềm 0.1.0, config demo-1, seed 42. Chỉ chứa wafer/recipe giả và ID ngẫu nhiên của session.

- [Bản HTML dễ đọc](db690faac6e1430da1f2c07868149f4f.html)
- [Bản JSON đầy đủ](db690faac6e1430da1f2c07868149f4f.json)

B01 kiểm tra mất phản hồi sau khi START đã được lưu, rồi retry nguyên command ID. 4/4 điều kiện đạt; bằng chứng gồm phản hồi 503, kết quả command đã lưu, run ID và nhật ký không tăng khi retry.

Đây là bằng chứng phần mềm của đúng lần chạy này, không là xác nhận vật lý hay chứng nhận máy thật. Chạy lại bằng `python -m fabscope scenarios --id B01` để tạo session và báo cáo mới.
